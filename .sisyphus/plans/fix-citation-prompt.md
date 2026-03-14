# Fix prompt template so model cites doc_id values instead of numeric indices

## TL;DR
> **Summary**: Execute task graph for: Fix prompt template so model cites doc_id values instead of numeric indices
> **Deliverables**: 1 tasks
> **Parallel**: YES - all independent
> **Critical Path**: fix-citation-prompt

## Context
### Original Request
Goal: Fix prompt template so model cites doc_id values instead of numeric indices

### Constraints
- Only modify runner.py — do not change graders.py, metrics.py, or adapters.py
- Only modify the strategic_prompt() function
- Keep the JSON schema structure the same — only add clarifying text

## Tasks

> EVERY task MUST have: Agent Profile + Parallelization + Acceptance Criteria.

- [ ] 1. Update strategic_prompt to instruct model to cite doc_id values

  **What to do**: In ai-lab/evals/knowledge_plane/runner.py, the strategic_prompt() function shows retrieved evidence as [1] doc_id=CANON.md ... but the output schema just says "key_evidence_ids": ["string"]. The model interprets this as numeric indices and outputs ["1", "2", "3"] instead of ["CANON.md", "arch.md"]. Fix the Required Output Schema section to explicitly instruct the model to use the doc_id values from the retrieved evidence, not the bracket indices. Example instruction: "key_evidence_ids must contain doc_id values from the Retrieved Evidence section (e.g. CANON.md), NOT numeric indices."
  **Must NOT do**: Do not modify files outside the task scope.

  **Recommended Agent Profile**:
  - Category: `writing`

  **Parallelization**: Can Parallel: YES | Wave 1

  **Acceptance Criteria**:
  - [ ] Task completes without errors

  **Commit**: YES | Message: `feat(lab): update strategic_prompt to instruct model to cite doc_id values`

## Final Verification Wave

- [ ] F1. Plan Compliance Audit — oracle
- [ ] F2. Code Quality Review — unspecified-high

## Commit Strategy
One commit per task. Conventional commit format.

## Success Criteria
All tasks pass acceptance criteria. Eval harness score ≥ baseline (0.562).