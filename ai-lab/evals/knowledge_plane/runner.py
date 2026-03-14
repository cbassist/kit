"""Main CLI orchestration: load cases, run local/hosted arms, grade, and write results."""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
from importlib import import_module
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

from openai import OpenAI

from .adapters import (
    LocalRetriever,
    OpenAIFileSearchRetriever,
    build_context_pack,
    chunks_to_jsonable,
)
from .graders import (
    deterministic_retrieval_grade,
    evidence_citation_grade,
    gold_fact_coverage,
    schema_grade,
    try_parse_json,
)
from .metrics import aggregate_case_score, summarize_results
from .normalization import (
    build_manifest_index,
    manifest_corpus_version,
    validate_cases_against_manifest,
    validate_retrieved_doc_ids_known,
)

RESULTS_DIR = Path(__file__).resolve().parent / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


class DummyLocalBackend:
    def search(self, query: str, top_k: int = 8) -> list[dict[str, Any]]:
        return [
            {
                "doc_id": "CANON.md",
                "chunk_id": "stub-1",
                "text": f"Stub local retrieval result for query: {query}",
                "score": 0.1,
                "metadata": {"stub": True},
            }
        ][:top_k]


def load_local_backend(spec: str | None):
    if not spec:
        return DummyLocalBackend()

    if ":" not in spec:
        raise ValueError("Local backend spec must look like 'package.module:ClassName'")

    module_name, class_name = spec.split(":", 1)
    module = import_module(module_name)
    cls = getattr(module, class_name)
    return cls()


