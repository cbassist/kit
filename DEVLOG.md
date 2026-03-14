# 01 Lab — Development Log

Living document tracking what we're building, why, and where we are.
Commit messages have the details — this has the narrative.

---

## Architecture (Oracle-validated 2026-03-13)

O1 was given the objective with zero context about our existing code.
It independently designed the same architecture we already built.
Confidence: 0.85. Full response: `docs/lab/oracle-v2-clean-room-response.json`

```mermaid
flowchart TB
    subgraph STRATEGIC["Strategic Loop — O1/O3 — called rarely"]
        planner["planner.py<br/>v2 12-part contract"]
        sysprompt["o1_system_prompt.md"]
    end

    subgraph PROJECT["Project Loop — task sequencer"]
        main["main.py<br/>3 nested loops"]
        critic["critic.py<br/>scores worker output"]
    end

    subgraph EXPERIMENT["Experiment Loop — fast, continuous"]
        worker["worker.py<br/>stateless execution"]
        tools["tools.py<br/>shell, python, file I/O"]
    end

    subgraph INFRA["Infrastructure"]
        state["state.py — 5-layer memory, JSON checkpoints"]
        memory["memory.py — skills DB + memory actions"]
        llm["llm.py — unified client: O1 + Ollama + API"]
        config["config.py — model routing, thresholds"]
    end

    planner -->|"task graph"| main
    main -->|"dispatch"| worker
    worker -->|"results"| critic
    critic -->|"keep/revert"| main
    critic -->|"5 failures"| planner
    worker --> tools
    worker --> llm
    main --> state
    state --> memory
```

## File Structure

```
01/
├── CANON.md                          # Source of truth (product spec)
├── CLAUDE.md                         # Quick reference for AI assistants
├── README.md                         # Overview + fundamental question
├── DEVLOG.md                         # ← YOU ARE HERE
├── .gitmessage                       # Conventional commit template
│
├── ai-lab/                           # Core engine (~1,700 LOC)
│   ├── main.py                       # Three nested loops (186 LOC)
│   ├── planner.py                    # Strategic planning, v2 contract (447 LOC)
│   ├── worker.py                     # Stateless task execution (65 LOC)
│   ├── critic.py                     # Evaluator / scorer (113 LOC)
│   ├── state.py                      # 5-layer memory, checkpoints (121 LOC)
│   ├── memory.py                     # Skills DB + vector search (247 LOC)
│   ├── llm.py                        # Unified LLM client (185 LOC)
│   ├── config.py                     # Model routing + thresholds (103 LOC)
│   ├── tools.py                      # Deterministic tools (86 LOC)
│   ├── ask_o1.py                     # Direct O1 CLI
│   │
│   ├── o1_system_prompt.md           # Strategist role definition (v2)
│   ├── o1_next_question_v2.md        # 12-part strategic query contract
│   ├── o1_next_question_mvp.md       # v1 contract (preserved for reference)
│   │
│   ├── oracle-v2-clean-room.md       # Clean room Oracle prompt (no bias)
│   ├── oracle-v2-architecture-review.md  # Biased version (unused)
│   │
│   └── goals/
│       └── 001-model-optimization.md # First validation goal
│
├── docs/
│   ├── ORIGIN.md                     # Design narrative (distilled from chat.md)
│   ├── chat.md                       # Original 4,461-line design conversation with GPT-5.4
│   ├── frontierscience-paper (1).pdf # Research paper
│   └── lab/
│       ├── architecture.md           # Mermaid diagrams (aligned to v2 language)
│       ├── o1-strategy-prompt.md     # Full strategy doc with draftbench data
│       ├── o1-o3-deployment-decision.md  # Codex's deployment analysis
│       ├── oracle-v2-clean-room-response.json  # O1's full architecture validation
│       ├── opencode-workflow-research-prompt.md # Deep research prompt for OMO capabilities
│       └── model-eval/
│           ├── README.md             # Scorecard across all models
│           ├── gpt54-q1-protocol.md  # GPT-5.4 on protocol gaps
│           ├── gpt54-q2-platform.md  # GPT-5.4 on platform + full eval harness (2,691 lines)
│           ├── o3-q1-protocol.md     # O3 on protocol gaps + schema delta
│           ├── o3-q2-platform.md     # O3 on platform decision
│           └── codex-q2-platform.md  # Codex on platform decision
│
└── references/
    ├── AutoResearch-mac/
    │   ├── autoresearch-karpathy/    # Original Karpathy autoresearch
    │   ├── autoresearch-mlx/         # MLX fork (trevin-creator)
    │   └── autoresearch-macos/       # macOS fork (miolini)
    └── draftbench/                   # Model pairing optimizer (alexziskind1)
```

