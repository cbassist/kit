"""
run_goal_001.py — First validation: Model Optimization on M4 Pro 24GB.

Runs available Ollama models through a fixed benchmark suite.
Compares quality scores to find the optimal worker-tier config.

This is a SMOKE TEST of the lab architecture:
- Does the benchmark harness work?
- Does scoring produce differentiated results?
- Do results align with draftbench predictions?

Usage:
    # Smoke test with available models (no pull needed)
    uv run run_goal_001.py

    # Full sweep after pulling models
    uv run run_goal_001.py --full

    # Test a specific model
    uv run run_goal_001.py --model qwen2.5-coder:14b-instruct-q6_K
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

from config import Paths
from benchmark import run_benchmark, GOAL_001_CONFIGS, BenchmarkResult
import memory

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

Paths.ensure_dirs()
RESULTS_DIR = Paths.ROOT / "goal_001_results"
RESULTS_DIR.mkdir(exist_ok=True)


def check_ollama_model(model_name: str) -> bool:
    """Check if a model is available in Ollama."""
    import subprocess
    result = subprocess.run(
        ["ollama", "list"], capture_output=True, text=True
    )
    return model_name in result.stdout


def run_sweep(configs: list[dict]) -> list[BenchmarkResult]:
    """Run benchmark across all specified model configs."""
    results: list[BenchmarkResult] = []

    for i, config in enumerate(configs, 1):
        model = config["name"]
        label = config["label"]
        mem_est = config["memory_est_gb"]

        logger.info(
            "\n{'='*60}\n"
            f"[{i}/{len(configs)}] {label} ({model})\n"
            f"Estimated memory: {mem_est}GB\n"
            f"{'='*60}"
        )

        if not check_ollama_model(model):
            logger.warning("Model %s not available. Skipping.", model)
            r = BenchmarkResult(model_name=model, error=f"Not installed")
            results.append(r)
            continue

        result = run_benchmark(model)
        results.append(result)

        # Brief pause between models to let memory settle
        if i < len(configs):
            logger.info("Pausing 5s between models for memory cleanup...")
            time.sleep(5)

    return results


def print_results(results: list[BenchmarkResult]) -> None:
    """Print a comparison table."""
    print("\n" + "=" * 70)
    print("GOAL 001 RESULTS — Model Quality Benchmark")
    print("=" * 70)
    print(f"\n{'Model':<40} {'Score':>8} {'Time':>8} {'Status':>10}")
    print("-" * 70)

    for r in sorted(results, key=lambda x: x.total_score, reverse=True):
        if r.error:
            print(f"{r.model_name:<40} {'—':>8} {'—':>8} {r.error:>10}")
        else:
            print(
                f"{r.model_name:<40} "
                f"{r.total_score:>5.0f}/25 "
                f"{r.total_time_sec:>6.1f}s "
                f"{'OK':>10}"
            )

    # Find winner
    valid = [r for r in results if not r.error]
    if valid:
        winner = max(valid, key=lambda r: r.total_score)
        print(f"\nWINNER: {winner.model_name} ({winner.total_score:.0f}/25)")
        print(f"Quality per second: {winner.total_score / winner.total_time_sec:.2f}")

    print()


def save_results(results: list[BenchmarkResult]) -> Path:
    """Save full results to JSON."""
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    path = RESULTS_DIR / f"sweep_{timestamp}.json"

    payload = {
        "timestamp": timestamp,
        "model_count": len(results),
        "results": [r.to_dict() for r in results],
    }

    path.write_text(json.dumps(payload, indent=2))
    logger.info("Results saved to %s", path)
    return path


def record_winner(results: list[BenchmarkResult]) -> None:
    """Save the winning config as a heuristic in skills DB."""
    valid = [r for r in results if not r.error]
    if not valid:
        return

    winner = max(valid, key=lambda r: r.total_score)
    memory.save_skill(
        description=(
            f"Optimal worker model on M4 Pro 24GB: {winner.model_name} "
            f"(score {winner.total_score:.0f}/25, {winner.total_time_sec:.1f}s total)"
        ),
        context="model_optimization_goal_001",
        tags=["model", "optimization", "worker", "ollama", "m4_pro"],
    )
    logger.info("[MEMORY] Winner recorded: %s", winner.model_name)


def main() -> int:
    parser = argparse.ArgumentParser(description="Goal 001: Model Optimization")
    parser.add_argument(
        "--model", default=None,
        help="Test a single model instead of sweep",
    )
    parser.add_argument(
        "--full", action="store_true",
        help="Run full sweep (requires all models pulled)",
    )
    args = parser.parse_args()

    if args.model:
        # Single model test
        configs = [{"name": args.model, "label": args.model, "memory_est_gb": 0}]
    elif args.full:
        # Full sweep including models that need pulling
        configs = GOAL_001_CONFIGS + [
            {"name": "qwen2.5:1.5b", "label": "1.5B (draft candidate)", "memory_est_gb": 1.2},
            {"name": "qwen2.5:7b", "label": "7B Q4", "memory_est_gb": 5},
        ]
    else:
        # Smoke test with already-installed models
        configs = GOAL_001_CONFIGS

    print(f"\nGoal 001: Model Optimization Benchmark")
    print(f"Models to test: {len(configs)}")
    print(f"Tasks per model: 5 (25 points max)")
    print(f"Critic model: {__import__('config').Models.PROJECT}")
    print()

    results = run_sweep(configs)
    print_results(results)
    path = save_results(results)
    record_winner(results)

    print(f"Full results: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
