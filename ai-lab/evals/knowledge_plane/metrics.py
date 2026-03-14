"""Weighted score aggregation and per-arm result summarization."""

from __future__ import annotations

from typing import Any


def aggregate_case_score(
    support_recall: float,
    schema_ok: bool,
    gold_fact_coverage: float,
    citations_ok: bool,
) -> dict[str, Any]:
    score = (
        0.35 * support_recall
        + 0.25 * gold_fact_coverage
        + 0.20 * (1.0 if schema_ok else 0.0)
        + 0.20 * (1.0 if citations_ok else 0.0)
    )
    return {
        "case_score": round(score, 4),
        "weights": {
            "support_recall": 0.35,
            "gold_fact_coverage": 0.25,
            "schema_ok": 0.20,
            "citations_ok": 0.20,
        },
    }


def summarize_results(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"count": 0, "avg_case_score": 0.0}

    avg = sum(r["aggregate"]["case_score"] for r in rows) / len(rows)
    by_arm: dict[str, list[float]] = {}
    for row in rows:
        by_arm.setdefault(row["arm"], []).append(row["aggregate"]["case_score"])

    return {
        "count": len(rows),
        "avg_case_score": round(avg, 4),
        "by_arm": {
            arm: {
                "count": len(scores),
                "avg_case_score": round(sum(scores) / len(scores), 4),
            }
            for arm, scores in by_arm.items()
        },
    }