## Decision Log

| Date | Decision | Rationale | Source |
|------|----------|-----------|--------|
| 2026-03-13 | Strategic tier is model-agnostic, eval-gated | Don't hardcode O1 — any reasoning model can fill the tier | O3 Q1, GPT-5.4 Q1 |
| 2026-03-13 | Local-first architecture, raw API | pgvector + RRF beats Assistants API for our use case | All 3 models unanimous |
| 2026-03-13 | Claude Code is the orchestrator | Other models are tools it routes to, not competitors | User decision |
| 2026-03-13 | v2 strategic query contract (12-part) | Synthesized best of O3, GPT-5.4, Codex evaluations | docs/lab/model-eval/ |
| 2026-03-13 | Architecture validated by Oracle | O1 clean-room design converged on our existing architecture | oracle-v2-clean-room-response.json |
| 2026-03-13 | Goal 001: model optimization | Known-answer validation — draftbench predicts the outcome | goals/001-model-optimization.md |
| 2026-03-13 | 14B coder is optimal worker model | 24/25 benchmark score, matches draftbench prediction | GOAL_001_REPORT.md |
| 2026-03-13 | Model family > param count | Code-tuned 14B > general 7B; tuned 1B > general 1.5B | Goal 001 full sweep |
| 2026-03-13 | Critic JSON needs robust parsing | gpt-4o wraps JSON in markdown fences; `_extract_json()` added | Bug found during smoke test |
| 2026-03-13 | MLX preferred over Ollama | 8.5 vs 12 GB memory, +16% throughput, native speculative decoding | MLX benchmark |
| 2026-03-13 | Speculative decoding scales with output length | +14% on short tasks, +124% on sustained generation | MLX benchmark |
| 2026-03-13 | Goal 001 V-Model complete | Architecture validated end-to-end, all predictions confirmed | GOAL_001_REPORT.md |
| 2026-03-14 | Local vector search beats hosted retrieval | Ollama nomic-embed-text: local 0.562 vs hosted 0.547 on 10-case eval | eval harness A/B run |
| 2026-03-14 | OMO integration: B now, D later | O1 chose B (plans only), O3 chose D (plans + Ralph). GPT-5.4 adjudicated: B first for control, promote to D after Ralph hooks proven | docs/lab/OpenCode/ |
| 2026-03-14 | Ralph promotion gate defined | Ralph may own optimization only after eval-hook gating is proven on a bounded task family | GPT-5.4 adjudication |
| 2026-03-14 | Strip per-file LOC from docs | LOC counts go stale; use aggregates only. Added Key Rule #6: keep docs in sync | Maintenance decision |

## Current Status

### What's Built (all committed, all pushed)
- [x] Three nested loops (strategic → project → experiment)
- [x] v2 strategic query contract (12-part, with confidence threshold)
- [x] Upgraded system prompt (uncertainty contract, pre-mortem, adjudicator role)
- [x] Memory actions (strategist → skills DB feedback loop)
- [x] Unified LLM client (O1/O3 + Ollama + standard API)
- [x] State checkpointing with resume
- [x] Conventional commit hook
- [x] Oracle architecture validation
- [x] Goal 001 defined

### What's Next
- [x] Build the 5-task benchmark suite for quality scoring → `benchmark.py`
- [x] Build Goal 001 runner → `run_goal_001.py`
- [x] Reboot, launch Terminal-only, run smoke test
- [x] Pull missing Ollama models (qwen2.5:1.5b, qwen2.5:7b)
- [x] Run full sweep and validate convergence against draftbench predictions
- [x] Fix critic JSON parsing bug (markdown fences) → `_extract_json()`
- [x] Write GOAL_001_REPORT.md with expected vs actual analysis

### Goal 001 Results (2026-03-13)

| Model | Score | Time | Rank |
|-------|-------|------|------|
| qwen2.5-coder:14b-instruct-q6_K | 24/25 | 50.5s | 1st |
| qwen2.5:7b | 19/25 | 81.3s | 2nd |
| llama3.2:1b | 16/25 | 16.1s | 3rd |
| qwen2.5:1.5b | 11/25 | 46.0s | 4th |

