from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Iterable

from openai import OpenAI

from .normalization import canonical_doc_id, manifest_corpus_version, safe_upload_name


HERE = Path(__file__).resolve().parent
RESULTS_DIR = HERE / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_REPO_ROOT = HERE.parents[3]

DEFAULT_PATTERNS = [
    "README.md",
    "CANON.md",
    "CLAUDE.md",
    ".env.example",
    "pyproject.toml",
    "requirements.txt",
    "docs/lab/**/*.md",
    "ai-lab/**/*.md",
]

OPTIONAL_CODE_PATTERNS = [
    "ai-lab/**/*.py",
]

OPTIONAL_REFERENCE_PATTERNS = [
    "references/AutoResearch-mac/**/*.md",
    "references/AutoResearch-mac/**/*.txt",
    "references/AutoResearch-mac/**/*.py",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def expand_patterns(repo_root: Path, patterns: list[str]) -> list[Path]:
    seen: set[Path] = set()
    out: list[Path] = []

    for pattern in patterns:
        for path in repo_root.glob(pattern):
            if not path.is_file():
                continue
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            out.append(path)

    return sorted(out, key=lambda p: str(p.relative_to(repo_root)))


def collect_paths(
    repo_root: Path,
    include_code: bool = False,
    include_references: bool = False,
) -> list[Path]:
    patterns = list(DEFAULT_PATTERNS)
    if include_code:
        patterns.extend(OPTIONAL_CODE_PATTERNS)
    if include_references:
        patterns.extend(OPTIONAL_REFERENCE_PATTERNS)
    return expand_patterns(repo_root, patterns)


def create_vector_store(client: OpenAI, name: str) -> str:
    vs = client.vector_stores.create(name=name)
    return vs.id


def write_manifest(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def upload_paths(
    client: OpenAI,
    vector_store_id: str,
    repo_root: Path,
    paths: Iterable[Path],
) -> list[dict]:
    manifest_entries: list[dict] = []

    with tempfile.TemporaryDirectory(prefix="kp_export_") as tmp:
        tmpdir = Path(tmp)

        for idx, path in enumerate(paths, start=1):
            doc_id = canonical_doc_id(path.relative_to(repo_root))
            sha256_hex = sha256_file(path)
            upload_name = safe_upload_name(doc_id, sha256_hex)
            staged_path = tmpdir / upload_name
            shutil.copy2(path, staged_path)

            print(f"[{idx}] Uploading {doc_id} as {upload_name} ...")
            with staged_path.open("rb") as f:
                vs_file = client.vector_stores.files.upload_and_poll(
                    vector_store_id=vector_store_id,
                    file=f,
                )

            entry = {
                "doc_id": doc_id,
                "path": doc_id,
                "upload_name": upload_name,
                "bytes": path.stat().st_size,
                "sha256": sha256_hex,
                "vector_store_file_id": getattr(vs_file, "id", None),
                "file_id": getattr(vs_file, "file_id", None),
                "status": getattr(vs_file, "status", None),
            }
            manifest_entries.append(entry)

    return manifest_entries


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export repo docs into an OpenAI vector store for knowledge-plane evals."
    )
    parser.add_argument("--repo-root", default=str(DEFAULT_REPO_ROOT))
    parser.add_argument("--vector-store-id", default=None)
    parser.add_argument("--name", default=None)
    parser.add_argument("--include-code", action="store_true")
    parser.add_argument("--include-references", action="store_true")
    parser.add_argument(
        "--manifest-out",
        default=str(RESULTS_DIR / "export_manifest.json"),
    )
    args = parser.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required.")

    repo_root = Path(args.repo_root).resolve()
    if not repo_root.exists():
        raise RuntimeError(f"Repo root does not exist: {repo_root}")

    paths = collect_paths(
        repo_root=repo_root,
        include_code=args.include_code,
        include_references=args.include_references,
    )
    if not paths:
        raise RuntimeError("No files matched the export patterns.")

    client = OpenAI(api_key=api_key)

    vector_store_id = args.vector_store_id
    created_new_store = False
    if not vector_store_id:
        name = args.name or f"knowledge-plane-eval-{time.strftime('%Y%m%d-%H%M%S')}"
        vector_store_id = create_vector_store(client, name)
        created_new_store = True

    files = upload_paths(
        client=client,
        vector_store_id=vector_store_id,
        repo_root=repo_root,
        paths=paths,
    )

    payload = {
        "repo_root": str(repo_root),
        "vector_store_id": vector_store_id,
        "created_new_store": created_new_store,
        "file_count": len(files),
        "include_code": args.include_code,
        "include_references": args.include_references,
        "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "files": files,
    }
    payload["corpus_version"] = manifest_corpus_version(payload)

    manifest_path = Path(args.manifest_out).resolve()
    write_manifest(manifest_path, payload)

    print("\nDone.")
    print(f"Vector store:    {vector_store_id}")
    print(f"Corpus version:  {payload['corpus_version']}")
    print(f"Manifest:        {manifest_path}")
    print(f"export OPENAI_VECTOR_STORE_ID={vector_store_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
