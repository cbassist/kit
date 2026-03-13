# Autonomous Self-Improvement Lab — Architecture

## 1. System Overview — The Three Layers

```mermaid
graph TB
    subgraph Orchestrator["ORCHESTRATOR (Shizzle)"]
        direction LR
        O1[Delegates only — never executes]
        O2[Surfaces: Telegram / CLI / Cron]
    end

    subgraph Loops["IMPROVEMENT LOOPS"]
        direction LR
        L1[Generic try → measure → keep/revert]
        L2[Chainable for any goal]
    end

    subgraph Tools["TOOL LAYER"]
        direction LR
        T1[OpenCode fork-terminal]
        T2[Ollama local LLMs]
        T3[Codex / Gemini workers]
    end

    subgraph Foundation["FOUNDATION"]
        direction LR
        F1[Apple M4 Pro — 24GB unified]
        F2[State + Memory + Traces]
        F3[Postgres + pgvector + FTS]
    end

    Orchestrator --> Loops
    Loops --> Tools
    Tools --> Foundation
```

## 2. Improvement Loop (Generic)

The core loop follows the autoresearch discipline: every experiment is a discrete, measurable unit with an explicit keep/revert decision.

```mermaid
stateDiagram-v2
    [*] --> IDLE

    IDLE --> PLAN: new goal or escalation
    PLAN --> EXPERIMENT: task graph ready

    EXPERIMENT --> EVALUATE: run complete
    EVALUATE --> APPLY: metric improved → keep
    EVALUATE --> EXPERIMENT: metric flat/worse → revert + try next
    EVALUATE --> PLAN: 5 consecutive failures → escalate

    APPLY --> IDLE: checkpoint saved

    note right of PLAN
        Strategic tier (O1 / O3 / any reasoning model)
        Called rarely — only on new goals
        or after repeated failure
        v2 query contract required
    end note

    note right of EXPERIMENT
        Ollama / OpenCode (fast tier)
        Continuous — runs autonomously
        Modify → commit → run → measure
    end note

    note right of EVALUATE
        Gemini (medium tier)
        Per-experiment judgment
        Binary: improved or not
    end note
```

### Loop Invariants

1. **Every experiment is atomic** — committed before running, reverted on failure
2. **Metrics are the only truth** — no subjective "looks better"
3. **Memory prevents repetition** — query past results before starting
4. **Escalation is bounded** — max 5 failures before strategic replanning
5. **State survives crashes** — checkpointed between every iteration

## 3. Memory & State System

```mermaid
graph TB
    subgraph Memory["LAYERED MEMORY"]
        direction TB
        WM[Working Memory<br/>Current goal, hypothesis, design]
        EM[Episodic Memory<br/>Recent experiments + outcomes]
        SM[Semantic Memory<br/>Heuristics + constraints learned]
        AM[Artifact Memory<br/>Filesystem — code, configs, logs]
    end

    subgraph State["STATE PERSISTENCE"]
        direction TB
        CP[Checkpoints<br/>JSON snapshots between iterations]
        GIT[Git Branch<br/>Branch tip = best known config]
        PG[Postgres<br/>session_traces + memory_bank]
    end

    subgraph Dedup["DEDUPLICATION"]
        direction TB
        QP[Query past results before experimenting]
        HS[Hybrid search: pgvector + FTS + RRF]
        SK[Skip if similar experiment failed recently]
    end

    Memory --> State
    State --> Dedup
    Dedup -->|inform| Memory
```

### Existing ai-lab/ Infrastructure

| Module | LOC | What It Does |
|--------|-----|-------------|
| `ai-lab/llm.py` | ~130 | Unified LLM client with transparent O1/O3 API quirk handling |
| `ai-lab/config.py` | ~101 | Model routing, safety thresholds, env config |
| `ai-lab/main.py` | ~186 | Three nested loops: strategic → project → experiment |
| `ai-lab/planner.py` | ~323 | O1 strategic planning + failure diagnosis |
| `ai-lab/critic.py` | ~113 | Critic/evaluator — rates worker output, suggests improvements |
| `ai-lab/worker.py` | ~65 | Stateless task execution (fast tier) |
| `ai-lab/state.py` | ~121 | 5-layer memory hierarchy, JSON serialization, resume support |
| `ai-lab/memory.py` | ~95 | Persistent skill heuristics + artifact registry |
| `ai-lab/tools.py` | ~86 | Deterministic tools: Python exec, shell, file I/O |

**Total: ~1,169 LOC of working infrastructure (+ ~400 LOC of strategy docs).**

### LangGraph vs Custom — Side-by-Side

This comparison is presented honestly for O1 to evaluate.

| Factor | LangGraph | Custom (extend aos/) |
|--------|-----------|---------------------|
| **Time to implement** | Days (turnkey graph execution) | Already built — `main.py` has all 3 loops |
| **State checkpointing** | Built-in (SQLite/Postgres backends) | `state.py` — JSON snapshots with resume (working) |
| **Graph-based routing** | Native nodes + edges + conditional branching | Manual controller loop in `main.py` (working) |
| **Memory integration** | LangGraph + LangMem library | `memory.py` skills DB + artifact registry (working) |
| **Embedding/retrieval** | Needs external setup | JSON tag-based now; can add vector search later |
| **Model routing** | LangChain model abstraction | `llm.py` + `config.py` 3-tier with O1 quirks handled |
| **Dependency weight** | Heavy — pulls langchain-core, langgraph, langsmith | 2 deps (openai, python-dotenv) |
| **Flexibility** | Framework-constrained, opinionated patterns | Full control over loop behavior |
| **Apple Silicon optimization** | Unknown — CUDA-focused ecosystem | Full control over Ollama/MLX integration |
| **Observability** | LangSmith (paid) or custom callbacks | Logging + state.db.json checkpoints (working, free) |
| **Community/docs** | Large, mature, many examples | Just us (but code is simple) |
| **Bloat risk** | High — LangChain transitive deps | Low — we own every line |
| **Upgrade risk** | API churn (LangChain ecosystem moves fast) | Stable — we control the interface |

