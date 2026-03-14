"""Deterministic graders: retrieval recall, schema checks, citation groundedness, gold-fact coverage."""

from __future__ import annotations

import json
from typing import Any


def deterministic_retrieval_grade(
    retrieved_doc_ids: list[str],
    expected_supporting_docs: list[str],
) -> dict[str, Any]:
    expected = set(expected_supporting_docs)
    got = set(retrieved_doc_ids)

    hits = expected.intersection(got)
    recall = (len(hits) / len(expected)) if expected else 1.0

    return {
        "expected_count": len(expected),
        "hit_count": len(hits),
        "support_recall": recall,
        "hits": sorted(hits),
        "misses": sorted(expected - got),
    }


def schema_grade(answer_obj: dict[str, Any]) -> dict[str, Any]:
    required = [
        "answer",
        "key_evidence_ids",
        "assumptions",
        "confidence",
        "next_action",
        "kill_criteria",
        "escalation_trigger",
    ]
    missing = [k for k in required if k not in answer_obj]
    return {
        "schema_ok": len(missing) == 0,
        "missing_fields": missing,
    }


def evidence_citation_grade(
    answer_obj: dict[str, Any],
    retrieved_doc_ids: list[str],
) -> dict[str, Any]:
    cited = answer_obj.get("key_evidence_ids", [])
    if not isinstance(cited, list):
        cited = []

    retrieved = set(retrieved_doc_ids)

    def _is_valid_citation(doc_id: Any) -> bool:
        if not isinstance(doc_id, str):
            return False

        normalized = doc_id.strip()
        if not normalized or normalized.isdigit():
            return False

        # Allow chunk-level IDs (e.g. CANON.md::chunk-0) to match doc-level retrieved IDs by prefix.
        return any(normalized.startswith(retrieved_id) for retrieved_id in retrieved)

    bad = sorted(
        [doc_id for doc_id in cited if not _is_valid_citation(doc_id)], key=str
    )

    return {
        "citations_ok": len(bad) == 0,
        "cited_count": len(cited),
        "invalid_citations": bad,
    }


def gold_fact_coverage(answer_text: str, gold_facts: list[str]) -> dict[str, Any]:
    answer_lower = answer_text.lower()
    matched = [fact for fact in gold_facts if fact.lower() in answer_lower]
    coverage = (len(matched) / len(gold_facts)) if gold_facts else 1.0
    return {
        "gold_fact_coverage": coverage,
        "matched_gold_facts": matched,
    }


def try_parse_json(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except Exception:
        return {"_raw_text": text, "_json_parse_failed": True}