**Winner:** 14B coder — matches draftbench prediction.
**Full report:** `ai-lab/goal_001_results/GOAL_001_REPORT.md`

### MLX Speculative Decoding Results (2026-03-13)

| Config | Score | TPS | Memory | Speedup |
|--------|-------|-----|--------|---------|
| 14B baseline (MLX) | 21/25 | 29.1 | 8.5 GB | — |
| 14B + 1.5B draft | 20/25 | 33.1 | 9.5 GB | +14% (short), +124% (warmup) |

MLX confirmed as preferred runtime. Speculative decoding validated — gains scale with output length.

### Knowledge Plane Eval Results (2026-03-14)

| Arm | Avg Score | Notes |
|-----|-----------|-------|
| Local (stub) | 0.465 | DummyLocalBackend — single stub result per query |
| Hosted (OpenAI file_search) | 0.554 | Real vector store, 20 repo docs uploaded |
| **Delta** | **+0.089** | Hosted wins 6/10 cases, loses on arch_* cases |

Per-case breakdown:
- Biggest hosted wins: `failure_001` (+0.38), `canon_002` (+0.23), `heuristic_002` (+0.17)
- Hosted losses: `arch_002` (-0.18), `arch_001` (-0.06) — multi-doc reasoning may dilute signal
- Full results: `ai-lab/evals/knowledge_plane/results/latest.json`

Bugs fixed during first run:
- `DEFAULT_REPO_ROOT` was `parents[3]` (wrong depth) → fixed to `parents[2]`
- OpenAI file_search rejects `.example` and `.toml` extensions → added `.txt` fallback in `safe_upload_name`

### Vector Search Results (2026-03-14)

| Backend | Avg Score | vs Stub |
|---------|-----------|---------|
| Stub local (DummyLocalBackend) | 0.465 | — |
| Hosted (OpenAI file_search) | 0.547 | +0.082 |
| **Vector local (Ollama nomic-embed-text)** | **0.562** | **+0.097** |

Local vector retrieval beats hosted on 7/10 cases at zero API cost.
Biggest local wins: `arch_001` (0.55 vs 0.44), `arch_002` (0.55 vs 0.20) — multi-doc reasoning cases.
Backend: `evals/knowledge_plane/local_backend.py` using `RepoSearchBackend`.

### On Deck
- [x] Extract GPT-5.4's eval harness into `ai-lab/evals/knowledge_plane/`
- [x] Build the A/B retrieval comparison (local vs hosted)
- [x] Add vector search to skills DB / local retrieval backend
- [x] Deep research: OpenCode + OMO workflow capabilities
- [x] Oracle consultation: O1 + O3 + GPT-5.4 adjudication → "B now, D later"
- [x] **T-01**: Prototype `.sisyphus/plans/*.md` generation from `planner.py`
- [x] **T-02**: Add eval-gated loop hook in `main.py` (Python owns stop/continue)
- [x] **T-03**: Plan→Execute→Evaluate integration test (all 3 subtests pass)
- [ ] **OpenCode execution pilot**: Run a generated plan through `opencode run`, capture structured output
- [ ] **Ralph promotion pilot**: Single Ralph Loop with eval-hook gating on bounded task
- [ ] Figma diagrams: 3 FigJam boards generated, need to claim/verify in Figma workspace
- [ ] Observability / telemetry beyond logging

## V-Model Progress

```
30,000 ft ─── Oracle validates architecture ✅
              │
20,000 ft ─── Goal 001 defined, tools identified ✅
              │
10,000 ft ─── Wire draftbench, build benchmark suite ✅
              │
Ground    ─── Run end-to-end, observe convergence ✅
              │
10,000 ft ─── Validate results against predictions ✅
              │
20,000 ft ─── Extract learnings, update heuristics ✅  ◄── COMPLETED
              │
30,000 ft ─── Architecture confirmed ✅
```

## Model Evaluation Archive

Three OpenAI models (O3, GPT-5.4, Codex) were asked the same two questions.
Full responses in `docs/lab/model-eval/`. Summary:

| Model | Q1 (Protocol) | Q2 (Platform) | Notable |
|-------|---------------|---------------|---------|
| O3 | Drop-in schema delta | Tables + decision flow | Best operational answers |
| GPT-5.4 | Best essay, 5 archetypes | Full eval harness (2,691 lines) | Self-promoted as O1 replacement |
| Codex | Clean reframe | Direct "95%, skip it" | Most concise |
