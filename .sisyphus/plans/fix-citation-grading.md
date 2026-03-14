# Improve eval harness citation grading to handle chunk-level IDs

## TL;DR
> **Summary**: Execute task graph for: Improve eval harness citation grading to handle chunk-level IDs
> **Deliverables**: 1 tasks
> **Parallel**: YES - all independent
> **Critical Path**: fix-citation-grading

## Context
### Original Request
Goal: Improve eval harness citation grading to handle chunk-level IDs

### Constraints
- Only modify graders.py — do not change metrics.py, runner.py, or test cases
- Do not change the function signature of evidence_citation_grade
- Bare numeric citations (e.g. "1", "3") must still be flagged as invalid
- Add a brief inline comment explaining the prefix match logic

## Tasks

> EVERY task MUST have: Agent Profile + Parallelization + Acceptance Criteria.

- [ ] 1. Fix citation ID matching in evidence_citation_grade

  **What to do**: In ai-lab/evals/knowledge_plane/graders.py, the evidence_citation_grade() function does exact string matching between cited doc IDs and retrieved doc IDs. Models cite chunk-level IDs like "CANON.md::chunk-0" but the retriever returns doc-level IDs like "CANON.md". Fix the matching so that a citation is valid if it starts with any retrieved doc ID (prefix match). For example, "CANON.md::chunk-0" should match against "CANON.md" in the retrieved set. Also handle the case where models cite bare numeric IDs like "1" or "3" — these are invalid and should remain flagged.
  **Must NOT do**: Do not modify files outside the task scope.

  **Recommended Agent Profile**:
  - Category: `writing`

  **Parallelization**: Can Parallel: YES | Wave 1

  **Acceptance Criteria**:
  - [ ] Task completes without errors

  **Commit**: YES | Message: `feat(lab): fix citation id matching in evidence_citation_grade`

## Final Verification Wave

- [ ] F1. Plan Compliance Audit — oracle
- [ ] F2. Code Quality Review — unspecified-high

## Commit Strategy
One commit per task. Conventional commit format.

## Success Criteria
All tasks pass acceptance criteria. Eval harness score ≥ baseline (0.562).