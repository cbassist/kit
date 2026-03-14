# PRP: Extract Knowledge Plane Eval Harness

**Goal:** Extract GPT-5.4's 2,691-line eval harness from a markdown document into working Python modules under `ai-lab/evals/knowledge_plane/`.

**Scope:** Code extraction, file organization, import wiring, and validation. No refactoring of logic. No changes to existing `ai-lab/` modules.

**Confidence:** 8/10 — code already exists, task is mechanical extraction with clear module boundaries.

---

## Context

### What This Is

During a model evaluation session, GPT-5.4 was asked about retrieval strategy (local vs hosted). Instead of just answering, it wrote a complete A/B evaluation framework — 2,691 lines of production Python embedded in a markdown file. The code is structured as 7 modules with clear boundaries, but it's trapped in a `.md` file and not executable.

### Why It Matters

This harness is a **general-purpose A/B evaluation instrument**, not just a retrieval test. It isolates one variable, holds everything else constant, and measures end-to-end quality. The lab needs this capability for future experiments.

### Source File

`docs/lab/model-eval/gpt54-q2-platform.md` — 2,691 lines. Contains multiple Python code blocks interspersed with explanation text. The code blocks are the extraction target.

---

## Target Structure

Create these files:

```
ai-lab/
├── evals/
│   ├── __init__.py                          # """Evaluation harnesses."""
│   └── knowledge_plane/
│       ├── __init__.py                      # """Knowledge-plane evaluation harness."""
│       ├── adapters.py                      # Retriever protocol + implementations (~232 lines)
│       ├── normalization.py                 # Doc ID canonicalization (~116 lines)
│       ├── graders.py                       # Deterministic + LLM graders (~132 lines)
│       ├── metrics.py                       # Score aggregation (~61 lines)
│       ├── runner.py                        # Main CLI orchestration (~274 lines)
│       ├── exporters.py                     # Hosted corpus staging (~283 lines)
│       ├── cases.jsonl                      # 10-case benchmark set
│       └── results/                         # Output directory (create empty with .gitkeep)
```

---

## Extraction Tasks (in order)

### Task 1: Read and Map the Source

Read `docs/lab/model-eval/gpt54-q2-platform.md` completely. Identify every Python code block. Map each block to its target module by looking at:
- Module docstrings and comments that name the file
- Class/function definitions that GPT-5.4 labeled
- Import statements that reference sibling modules

**The markdown contains TWO passes of the code:**
1. **First pass (~lines 145-370):** Initial version with simpler adapters
2. **Second pass (~lines 780-1260):** "Hardened" version with normalization, manifest, groundedness grading

**USE THE SECOND (HARDENED) PASS.** It supersedes the first. The first pass is a draft; the second is the production version.

### Task 2: Create Directory Structure

```bash
mkdir -p ai-lab/evals/knowledge_plane/results
touch ai-lab/evals/__init__.py
touch ai-lab/evals/knowledge_plane/__init__.py
touch ai-lab/evals/knowledge_plane/results/.gitkeep
```

### Task 3: Extract `normalization.py`

This module has NO dependencies on other harness modules. Extract first.

**Contains:**
- `canonical_doc_id(path)` — normalizes paths to POSIX repo-relative
- `safe_upload_name(doc_id, sha256_hex)` — deterministic upload filenames
- `manifest_corpus_version(manifest)` — SHA256 of sorted corpus
- `build_manifest_index(manifest)` — lookup tables for manifest
- `normalize_hosted_doc_id(*, filename, file_id, manifest_index)` — reverse mapping
- `validate_cases_against_manifest(cases, manifest)` — pre-flight check
- `validate_retrieved_doc_ids_known(retrieved_doc_ids, manifest)` — groundedness check

**Imports:** stdlib only (`hashlib`, `json`, `re`, `pathlib`, `typing`)

### Task 4: Extract `adapters.py`

**Contains:**
- `RetrievedChunk` dataclass — fields: `doc_id`, `chunk_id`, `text`, `score`, `source`, `metadata`
- `LocalSearchBackend` Protocol — abstract `search(query, top_k)` method
- `LocalRetriever` class — wraps local backend, normalizes to `RetrievedChunk`
- `OpenAIFileSearchRetriever` class — calls `client.responses.create()` with `file_search` tool
- `build_context_pack(chunks)` — formats chunks as markdown context
- `chunks_to_jsonable(chunks)` — serialization helper

**Imports from harness:** `from .normalization import canonical_doc_id, normalize_hosted_doc_id`

### Task 5: Extract `graders.py`

