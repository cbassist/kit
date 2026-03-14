"""
benchmark.py — Model benchmarking tool for Goal 001.

Runs a fixed task suite against a specified Ollama model config
and returns quality scores. The experiment loop uses this to
compare model configs and converge on the optimal setup.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from typing import Any

import llm
from config import Models

logger = logging.getLogger(__name__)

# ── Fixed benchmark tasks ─────────────────────────────────────
BENCHMARK_TASKS = [
    {
        "id": "code_gen",
        "name": "Code Generation",
        "prompt": (
            "Write a Python function called `binary_search` that takes a sorted list "
            "and a target value, returns the index if found or -1 if not. "
            "Include a docstring and handle edge cases."
        ),
        "criteria": [
            "Function is syntactically valid Python",
            "Handles empty list edge case",
            "Returns -1 when target not found",
            "Has a docstring",
            "Uses O(log n) algorithm, not linear scan",
        ],
    },
    {
        "id": "structured_output",
        "name": "Structured JSON Output",
        "prompt": (
            "Given this bug report: 'Users report that the login page times out after "
            "10 seconds when the database connection pool is exhausted during peak hours.' "
            "Output a JSON object with keys: root_cause, fix, confidence (0-1), priority (P1-P4)."
        ),
        "criteria": [
            "Output is valid JSON",
            "Contains all four required keys",
            "root_cause is specific and plausible",
            "fix is actionable",
            "confidence is a number between 0 and 1",
        ],
    },
    {
        "id": "tool_calling",
        "name": "Tool Selection",
        "prompt": (
            "You have these tools available:\n"
            "- check_disk_usage(path: str) -> dict with total_gb, used_gb, free_gb\n"
            "- list_processes(sort_by: str) -> list of running processes\n"
            "- read_log(service: str, lines: int) -> recent log lines\n"
            "- restart_service(name: str) -> bool\n\n"
            "The user says: 'The API is returning 500 errors and the server seems slow.'\n"
            "Which tools should you call first and in what order? Return a JSON array of "
            "tool calls with arguments, in priority order."
        ),
        "criteria": [
            "Output is valid JSON array",
            "Includes read_log as one of the first steps",
            "Includes check_disk_usage or list_processes for diagnosis",
            "Does NOT restart_service as the first action",
            "Arguments are reasonable and complete",
        ],
    },
    {
        "id": "reasoning",
        "name": "Logical Reasoning",
        "prompt": (
            "A farmer has 17 sheep. All but 9 die. How many sheep does the farmer have left?\n"
            "Think carefully and explain your reasoning step by step, then give the final answer."
        ),
        "criteria": [
            "Final answer is 9",
            "Reasoning explains that 'all but 9' means 9 survive",
            "Does not say 8 or 17 or any other wrong answer",
        ],
    },
    {
        "id": "instruction_following",
        "name": "Instruction Following",
        "prompt": (
            "Rewrite the following paragraph in EXACTLY 3 sentences. No more, no fewer.\n\n"
            "'Machine learning models require large datasets for training. The quality of "
            "the data matters as much as the quantity. Preprocessing steps like normalization "
            "and feature engineering can significantly impact model performance. Transfer "
            "learning allows models trained on one task to be adapted for another, reducing "
            "the need for massive datasets. Fine-tuning pre-trained models has become the "
            "standard approach in many domains.'"
        ),
        "criteria": [
            "Output contains exactly 3 sentences",
            "Covers the key themes: data quality, preprocessing, transfer learning",
            "Is coherent and grammatically correct",
        ],
    },
]


@dataclass
class BenchmarkResult:
    """Result from running one model config through the benchmark suite."""
    model_name: str
    total_score: float = 0.0
    max_score: float = 25.0
    task_results: list[dict[str, Any]] = field(default_factory=list)
    total_time_sec: float = 0.0
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def score_response(response: str, criteria: list[str]) -> dict[str, Any]:
    """
    Use the PROJECT model (critic tier) to score a response against criteria.
    Returns {"score": float 0-5, "passed_criteria": [...], "failed_criteria": [...]}.
    """
    criteria_text = "\n".join(f"  {i+1}. {c}" for i, c in enumerate(criteria))

    messages = [{
        "role": "user",
        "content": (
            f"Score this response against the criteria below.\n\n"
            f"CRITERIA:\n{criteria_text}\n\n"
            f"RESPONSE:\n{response}\n\n"
            f"Return JSON only:\n"
            f'{{"score": <0-5 integer, one point per criterion met>, '
            f'"passed_criteria": [<list of met criteria numbers>], '
            f'"failed_criteria": [<list of failed criteria numbers>]}}'
        ),
    }]

    raw = llm.call(messages, model=Models.PROJECT, system_prompt=(
        "You are a precise benchmark scorer. Score responses against criteria. "
        "Be strict. Return JSON only."
    ))

    try:
        data = json.loads(raw)
        return {
            "score": min(5, max(0, int(data.get("score", 0)))),
            "passed_criteria": data.get("passed_criteria", []),
            "failed_criteria": data.get("failed_criteria", []),
        }
    except (json.JSONDecodeError, ValueError):
        logger.warning("[BENCHMARK] Could not parse score JSON, defaulting to 0.")
        return {"score": 0, "passed_criteria": [], "failed_criteria": list(range(1, len(criteria)+1))}


def run_benchmark(model_name: str) -> BenchmarkResult:
    """
    Run the full benchmark suite against a specific Ollama model.
    Returns a BenchmarkResult with total score out of 25.
    """
    result = BenchmarkResult(model_name=model_name)
    start = time.time()

    logger.info("[BENCHMARK] Starting benchmark for model: %s", model_name)

    for task in BENCHMARK_TASKS:
        task_start = time.time()
        logger.info("[BENCHMARK] Running task: %s", task["name"])

        try:
            # Call the model under test
            messages = [{"role": "user", "content": task["prompt"]}]
            response = llm.call(
                messages,
                model=model_name,
                system_prompt="You are a helpful assistant. Follow instructions precisely.",
            )

            # Score it using the critic tier
            scoring = score_response(response, task["criteria"])
            task_time = time.time() - task_start

            task_result = {
                "task_id": task["id"],
                "task_name": task["name"],
                "score": scoring["score"],
                "max_score": 5,
                "passed_criteria": scoring["passed_criteria"],
                "failed_criteria": scoring["failed_criteria"],
                "response_length": len(response),
                "time_sec": round(task_time, 2),
            }
            result.task_results.append(task_result)
            result.total_score += scoring["score"]

            logger.info(
                "[BENCHMARK] %s: %d/5 (%.1fs)",
                task["name"], scoring["score"], task_time,
            )

        except Exception as exc:
            logger.error("[BENCHMARK] Task %s failed: %s", task["name"], exc)
            result.task_results.append({
                "task_id": task["id"],
                "task_name": task["name"],
                "score": 0,
                "max_score": 5,
                "error": str(exc),
                "time_sec": round(time.time() - task_start, 2),
            })

    result.total_time_sec = round(time.time() - start, 2)
    logger.info(
        "[BENCHMARK] %s finished: %.0f/25 in %.1fs",
        model_name, result.total_score, result.total_time_sec,
    )
    return result


# ── Available model configs for Goal 001 ──────────────────────
GOAL_001_CONFIGS = [
    {"name": "qwen2.5-coder:14b-instruct-q6_K", "label": "14B Q6 (no draft)", "memory_est_gb": 12},
    {"name": "llama3.2:1b", "label": "1B baseline", "memory_est_gb": 1.3},
]

# Models that need to be pulled before running full sweep:
# {"name": "qwen2.5:1.5b", "label": "1.5B (draft candidate)", "memory_est_gb": 1.2},
# {"name": "qwen2.5:7b", "label": "7B Q4", "memory_est_gb": 5},
# {"name": "qwen2.5:32b", "label": "32B Q4", "memory_est_gb": 18},
