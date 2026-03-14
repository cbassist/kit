"""
run_goal_001_mlx.py — Speculative decoding benchmark via MLX.

Runs the same 5 benchmark tasks from Goal 001 through MLX with:
1. 14B target alone (baseline)
2. 14B target + 1.5B draft (speculative decoding)

Measures throughput (tok/s), quality (critic-scored), and memory.
Validates draftbench prediction: 50-80% speedup with 1.5B draft.

Usage:
    uv run run_goal_001_mlx.py                # Full benchmark
    uv run run_goal_001_mlx.py --baseline     # Target only (no draft)
    uv run run_goal_001_mlx.py --draft-only   # Draft test only
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path

from benchmark import BENCHMARK_TASKS, score_response, _extract_json
from config import Paths

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

Paths.ensure_dirs()
RESULTS_DIR = Paths.ROOT / "goal_001_results"
RESULTS_DIR.mkdir(exist_ok=True)

# MLX model IDs
TARGET_MODEL = "mlx-community/Qwen2.5-Coder-14B-Instruct-4bit"
DRAFT_MODEL = "mlx-community/Qwen2.5-Coder-1.5B-Instruct-4bit"
NUM_DRAFT_TOKENS = 4
MAX_TOKENS = 1024


def load_models(use_draft: bool):
    """Load target and optionally draft model via mlx-lm."""
    from mlx_lm import load

    logger.info("[MLX] Loading target: %s", TARGET_MODEL)
    model, tokenizer = load(TARGET_MODEL)
    logger.info("[MLX] Target loaded.")

    draft_model = None
    if use_draft:
        logger.info("[MLX] Loading draft: %s", DRAFT_MODEL)
        draft_model, _ = load(DRAFT_MODEL)
        logger.info("[MLX] Draft loaded.")

    return model, tokenizer, draft_model


def generate_mlx(model, tokenizer, draft_model, prompt: str) -> dict:
    """Generate text with MLX, return response + metrics."""
    from mlx_lm import stream_generate

    messages = [{"role": "user", "content": prompt}]
    formatted = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )

    chunks = []
    final = None
    kwargs = {"max_tokens": MAX_TOKENS}
    if draft_model is not None:
        kwargs["draft_model"] = draft_model
        kwargs["num_draft_tokens"] = NUM_DRAFT_TOKENS

    for response in stream_generate(model, tokenizer, formatted, **kwargs):
        chunks.append(response.text)
        final = response

    text = "".join(chunks)

    metrics = {
        "generation_tps": getattr(final, "generation_tps", 0),
        "prompt_tps": getattr(final, "prompt_tps", 0),
        "peak_memory_gb": getattr(final, "peak_memory", 0),
        "token_count": len(chunks),
    }

    return {"text": text, "metrics": metrics}


def run_benchmark_mlx(model, tokenizer, draft_model, label: str) -> dict:
    """Run all 5 benchmark tasks and return results."""
    logger.info("\n%s", "=" * 60)
    logger.info("Running: %s", label)
    logger.info("=" * 60)

    task_results = []
    total_score = 0
    total_gen_tokens = 0
    total_gen_time = 0.0

    # Warmup — JIT compilation on first call
    logger.info("[MLX] Warmup generation...")
    warmup = generate_mlx(model, tokenizer, draft_model, "Say hello.")
    logger.info("[MLX] Warmup done. TPS: %.1f", warmup["metrics"]["generation_tps"])

    for i, task in enumerate(BENCHMARK_TASKS, 1):
        logger.info("[%d/5] %s", i, task["name"])
        start = time.time()

        result = generate_mlx(model, tokenizer, draft_model, task["prompt"])
        gen_time = time.time() - start

        # Score with critic
        scoring = score_response(result["text"], task["criteria"])

        tps = result["metrics"]["generation_tps"]
        total_gen_tokens += result["metrics"]["token_count"]
        total_gen_time += gen_time

        task_result = {
            "task_id": task["id"],
            "task_name": task["name"],
            "score": scoring["score"],
            "max_score": 5,
            "passed_criteria": scoring["passed_criteria"],
            "failed_criteria": scoring["failed_criteria"],
            "generation_tps": round(tps, 2),
            "peak_memory_gb": round(result["metrics"]["peak_memory_gb"], 2),
            "response_length": len(result["text"]),
            "time_sec": round(gen_time, 2),
        }
        task_results.append(task_result)
        total_score += scoring["score"]

        logger.info(
            "  Score: %d/5 | %.1f tok/s | %.1fs | %.1f GB peak",
            scoring["score"], tps, gen_time,
            result["metrics"]["peak_memory_gb"],
        )

    avg_tps = sum(t["generation_tps"] for t in task_results) / len(task_results)

    return {
        "label": label,
        "total_score": total_score,
        "max_score": 25,
        "avg_generation_tps": round(avg_tps, 2),
        "total_time_sec": round(total_gen_time, 2),
        "task_results": task_results,
    }


def print_comparison(baseline: dict, speculative: dict | None) -> None:
    """Print side-by-side comparison."""
    print("\n" + "=" * 70)
    print("GOAL 001 MLX RESULTS — Speculative Decoding Benchmark")
    print("=" * 70)

    print(f"\n{'Config':<35} {'Score':>8} {'Avg TPS':>10} {'Time':>8} {'Speedup':>10}")
    print("-" * 75)

    print(
        f"{'14B baseline (no draft)':<35} "
        f"{baseline['total_score']:>5}/25 "
        f"{baseline['avg_generation_tps']:>8.1f} "
        f"{baseline['total_time_sec']:>6.1f}s "
        f"{'—':>10}"
    )

    if speculative:
        speedup = (
            speculative["avg_generation_tps"] / baseline["avg_generation_tps"] - 1
        ) * 100 if baseline["avg_generation_tps"] > 0 else 0

        print(
            f"{'14B + 1.5B draft':<35} "
            f"{speculative['total_score']:>5}/25 "
            f"{speculative['avg_generation_tps']:>8.1f} "
            f"{speculative['total_time_sec']:>6.1f}s "
            f"{speedup:>+8.0f}%"
        )

        print(f"\nDraftbench prediction: +50-80% speedup")
        print(f"Actual speedup:        {speedup:+.0f}%")

        quality_delta = speculative["total_score"] - baseline["total_score"]
        print(f"Quality delta:         {quality_delta:+d} points (should be ~0)")

    print()


def main() -> int:
    parser = argparse.ArgumentParser(description="Goal 001: MLX Speculative Decoding")
    parser.add_argument("--baseline", action="store_true", help="Run baseline only")
    parser.add_argument("--draft-only", action="store_true", help="Run draft test only")
    args = parser.parse_args()

    run_baseline = not args.draft_only
    run_draft = not args.baseline

    print(f"\nGoal 001 MLX: Speculative Decoding Benchmark")
    print(f"Target: {TARGET_MODEL}")
    print(f"Draft:  {DRAFT_MODEL}")
    print(f"Draft tokens per step: {NUM_DRAFT_TOKENS}")
    print()

    results = {}

    if run_baseline:
        model, tokenizer, _ = load_models(use_draft=False)
        results["baseline"] = run_benchmark_mlx(
            model, tokenizer, None, "14B Q4 baseline (no draft)"
        )
        # Free memory before loading draft
        del model
        import gc; gc.collect()

    if run_draft:
        model, tokenizer, draft_model = load_models(use_draft=True)
        results["speculative"] = run_benchmark_mlx(
            model, tokenizer, draft_model,
            "14B Q4 + 1.5B Q4 draft (speculative)"
        )

    # Print comparison
    if "baseline" in results:
        print_comparison(results["baseline"], results.get("speculative"))
    elif "speculative" in results:
        print("\n" + "=" * 70)
        print("SPECULATIVE DECODING RESULTS (no baseline for comparison)")
        print("=" * 70)
        s = results["speculative"]
        print(f"Score: {s['total_score']}/25 | Avg TPS: {s['avg_generation_tps']:.1f} | Time: {s['total_time_sec']:.1f}s")

    # Save results
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    path = RESULTS_DIR / f"mlx_speculative_{timestamp}.json"
    payload = {
        "timestamp": timestamp,
        "target_model": TARGET_MODEL,
        "draft_model": DRAFT_MODEL,
        "num_draft_tokens": NUM_DRAFT_TOKENS,
        **results,
    }
    path.write_text(json.dumps(payload, indent=2))
    logger.info("Results saved to %s", path)

    print(f"Full results: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