**Contains:**
- `deterministic_retrieval_grade(retrieved_doc_ids, expected_supporting_docs)` — support recall
- `schema_grade(answer_obj)` — validates required output fields
- `evidence_citation_grade(answer_obj, retrieved_doc_ids)` — groundedness check (hardened version)
- `gold_fact_coverage(answer_text, gold_facts)` — substring matching
- `try_parse_json(text)` — safe JSON parsing

**Imports:** stdlib only (`json`, `typing`)

### Task 6: Extract `metrics.py`

**Contains:**
- `aggregate_case_score(support_recall, schema_ok, gold_fact_coverage, citations_ok)` — weighted scoring
  - Weights: 35% retrieval, 25% gold facts, 20% schema, 20% citations
- `summarize_results(rows)` — per-arm aggregation

**Imports:** stdlib only (`typing`)

### Task 7: Extract `runner.py`

This is the main orchestrator. It imports from all other harness modules.

**Contains:**
- `DummyLocalBackend` — stub for scaffold testing
- `load_cases(path)` — reads JSONL
- `load_local_backend(spec)` — dynamic import from `"package.module:ClassName"` format
- `load_json(path)` — manifest loader
- `strategic_prompt(case, context_pack)` — builds reasoning prompt with structured sections
- `answer_with_context(client, model, case, context_pack)` — calls Responses API with JSON mode
- `run_arm(arm, case, client, model, vector_store_id)` — full case evaluation pipeline
- `main()` — CLI entrypoint with argparse

**CLI args:** `--cases`, `--arm` (local|hosted|both), `--model`, `--local-backend`, `--vector-store-id`, `--manifest`

**Imports from harness:**
```python
from .adapters import LocalRetriever, OpenAIFileSearchRetriever, build_context_pack, chunks_to_jsonable
from .graders import deterministic_retrieval_grade, schema_grade, evidence_citation_grade, gold_fact_coverage, try_parse_json
from .metrics import aggregate_case_score, summarize_results
from .normalization import build_manifest_index, validate_cases_against_manifest
```

### Task 8: Extract `exporters.py`

**Contains:**
- `sha256_file(path)` — file hashing
- `expand_patterns(repo_root, patterns)` — glob expansion
- `collect_paths(repo_root, include_code, include_references)` — default corpus patterns
- `create_vector_store(client, name)` — OpenAI vector store creation
- `upload_paths(client, vector_store_id, repo_root, paths)` — batch upload with manifest tracking
- `write_manifest(path, payload)` — manifest output
- `main()` — CLI entrypoint

**Default corpus patterns:**
- Always: `README.md`, `CANON.md`, `CLAUDE.md`, `pyproject.toml`, `docs/lab/**/*.md`, `ai-lab/**/*.md`
- Optional code: `ai-lab/**/*.py`
- Optional references: `references/AutoResearch-mac/**/*.{md,txt,py}`

**Imports from harness:** `from .normalization import canonical_doc_id, safe_upload_name, manifest_corpus_version`

### Task 9: Extract `cases.jsonl`

The 10-case benchmark set is in the markdown around lines 1267-1277. Extract as JSONL (one JSON object per line).

Cases cover 5 buckets:
1. `canon_retrieval` — can the system find CANON.md content?
2. `architecture_adjudication` — can it make architecture decisions from docs?
3. `failure_diagnosis` — can it find escalation policy for failure scenarios?
4. `heuristic_reuse` — can it retrieve design constraints?
5. `runbook_synthesis` — can it synthesize procedures from docs?

### Task 10: Add `__init__.py` files

- `ai-lab/evals/__init__.py`: `"""Evaluation harnesses."""`
- `ai-lab/evals/knowledge_plane/__init__.py`: `"""Knowledge-plane evaluation harness."""`

### Task 11: Validate Imports

Run from `ai-lab/` directory:

```bash
cd ai-lab && python -c "
from evals.knowledge_plane import adapters, graders, metrics, normalization
from evals.knowledge_plane.adapters import RetrievedChunk, LocalRetriever, OpenAIFileSearchRetriever
from evals.knowledge_plane.graders import deterministic_retrieval_grade, schema_grade
from evals.knowledge_plane.metrics import aggregate_case_score, summarize_results
from evals.knowledge_plane.normalization import canonical_doc_id, build_manifest_index
print('All imports OK')
"
```

### Task 12: Validate Runner CLI Help

```bash
cd ai-lab && python -m evals.knowledge_plane.runner --help
```

Should show argparse help with `--cases`, `--arm`, `--model`, etc.

### Task 13: Validate Exporter CLI Help

