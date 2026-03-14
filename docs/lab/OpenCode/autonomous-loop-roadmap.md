# Autonomous Self-Improvement Loop — Roadmap

> **Goal:** Replace OpenClaw with a transparent, measurable, self-improving system we fully control.
> **Oracle Decision:** 2026-03-14, O1 confidence 0.85

## Where We Are Today

```mermaid
flowchart LR
    subgraph DONE["✅ Working"]
        A["3-Loop<br/>Orchestration<br/><i>main.py</i>"]
        B["Strategic<br/>Planning<br/><i>planner.py</i>"]
        C["Plan Emission<br/><i>.sisyphus/plans/</i>"]
        D["OpenCode<br/>Executor<br/><i>opencode_executor.py</i>"]
        E["Eval Harness<br/><i>evals/knowledge_plane/</i><br/>Score: 0.778"]
        F["Eval Gate<br/><i>run_eval_gate()</i>"]
        G["Vector Search<br/><i>memory.py</i>"]
        H["State Checkpoint<br/><i>state.db.json</i>"]
    end
```

## What We're Building (Oracle Task Graph)

```mermaid
flowchart TD
    T01["<b>T-01</b><br/>Episodic Memory<br/><i>episodic.json</i><br/>🔴 NOT STARTED"]
    T02["<b>T-02</b><br/>Git Keep/Revert<br/><i>auto commit + revert</i><br/>🔴 NOT STARTED"]
    T03["<b>T-03</b><br/>Template Improvement<br/><i>if recall < X, try Y</i><br/>🔴 NOT STARTED"]
    T04["<b>T-04</b><br/>Heuristic Storage<br/><i>heuristics.json</i><br/>🔴 NOT STARTED"]
    T05["<b>T-05</b><br/>Wire Into Loop<br/><i>main.py integration</i><br/>🔴 NOT STARTED"]
    T06["<b>T-06</b><br/>LLM Fallback<br/><i>novel improvements</i><br/>⚪ OPTIONAL"]
    T07["<b>T-07</b><br/>5-Cycle Test<br/><i>unattended run</i><br/>🔴 NOT STARTED"]

    T01 --> T02
    T02 --> T03
    T03 --> T04
    T04 --> T05
    T05 --> T06
    T05 --> T07
```

## The Autonomous Loop (What It Will Do)

```mermaid
flowchart TD
    START(["Start Cycle"]) --> ANALYZE["1. Analyze eval results<br/>Find weakest metric"]
    ANALYZE --> HYPOTHESIS["2. Generate hypothesis<br/>Template or LLM"]
    HYPOTHESIS --> PLAN["3. Emit plan<br/>.sisyphus/plans/*.md"]
    PLAN --> COMMIT["4. Git commit<br/>(snapshot before change)"]
    COMMIT --> EXECUTE["5. OpenCode executes<br/>opencode run --format json"]
    EXECUTE --> EVAL["6. Run eval harness<br/>Compare before/after"]
    EVAL --> DECIDE{Score improved?}
    DECIDE -->|Yes| KEEP["✅ Keep change<br/>Save heuristic"]
    DECIDE -->|No| REVERT["❌ Git revert<br/>Log failure"]
    KEEP --> EPISODIC["7. Update episodic.json"]
    REVERT --> EPISODIC
    EPISODIC --> NEXT{More cycles?}
    NEXT -->|Yes| ANALYZE
    NEXT -->|No| DONE(["Done — report results"])
```

## Memory Architecture (5-Layer, O1 Design)

```mermaid
flowchart LR
    subgraph MEMORY["Memory Hierarchy"]
        direction TB
        L1["🧠 <b>Layer 1: Identity</b><br/>System role, rules<br/><i>state.system_role</i><br/>✅ Permanent"]
        L2["💭 <b>Layer 2: Working</b><br/>Current goal, hypothesis<br/><i>state.current_goal</i><br/>✅ Active session"]
        L3["📓 <b>Layer 3: Episodic</b><br/>What was tried, what happened<br/><i>episodic.json</i><br/>🔴 T-01: Needs persistence"]
        L4["📚 <b>Layer 4: Semantic</b><br/>Learned heuristics<br/><i>heuristics.json + skills.json</i><br/>🔴 T-04: Needs auto-capture"]
        L5["📁 <b>Layer 5: Artifact</b><br/>Files, outputs, logs<br/><i>artifacts/</i><br/>✅ Filesystem"]

        L1 --- L2 --- L3 --- L4 --- L5
    end
```

