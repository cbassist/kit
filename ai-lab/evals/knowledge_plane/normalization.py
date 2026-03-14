from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


def canonical_doc_id(path: str | Path) -> str:
    """
    Canonical doc IDs are always repo-relative POSIX-style paths.
    """
    return str(Path(path).as_posix()).lstrip("./")


def safe_upload_name(doc_id: str, sha256_hex: str) -> str:
    """
    Deterministic hosted filename derived from canonical doc_id.
    We do NOT trust hosted filenames to equal repo-relative paths.
    """
    stem = re.sub(r"[^A-Za-z0-9._-]+", "__", doc_id)
    short = sha256_hex[:12]
    return f"{short}__{stem}"


def manifest_corpus_version(manifest: dict[str, Any]) -> str:
    """
    Stable corpus version from doc_id + sha256 pairs.
    """
    items = sorted(
        (f["doc_id"], f["sha256"])
        for f in manifest.get("files", [])
    )
    raw = json.dumps(items, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def build_manifest_index(manifest: dict[str, Any]) -> dict[str, Any]:
    by_doc_id: dict[str, dict[str, Any]] = {}
    by_upload_name: dict[str, dict[str, Any]] = {}
    by_file_id: dict[str, dict[str, Any]] = {}

    for entry in manifest.get("files", []):
        doc_id = entry["doc_id"]
        by_doc_id[doc_id] = entry

        upload_name = entry.get("upload_name")
        if upload_name:
            by_upload_name[upload_name] = entry

        file_id = entry.get("file_id")
        if file_id:
            by_file_id[file_id] = entry

    return {
        "by_doc_id": by_doc_id,
        "by_upload_name": by_upload_name,
        "by_file_id": by_file_id,
    }


def normalize_hosted_doc_id(
    *,
    filename: str | None,
    file_id: str | None,
    manifest_index: dict[str, Any],
) -> str:
    """
    Resolve hosted retrieval results back to canonical repo-relative doc_id.
    """
    if file_id and file_id in manifest_index["by_file_id"]:
        return manifest_index["by_file_id"][file_id]["doc_id"]

    if filename and filename in manifest_index["by_upload_name"]:
        return manifest_index["by_upload_name"][filename]["doc_id"]

    raise KeyError(
        f"Unable to normalize hosted result to canonical doc_id "
        f"(filename={filename!r}, file_id={file_id!r})"
    )


def validate_cases_against_manifest(
    cases: list[dict[str, Any]],
    manifest: dict[str, Any],
) -> None:
    known = set(build_manifest_index(manifest)["by_doc_id"].keys())

    missing_refs: list[tuple[str, str]] = []
    for case in cases:
        for doc_id in case.get("expected_supporting_docs", []):
            if doc_id not in known:
                missing_refs.append((case["id"], doc_id))

    if missing_refs:
        pretty = "\n".join(f"- case={cid} missing doc_id={doc}" for cid, doc in missing_refs)
        raise RuntimeError(
            "cases.jsonl references docs not present in export manifest:\n" + pretty
        )


def validate_retrieved_doc_ids_known(
    retrieved_doc_ids: list[str],
    manifest: dict[str, Any],
) -> None:
    known = set(build_manifest_index(manifest)["by_doc_id"].keys())
    unknown = sorted(set(retrieved_doc_ids) - known)
    if unknown:
        raise RuntimeError(
            "Retriever returned doc_ids not present in manifest:\n- "
            + "\n- ".join(unknown)
        )