```bash
cd ai-lab && python -m evals.knowledge_plane.exporters --help
```

Should show argparse help with `--repo-root`, `--name`, etc.

---

## Conventions to Follow

These are observed patterns from the existing `ai-lab/` codebase:

1. **Every module starts with:** `from __future__ import annotations`
2. **Structured data uses dataclasses**, not plain dicts (see `benchmark.py:BenchmarkResult`)
3. **Full type hints** on all function signatures
4. **Module-level docstrings** explaining the file's role
5. **Logging via** `logging.getLogger(__name__)` (not print statements)
6. **`pathlib.Path`** for file paths, not string concatenation
7. **JSON output** indented with 2 spaces

If GPT-5.4's code uses `print()` for status output, convert to `logger.info()` to match existing convention. Keep `print()` only for final user-facing output (results tables).

---

## What NOT to Do

1. **Do NOT refactor the logic.** Extract as-is. The code works as designed.
2. **Do NOT modify existing `ai-lab/` files** (`llm.py`, `config.py`, `memory.py`). The harness is a sidecar.
3. **Do NOT use the first-pass code** from the markdown. Only extract the hardened (second) pass.
4. **Do NOT add new dependencies** to `pyproject.toml`. Everything uses stdlib + `openai` (already installed).
5. **Do NOT create tests** beyond the import validation. The harness IS the test — it evaluates itself via `cases.jsonl`.

---

## Validation Gates

All of these must pass before the task is complete:

```bash
# 1. Directory structure exists
ls ai-lab/evals/knowledge_plane/{__init__,adapters,normalization,graders,metrics,runner,exporters}.py
ls ai-lab/evals/knowledge_plane/cases.jsonl
ls ai-lab/evals/knowledge_plane/results/.gitkeep

# 2. All imports resolve
cd ai-lab && python -c "
from evals.knowledge_plane import adapters, graders, metrics, normalization, runner, exporters
from evals.knowledge_plane.adapters import RetrievedChunk, LocalRetriever, OpenAIFileSearchRetriever, build_context_pack
from evals.knowledge_plane.graders import deterministic_retrieval_grade, schema_grade, evidence_citation_grade, gold_fact_coverage
from evals.knowledge_plane.metrics import aggregate_case_score, summarize_results
from evals.knowledge_plane.normalization import canonical_doc_id, safe_upload_name, build_manifest_index, manifest_corpus_version
print('All imports OK')
"

# 3. Runner CLI responds
cd ai-lab && python -m evals.knowledge_plane.runner --help

# 4. Exporter CLI responds
cd ai-lab && python -m evals.knowledge_plane.exporters --help

# 5. Cases file is valid JSONL
cd ai-lab && python -c "
import json
with open('evals/knowledge_plane/cases.jsonl') as f:
    cases = [json.loads(line) for line in f if line.strip()]
assert len(cases) == 10, f'Expected 10 cases, got {len(cases)}'
for c in cases:
    assert 'id' in c and 'question' in c and 'expected_supporting_docs' in c
print(f'{len(cases)} cases loaded OK')
"

# 6. No syntax errors in any module
cd ai-lab && python -m py_compile evals/knowledge_plane/adapters.py
cd ai-lab && python -m py_compile evals/knowledge_plane/normalization.py
cd ai-lab && python -m py_compile evals/knowledge_plane/graders.py
cd ai-lab && python -m py_compile evals/knowledge_plane/metrics.py
cd ai-lab && python -m py_compile evals/knowledge_plane/runner.py
cd ai-lab && python -m py_compile evals/knowledge_plane/exporters.py
echo "All modules compile OK"
```

---

## Reference Files

Read these to understand existing conventions before extracting:

| File | Why |
|------|-----|
| `docs/lab/model-eval/gpt54-q2-platform.md` | **THE SOURCE** — all code comes from here |
| `ai-lab/benchmark.py` | Closest existing pattern (task suite + scoring + JSON results) |
| `ai-lab/llm.py` | See how the project does LLM client instantiation |
| `ai-lab/config.py` | See how config/env vars are managed |
| `ai-lab/critic.py` | See grading patterns (`CriticVerdict` dataclass) |
| `CANON.md` | Source of truth — the harness evaluates retrieval of THIS document |

---

## Success Criteria

1. All 9 files created in the correct locations
2. All validation gates pass (imports, CLI help, JSONL parsing, compilation)
3. Code is from the **hardened (second) pass** of the markdown, not the initial draft
4. Module docstrings and type hints match existing `ai-lab/` conventions
5. No modifications to any existing files outside `ai-lab/evals/`
