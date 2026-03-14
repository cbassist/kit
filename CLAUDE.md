# CLAUDE.md — Autonomous R&D Lab (01)

A self-improving autonomous engineering system. O1 plans, workers execute, critics evaluate, and the system learns from every experiment. This repo builds and optimizes itself.

## What This Is

Three nested loops that run autonomously:
- **Strategic Loop** (O1) — Plans task graphs, diagnoses failures. Called rarely.
- **Project Loop** (GPT-4o / Gemini) — Evaluates results, manages task queue.
- **Experiment Loop** (OpenCode / Ollama / fast) — Executes tasks via OMO agents or built-in worker.

**Current status:** OpenCode execution pilot validated. 4 self-improvement cycles ran autonomously at $0.00 (flat rate), improving eval score from 0.547 → 0.778 (+42%). Now building the autonomous loop (see roadmap below).

## Quick Start

```bash
cp .env.example .env        # Add your OPENAI_API_KEY
uv sync                     # Install deps
cd ai-lab && uv run main.py "Your goal here"

# With OpenCode executor (routes through OMO agents):
OPENCODE_EXECUTOR=1 OPENCODE_AGENT=sisyphus uv run main.py "Your goal here"
```

## Module Map

| File | Role | Status |
|------|------|--------|
| `ai-lab/main.py` | Three-loop orchestration + OpenCode routing | ✅ |
| `ai-lab/planner.py` | O1 strategic planning + plan emission | ✅ |
| `ai-lab/opencode_executor.py` | OpenCode JSON event bridge | ✅ |
| `ai-lab/llm.py` | Unified LLM client (handles O1 API quirks) | ✅ |
| `ai-lab/critic.py` | Worker output evaluation + scoring | ✅ |
| `ai-lab/worker.py` | Stateless task execution (fast tier) | ✅ |
| `ai-lab/state.py` | 5-layer memory hierarchy, JSON checkpoint/resume | ⚠️ Episodic resets per-run |
| `ai-lab/memory.py` | Skill heuristics DB + vector search (Ollama embeddings) | ⚠️ Never auto-called |
| `ai-lab/config.py` | Model routing, thresholds, env config | ✅ |
| `ai-lab/tools.py` | Deterministic tools: Python exec, shell, file I/O | ✅ |
| `ai-lab/evals/knowledge_plane/` | Eval harness (10 cases, 4 metrics, score: 0.778) | ✅ |

## Key Documents

| Document | Purpose |
|----------|---------|
| `CANON.md` | Product spec authority — all decisions checked against this |
| `docs/ORIGIN.md` | Design narrative distilled from the founding GPT-5.4 conversation |
| `docs/lab/OpenCode/autonomous-loop-roadmap.md` | **Current roadmap** — task graph, diagrams, status |
| `docs/lab/OpenCode/model-provider-strategy.md` | Provider/model/agent mapping |
| `docs/lab/OpenCode/oracle-autonomous-loop-response.json` | O1 decision: autonomous loop implementation plan |
| `ai-lab/o1_system_prompt.md` | Chief Strategist role definition for O1 |
| `docs/lab/architecture.md` | Mermaid diagrams of full system architecture |

## Autonomous Loop Roadmap (Oracle-Ordered)

```
T-01: Persist Episodic Memory     🔴  ← START HERE
  T-02: Git Keep/Revert           🔴
    T-03: Template Improvements    🔴
      T-04: Heuristic Storage      🔴
        T-05: Wire Into Loop       🔴
          T-06: LLM Fallback       ⚪  (optional)
          T-07: 5-Cycle Test       🔴  ← VALIDATION
```

Full details, Mermaid diagrams, and design decisions in `docs/lab/OpenCode/autonomous-loop-roadmap.md`.

## Key Rules

1. **CANON.md is the source of truth** — architecture changes are product-spec changes
2. **O1 questions must include**: objective, state snapshot, constraints, prior attempts, decision question, output schema (Section 18)
3. **State over context** — context windows are disposable; `state.db.json` is durable
4. **Escalation is bounded** — max 5 worker failures → critic escalation → O1 strategic replan
5. **Simplicity constraint** — no feature added unless it improves reliability, observability, or decision quality
6. **Keep docs in sync** — when adding new top-level directories, key files, or documents, update the Module Map and Key Documents above
7. **Self-reliance** — build our own systems. No dependency on third-party state formats (OMO notepads, boulder.json). Can read from them, never depend on them.
8. **No Anthropic API** — use OpenRouter or OpenCode Zen for Claude models. Anthropic direct is slow/unreliable.

## Model Tiers

| Tier | Default Model | Role | Cost |
|------|---------------|------|------|
| STRATEGIC | `o1` | Planning, diagnosis | $$ (rare) |
| PROJECT | `gpt-4o` | Evaluation, routing | $ |
| WORKER | `gpt-4o-mini` | Execution, attempts | ¢ |
| LOCAL_WORKER | Ollama `qwen2.5-coder:14b` | Local execution | $0 |
| OPENCODE | `openai/gpt-5.3-codex` | OMO agents (flat rate) | $0/token |