def load_json(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_cases(path: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def strategic_prompt(case: dict[str, Any], context_pack: str) -> str:
    constraints = "\n".join(f"- {x}" for x in case["context"]["constraints"])
    already_tried = "\n".join(f"- {x}" for x in case["context"]["already_tried"])

    return f"""You are the strategist for this project.

## Objective
{case["question"]}

## Success Metric
Return the highest-leverage answer grounded in the retrieved evidence.

## Current State Snapshot
{json.dumps(case["context"], indent=2)}

## Constraints
{constraints}

## What's Already Been Tried
{already_tried}

## Decision Question
{case["decision_question"]}

## Retrieved Evidence
{context_pack}

## Required Output Schema
Return JSON only with this schema:
{{
  "answer": "string",
  "key_evidence_ids": ["string"],
  "assumptions": ["string"],
  "confidence": 0.0,
  "next_action": "string",
  "kill_criteria": ["string"],
  "escalation_trigger": "string"
}}
`key_evidence_ids` must contain `doc_id` values from the Retrieved Evidence section (for example, `CANON.md`), not bracket index numbers like `1`, `2`, or `3`.
""".strip()


def answer_with_context(
    client: OpenAI,
    model: str,
    case: dict[str, Any],
    context_pack: str,
) -> tuple[str, dict[str, Any]]:
    prompt = strategic_prompt(case, context_pack)

    started = time.time()
    resp = client.responses.create(
        model=model,
        input=prompt,
        text={"format": {"type": "json_object"}},
        store=False,
    )
    latency = time.time() - started

    text = getattr(resp, "output_text", "") or ""
    usage = getattr(resp, "usage", None)

    usage_dict = {}
    if usage:
        usage_dict = {
            "input_tokens": getattr(usage, "input_tokens", None),
            "output_tokens": getattr(usage, "output_tokens", None),
            "total_tokens": getattr(usage, "total_tokens", None),
        }

    return text, {
        "latency_sec": round(latency, 3),
        "usage": usage_dict,
    }


def run_arm(
    *,
    arm: str,
    case: dict[str, Any],
    client: OpenAI,
    model: str,
    vector_store_id: str | None,
    manifest: dict[str, Any],
    manifest_index: dict[str, Any],
    local_backend_spec: str | None,
) -> dict[str, Any]:
    if arm == "local":
        retriever = LocalRetriever(load_local_backend(local_backend_spec))
    elif arm == "hosted":
        if not vector_store_id:
            raise RuntimeError("OPENAI_VECTOR_STORE_ID is required for hosted arm.")
        retriever = OpenAIFileSearchRetriever(
            client=client,
            vector_store_id=vector_store_id,
            model=model,
            manifest_index=manifest_index,
        )
    else:
        raise ValueError(f"Unknown arm: {arm}")

    retrieved = retriever.retrieve(case["retrieval_query"], k=case.get("top_k", 8))
    retrieved_doc_ids = [c.doc_id for c in retrieved]
    validate_retrieved_doc_ids_known(retrieved_doc_ids, manifest)

    context_pack = build_context_pack(retrieved)
    answer_text, llm_meta = answer_with_context(client, model, case, context_pack)

    answer_obj = try_parse_json(answer_text)

    retrieval_grade = deterministic_retrieval_grade(
        retrieved_doc_ids=retrieved_doc_ids,
        expected_supporting_docs=case["expected_supporting_docs"],
    )
    schema = schema_grade(answer_obj)
    citations = evidence_citation_grade(answer_obj, retrieved_doc_ids)
    fact_grade = gold_fact_coverage(
        answer_text=answer_obj.get("answer", answer_text),
        gold_facts=case["gold_facts"],
    )
    aggregate = aggregate_case_score(
        support_recall=retrieval_grade["support_recall"],
        schema_ok=schema["schema_ok"],
        gold_fact_coverage=fact_grade["gold_fact_coverage"],
        citations_ok=citations["citations_ok"],
    )

    return {
        "case_id": case["id"],
        "arm": arm,
        "question": case["question"],
        "retrieved": chunks_to_jsonable(retrieved),
        "answer_raw": answer_text,
        "answer_obj": answer_obj,
        "retrieval_grade": retrieval_grade,
        "schema_grade": schema,
        "citation_grade": citations,
        "fact_grade": fact_grade,
        "aggregate": aggregate,
        "llm_meta": llm_meta,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", required=True)
    parser.add_argument(
        "--manifest",
        default=str(RESULTS_DIR / "export_manifest.json"),
        help="Export manifest produced by exporters.py",
    )
    parser.add_argument(
        "--arm",
        choices=["local", "hosted", "both"],
        default="both",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("KNOWLEDGE_PLANE_MODEL", "gpt-5.4"),
    )
    parser.add_argument(
        "--local-backend",
        default=os.environ.get("KNOWLEDGE_PLANE_LOCAL_BACKEND"),
        help="Import path like 'aos.retrieve:RetrieverBackend'",
    )
    args = parser.parse_args()

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    vector_store_id = os.environ.get("OPENAI_VECTOR_STORE_ID")

    manifest = load_json(args.manifest)
    manifest_index = build_manifest_index(manifest)

    cases = load_cases(args.cases)
    validate_cases_against_manifest(cases, manifest)

    arms = ["local", "hosted"] if args.arm == "both" else [args.arm]

    rows: list[dict[str, Any]] = []
    for case in cases:
        for arm in arms:
            logger.info("Running case=%s arm=%s", case["id"], arm)
            row = run_arm(
                arm=arm,
                case=case,
                client=client,
                model=args.model,
                vector_store_id=vector_store_id,
                manifest=manifest,
                manifest_index=manifest_index,
                local_backend_spec=args.local_backend,
            )
            rows.append(row)

    payload = {
        "model": args.model,
        "case_count": len(cases),
        "run_count": len(rows),
        "corpus_version": manifest.get("corpus_version")
        or manifest_corpus_version(manifest),
        "vector_store_id": manifest.get("vector_store_id"),
        "summary": summarize_results(rows),
        "results": rows,
    }

    out_path = RESULTS_DIR / "latest.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print(json.dumps(payload["summary"], indent=2))
    print(f"\nWrote results to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