## Design Decisions (Oracle-Chosen)

| Decision | Choice | Why |
|----------|--------|-----|
| **Memory format** | JSON files | Git-trackable, no deps, matches existing skills.json |
| **Task generation** | Hybrid (templates + LLM) | Templates for known patterns, LLM for novel cases |
| **Keep/revert** | Git-based | Commit before change, revert on regression. Auditable. |
| **Where to build** | Extend `memory.py` | Centralize memory, reuse vector search |
| **First test** | 5 unattended cycles | Enough to see multiple keep/revert decisions |
| **Third-party deps** | None | Self-reliant. No OMO notepad/boulder dependency. |

## Score Progression

```
Baseline:       0.547  ████████████████████████████░░░░░░░░░░░░░░░░
Cycle 1 grader: 0.562  █████████████████████████████░░░░░░░░░░░░░░░
Cycle 2 cite:   0.696  ███████████████████████████████████░░░░░░░░░
Cycle 3 facts:  0.748  █████████████████████████████████████░░░░░░░
Cycle 4 dedup:  0.778  ██████████████████████████████████████░░░░░░
Oracle target:  0.600  ██████████████████████████████░░░░░░░░░░░░░░  ← exceeded
Next target:    0.850  ██████████████████████████████████████████░░
Perfect:        1.000  ██████████████████████████████████████████████
```

## Module Map (Current)

| File | Role | LOC | Status |
|------|------|-----|--------|
| `main.py` | 3-loop orchestration + OpenCode routing | ~300 | ✅ Working |
| `planner.py` | O1 strategic planning + plan emission | ~600 | ✅ Working |
| `opencode_executor.py` | OpenCode JSON event bridge | ~170 | ✅ Working |
| `worker.py` | Stateless task execution | ~65 | ✅ Working |
| `critic.py` | Worker output evaluation | ~90 | ✅ Working |
| `state.py` | 5-layer state + checkpoint | ~120 | ⚠️ Episodic resets |
| `memory.py` | Skills DB + vector search | ~250 | ⚠️ Never auto-called |
| `config.py` | Model routing + thresholds | ~100 | ✅ Working |
| `llm.py` | Unified LLM client | ~150 | ✅ Working |
| `tools.py` | Python exec, shell, file I/O | ~100 | ✅ Working |
| `evals/knowledge_plane/` | Eval harness (10 cases, 4 metrics) | ~900 | ✅ Score: 0.778 |

## Key Files Reference

| Document | What It Is |
|----------|-----------|
| `CANON.md` | Product spec authority — all decisions checked against this |
| `docs/ORIGIN.md` | Design narrative from founding conversation |
| `docs/lab/OpenCode/model-provider-strategy.md` | Provider/model/agent mapping |
| `docs/lab/OpenCode/oracle-autonomous-loop-response.json` | This roadmap's source decision |
| `docs/lab/OpenCode/o3-OpenCode.md` | Original OMO integration decision (B now, D later) |
| `ai-lab/o1_system_prompt.md` | Chief Strategist role definition |

## What "Replace OpenClaw" Means

| OpenClaw Does | Our System Does | Status |
|--------------|----------------|--------|
| Opaque orchestration | Transparent 3-loop engine | ✅ |
| Unknown model routing | Documented model/provider strategy | ✅ |
| No eval feedback | 10-case scored eval harness | ✅ |
| No memory | 5-layer hierarchy (designed) | 🔴 T-01–T-05 |
| No self-improvement | Autonomous loop (designed) | 🔴 T-01–T-07 |
| No keep/revert | Git-based discipline | 🔴 T-02 |
| Can't explain decisions | Oracle queries + responses saved | ✅ |
| Vendor lock-in | Self-reliant, any model, flat rate | ✅ |