**Key question for O1:** Given that ai-lab/ already provides a working three-loop orchestration, O1 API handling, state checkpointing, and escalation — is the incremental value of LangGraph's graph execution engine worth the dependency weight and loss of control?

## 4. Agent Topology

```mermaid
graph TB
    Shizzle[Shizzle<br/>Orchestrator<br/>Delegates only]

    Shizzle --> Heartbeat[Heartbeat Agent<br/>Monitoring + cron<br/>Health checks]
    Shizzle --> Lab[Lab Controller<br/>Improvement loops<br/>State management]
    Shizzle --> Fork[Fork Terminal<br/>OpenCode workflows<br/>Code execution]

    Lab --> Planner[Strategic Planner<br/>Strategic tier · eval-gated<br/>Called rarely]
    Lab --> Critic[Critic / Evaluator<br/>Gemini medium<br/>Per-experiment]
    Lab --> Workers[Workers<br/>Ollama / OpenCode fast<br/>Continuous]

    Planner -.->|task graph| Lab
    Workers -.->|results| Critic
    Critic -.->|keep/revert| Lab
    Critic -.->|5 failures| Planner

    style Shizzle fill:#1a1a2e,stroke:#e94560,color:#fff
    style Lab fill:#16213e,stroke:#0f3460,color:#fff
    style Planner fill:#533483,stroke:#e94560,color:#fff
    style Critic fill:#0f3460,stroke:#e94560,color:#fff
    style Workers fill:#1a1a2e,stroke:#0f3460,color:#fff
```

### Model Tier Mapping

| Role | Model | Tier | Cost | When Called |
|------|-------|------|------|-------------|
| Strategic Planner | O1 / O3 / reasoning model (eval-gated) | heavy | $$ | New goals, escalations only |
| Critic / Evaluator | Gemini 2.5 Flash | medium | ~$0.001/call | Every experiment |
| Worker / Executor | Ollama (llama3.3:70b on M4 Pro) | fast | $0 | Continuous |
| Orchestrator | Claude Code (Max sub) | heavy | $0 (subscription) | Delegation, execution, tool routing |

## 5. Optimization Sequence

The improvement loop optimizes the system in layers, where each layer multiplies the effectiveness of the next.

```mermaid
graph TB
    L1[Layer 1: LLM Models<br/>Which models run best on M4 Pro 24GB?<br/>Quantization, context windows, throughput]
    L2[Layer 2: Tools<br/>Fork-terminal, OpenCode workflows<br/>Better tools = better experiments]
    L3[Layer 3: Loop Chains<br/>Combine loops for complex goals<br/>Model optimization → tool optimization → ...]
    L4[Layer 4: Orchestrator Tuning<br/>Shizzle prompt, routing logic<br/>Better delegation = better everything]

    L1 -->|multiplier effect| L2
    L2 -->|better tools| L3
    L3 -->|compound improvement| L4

    style L1 fill:#e94560,stroke:#1a1a2e,color:#fff
    style L2 fill:#0f3460,stroke:#1a1a2e,color:#fff
    style L3 fill:#533483,stroke:#1a1a2e,color:#fff
    style L4 fill:#16213e,stroke:#e94560,color:#fff
```

### Layer 1 Details: LLM Model Optimization

This is the foundation — everything else depends on fast, capable local models.

| Question | Why It Matters |
|----------|---------------|
| Which Ollama models fit in 24GB? | Memory ceiling determines model size |
| Quantization tradeoffs (Q4 vs Q5 vs Q8)? | Speed vs quality vs memory |
| Optimal context window for each role? | Workers need less context than planners |
| MLX vs Ollama for specific tasks? | MLX may be faster for some workloads |
| Can we run 2 models simultaneously? | Parallel worker + critic without swapping |

### Compound Improvement Example

```
Loop 1: Optimize local model selection
  → Find that Q5_K_M llama3.3 gives best speed/quality on M4 Pro
  → 40% faster inference for workers

Loop 2: Optimize fork-terminal workflows (using faster workers)
  → Discover parallel execution pattern
  → 3x throughput on multi-file changes

Loop 3: Chain loops 1+2 for codebase refactoring goal
  → Fast models + parallel execution = autonomous refactoring
  → What took 2 hours now takes 20 minutes
```

## 6. Autoresearch Pattern (Reference)

The autoresearch discipline we're abstracting:

```mermaid
sequenceDiagram
    participant R as Researcher (Agent)
    participant C as Code (train.py)
    participant G as Git Branch
    participant M as Metric (val_bpb)

    R->>C: Modify with experimental idea
    R->>G: git commit -m "experiment: description"
    R->>C: uv run train.py > run.log
    C->>M: Run produces val_bpb

    alt Metric Improved
        R->>G: Keep commit (advance branch)
        R->>R: Log result as "keep" in results.tsv
    else Metric Worse or Equal
        R->>G: git reset --hard (revert to last keep)
        R->>R: Log result as "discard"
    else Crash
        R->>R: Quick fix attempt (if trivial)
        R->>G: git reset --hard (if can't fix)
        R->>R: Log result as "crash"
    end

    R->>R: Loop forever (autonomous)
```

**Key properties we preserve in our generic loop:**
1. Git branch as state management (branch tip = best known config)
2. Fixed evaluation metric (no subjective judgment)
3. Atomic experiments (commit before run, revert on failure)
4. Autonomous operation (never stop to ask — loop until interrupted)
5. Results logging (TSV/structured log of all attempts)
