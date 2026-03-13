# 01 — Autonomous Self-Improvement Lab

> **The Fundamental Question (for GPT-5.4, Codex, and all reviewers):**
>
> *Are we properly referencing, leveraging, and utilizing the unique capabilities of the O1 reasoning model?*
>
> This repo uses O1 as its strategic reasoning tier — called rarely but with precision for planning and failure diagnosis. The ABC hybrid question: given three AutoResearch implementations (Karpathy's original, MLX fork, macOS fork) in `references/AutoResearch-mac/`, what is the optimal way to harness O1's extended chain-of-thought reasoning for autonomous self-improvement?
>
> **O1 vs O1 Pro:** O1 Pro is not just faster — it applies more inference-time compute, scoring ~12 points higher on AIME and ~9 points higher on GPQA Diamond. However, O1 with `reasoning_effort: high` reaches ~80-85% of O1 Pro's quality at 4x lower cost with full API access. O1 Pro remains largely a ChatGPT Pro ($200/mo) feature with limited API availability. O3 may have superseded O1 Pro's niche entirely. Our current stance: **O1 with `reasoning_effort: high` is sufficient** — no hurry, quality over speed, and the cost difference at our low call volume is negligible.

A self-improving autonomous R&D system. O1 plans the strategy, workers execute experiments, critics evaluate results, and the system learns from every iteration. The lab builds and optimizes itself.

## How It Works

Three nested loops run autonomously against any goal:

```
┌─ STRATEGIC LOOP (heavy reasoning — e.g. O1) ─────────────────┐
│  Called rarely — new goals and failure diagnosis only.        │
│                                                              │
│  ┌─ PROJECT LOOP (medium tier — critic/evaluator) ────────┐  │
│  │  Evaluates results. Manages the task queue.             │  │
│  │                                                         │  │
│  │  ┌─ EXPERIMENT LOOP (fast tier — local or cheap) ────┐  │  │
│  │  │  Worker tries → Critic scores → Retry or escalate  │  │  │
│  │  └───────────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

Model selection for each tier is a key decision the lab optimizes. Defaults are configured in `.env` but the system is designed to evaluate and improve its own model choices.

The core discipline comes from [autoresearch](https://github.com/karpathy/autoresearch): every experiment is atomic, metrics are the only truth, and failures are reverted cleanly.

## Quick Start

```bash
# 1. Install dependencies
uv sync

# 2. Configure
cp .env.example .env
# Edit .env — at minimum set OPENAI_API_KEY

# 3. Run the lab on a goal
cd ai-lab
uv run main.py "Optimize local LLM inference on Apple Silicon"

# Or ask O1 a strategic question directly
uv run ask_o1.py "What is the optimal quantization for llama3.3 on M4 Pro 24GB?"

# Or submit a full strategy document
uv run ask_o1.py --file ../docs/lab/o1-strategy-prompt.md
```

## Model Tiers

The system routes to three tiers based on task complexity, not specific models. Which model fills each tier is itself an optimization target.

| Tier | Current Default | Role | Cost |
|------|-----------------|------|------|
| **Strategic** | `o1` | Planning, failure diagnosis | $$ (called rarely) |
| **Project** | `gpt-4o` | Evaluation, task routing | $ |
| **Worker** | `gpt-4o-mini` | Task execution, 100s of attempts | cents |
| **Local** | Ollama `llama3.3:70b` | $0 execution on Apple Silicon | free |

These are starting defaults. One of the lab's first self-improvement goals is to determine optimal model selection for each tier given the hardware constraints. `llm.call()` handles O1 API quirks, Ollama local routing, and standard OpenAI calls behind a single interface — swapping models is a config change, not a code change.

## Project Structure

```
01/
├── CANON.md                    # Product spec authority (source of truth)
├── CLAUDE.md                   # Quick reference for AI assistants
├── .env.example                # All configuration options
│
├── ai-lab/                     # Core engine (~1,300 LOC)
│   ├── main.py                 # Three-loop orchestration
│   ├── planner.py              # O1 strategic planning + failure diagnosis
│   ├── llm.py                  # Unified LLM client (O1 + Ollama + standard)
│   ├── critic.py               # Worker output evaluation + scoring
│   ├── worker.py               # Stateless task execution
│   ├── state.py                # 5-layer memory hierarchy + checkpointing
│   ├── memory.py               # Skill heuristics DB + artifact registry
│   ├── config.py               # Model routing + safety thresholds
│   ├── tools.py                # Deterministic tools (Python, shell, file I/O)
│   ├── ask_o1.py               # Direct O1 CLI for strategic queries
│   ├── o1_system_prompt.md     # Chief Strategist role definition
│   └── o1_next_question_mvp.md # Template for structured O1 queries
│
└── docs/lab/                   # Architecture & strategy
    ├── architecture.md         # Mermaid diagrams of full system
    └── o1-strategy-prompt.md   # Structured O1 decision document
```

## Configuration

All settings live in `.env` (copy from `.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | *(required)* | Your OpenAI API key |
| `STRATEGIC_MODEL` | `o1` | Model for planning/diagnosis |
| `PROJECT_MODEL` | `gpt-4o` | Model for evaluation/routing |
| `WORKER_MODEL` | `gpt-4o-mini` | Model for execution |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Local Ollama instance |
| `LOCAL_WORKER_MODEL` | `llama3.3:70b` | Ollama model for local execution |
| `O1_REASONING_EFFORT` | `high` | O1 reasoning depth: low/medium/high |
| `ESCALATE_THRESHOLD` | `5` | Worker failures before O1 escalation |
| `MAX_PROJECT_ITERATIONS` | `200` | Hard safety cap on loop iterations |

## Key Concepts

### The Canon

[`CANON.md`](CANON.md) is the product specification authority. All architecture, prompt, model-role, and state schema changes are product-spec changes. Major decisions go through the O1-in-the-loop spec cycle (CANON Section 16).

### Asking the Strategic Tier the Right Questions

The strategic tier (O1, O3, or any reasoning model) is called rarely but with precision. Every query follows the **v2 Strategic Query Contract** (`ai-lab/o1_next_question_v2.md`), a 12-part protocol synthesized from O3, GPT-5.4, and Codex evaluations:

1. **Meta** — caller type, confidence threshold, budget envelope
2. **Objective** and explicit success metric
3. **Current state snapshot** (structured, not narrative)
4. **Constraints** with blast radius (patch | refactor | rewrite)
5. **Prior attempts** and failure signatures with categories
6. **Explicit option set** — named alternatives to adjudicate, never open-ended "what's optimal?"
7. **Assumptions & unknowns** — what we believe but haven't verified, what's missing
8. **Decision question** — precise, bounded, against named options
9. **Required output** — strategy, rejected alternatives, risk forecast, smallest validating experiment, kill criteria, memory actions, verification conditions

Key principle: **if confidence is below threshold, output an experiment, not a plan.** Uncertainty contracts beat confident plans built on shaky premises.

See also: `ai-lab/o1_system_prompt.md` for the full strategist role definition, and `docs/lab/model-eval/` for the source evaluations.

### State Over Context

Context windows are disposable. State is durable. The `SystemState` object in `state.py` implements a 5-layer memory hierarchy:

- **Identity** — system role (permanent)
- **Working** — current goal, hypothesis, design (active)
- **Episodic** — recent experiments and outcomes (rolling)
- **Semantic** — learned heuristics from past runs (persistent)
- **Artifact** — generated files and outputs (filesystem)

State is checkpointed to `state.db.json` between every loop iteration. The system can resume from any checkpoint.

### The Improvement Loop

Inspired by autoresearch's try-measure-keep/revert discipline:

1. **Plan** — O1 builds a task graph with evaluation criteria
2. **Execute** — Worker runs the task (fast, cheap, many attempts)
3. **Evaluate** — Critic scores output against criteria
4. **Keep or revert** — Good results advance; failures get retried or escalated
5. **Learn** — Heuristics saved to skills DB for future runs

After 5 consecutive worker failures, the system escalates to O1 for strategic diagnosis and replanning.

## Dependencies

Intentionally minimal:

```
openai>=1.30.0
python-dotenv>=1.0.0
```

That's it. Ollama runs as a separate local service. No LangChain, no LangGraph, no framework overhead.

## Hardware

Developed on Apple M4 Pro (24GB unified memory). Ollama runs 70B Q4 models in ~18GB, leaving room for application state. MLX is available for workloads that benefit from native Apple Silicon acceleration.

## License

Private repository.
