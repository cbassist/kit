You are the strategist for this project.

## 0. Meta
- caller: planner
- confidence_threshold: 0.75
- budget_envelope: 2 weeks of dev time, M4 Pro 24GB hardware, OpenAI API budget ~$50/mo, Anthropic Max subscription (Claude Code), OpenAI Pro subscription (GPT/Codex)

## 1. Objective
Determine the optimal integration path for Oh-My-OpenCode (OMO) into our autonomous R&D lab's three-loop improvement system, maximizing measurable experiment throughput and quality while preserving our local-first, deterministic-infrastructure philosophy.

## 2. Success Metric
- Experiment loop can run autonomously via OMO (Ralph/Ultrawork or plan→execute) with eval-gated stopping
- Each iteration produces structured, scorable output compatible with our eval harness (currently 0.562 avg on 10-case benchmark)
- Cost per experiment iteration stays below $0.10 for worker-tier tasks (local models handle 90%+ of execution)
- Measurable improvement in eval scores over 3 successive improvement cycles

## 3. Current State Snapshot
```json
{
  "active_goal": "Wire OMO as the experiment loop executor with eval-gated quality control",
  "runtime_modules": [
    "ai-lab/main.py — 3-loop orchestration (Python, 186 LOC)",
    "ai-lab/planner.py — O1 strategic planning (447 LOC)",
    "ai-lab/memory.py — skills DB + vector search via Ollama nomic-embed-text (247 LOC)",
    "ai-lab/evals/knowledge_plane/ — A/B eval harness (870 LOC, 10 cases, 5 buckets)",
    "ai-lab/evals/knowledge_plane/local_backend.py — Ollama-powered local retrieval (beats hosted)"
  ],
  "recent_experiment_results": [
    "Eval harness A/B: local vector 0.562 vs hosted 0.547 vs stub 0.465",
    "Local retrieval beats OpenAI file_search on 7/10 cases at zero API cost",
    "Goal 001: qwen2.5-coder:14b confirmed as optimal local worker (24/25 benchmark)",
    "MLX speculative decoding: +14% short tasks, +124% sustained generation"
  ],
  "known_constraints": [
    "M4 Pro 24GB — Ollama runs 14B Q6 in ~8.5GB, leaves room for concurrent processes",
    "Two dependencies only (openai, python-dotenv) — adding OMO is a runtime dependency, not a library dep",
    "OMO is a TypeScript/Node runtime; our lab is Python — integration is via CLI/API, not library import",
    "CANON: deterministic by default, probabilistic only where reasoning is required",
    "CANON: no feature added unless it improves reliability, observability, or decision quality"
  ],
  "known_gaps": [
    "Experiment loop currently uses ad-hoc forked terminals, not OMO's built-in loop primitives",
    "No structured output capture from agent sessions (text only)",
    "No eval-gated stopping — eval runs post-hoc, not as a loop gate",
    "No session history mining for heuristic reuse",
    "No /init-deep hierarchical context in our repo",
    "Categories configured in oh-my-opencode.json but not treated as a measured routing policy",
    "oh-my-opencode run lacks JSON streaming parity with opencode run --format json"
  ]
}
```

## 4. Constraints
- Blast radius: refactor (not rewrite — the Python lab core stays; OMO is wired in as the execution layer)
- Must remain measurable: every change must produce a delta visible in our eval harness
- Local-first: Ollama/MLX handles execution; API models handle planning/review only
- OMO is a runtime tool, not a library: integration is via CLI (`opencode run`, `opencode serve`) or file artifacts (`.sisyphus/plans/`)
- Permission safety: OMO had a reported permissions regression — we must verify tool permissions are enforced before running autonomous destructive workflows
- `oh-my-opencode run` does NOT currently support `--format json` streaming — prefer `opencode run --format json` or server APIs for programmatic integration

## 5. Prior Attempts & Failure Signatures
- Manual forked terminal agents: work but lack structured output, no eval gating, no concurrency control, no resume state. Category: tooling gap.
- Stub local retrieval: 0.465 score — replaced with vector search (0.562). Category: resolved (data quality).
- No prior attempt at OMO loop integration — this is greenfield.

## 6. Explicit Option Set

| Option | Description | Estimated Cost | Risk |
|--------|-------------|---------------|------|
| A: Ralph Loop + Eval Gate | Wire `/ralph-loop` as the experiment loop. Inject eval harness as the DONE condition via hooks. Agent iterates until score threshold met or max iterations reached. Keep Python orchestrator as the project/strategic loops. | Low (config + hook) | Medium — Ralph's stop semantics may not cleanly support external scoring |
| B: Plan→Execute Pipeline | Emit task graphs from `planner.py` as `.sisyphus/plans/*.md` artifacts. Use `/start-work` (Atlas) to execute them. Use `boulder.json` for resume state. Python project loop monitors via OpenCode server API. | Medium (artifact format + API integration) | Low — well-documented, resumable, but adds file-format coupling |
| C: OpenCode Server SDK | Run `opencode serve` as a headless server. Python `main.py` drives sessions programmatically via HTTP API (create session, send prompts with `noReply` context injection, collect structured outputs via `outputFormat`). Full control, full telemetry. | High (API client + structured output contracts) | Low — most flexible but most engineering effort |
| D: Hybrid — B for planning, A for execution | Emit plans as `.sisyphus/plans/`, then run `/ralph-loop` within each task step with eval-gated stopping. Best of both: structured plans + autonomous iteration per task. | Medium | Medium — two integration surfaces |

## 7. Assumptions & Unknowns
- Assumptions:
  - OMO's Ralph Loop reliably respects max iteration caps and DONE signals (documented, not verified by us)
  - OpenCode server API is stable enough for programmatic session management (documented as OpenAPI)
  - `.sisyphus/plans/` artifact format is stable and Atlas will execute plans we generate externally
  - Background task concurrency controls work as documented (per-provider/per-model caps)
  - Our eval harness can run as a hook or post-processing step within ~5 seconds per case

- Unknowns:
  - Can a Ralph Loop hook call our Python eval harness and feed the score back as a continue/stop signal?
  - What is the actual latency of `opencode serve` API calls vs direct CLI invocation?
  - Does `boulder.json` survive across OpenCode restarts or only within a session?
  - How much token overhead does OMO's agent system add per experiment iteration?
  - Can we run OpenCode server + Ollama simultaneously on 24GB without OOM?

- Evidence that would change our mind:
  - If Ralph Loop hooks cannot invoke external scripts → Option A is eliminated
  - If OpenCode server API adds >2s latency per call → Option C becomes impractical for 100-attempt loops
  - If `.sisyphus/plans/` format is undocumented/unstable → Option B/D lose their advantage

## 8. Decision Question
Given options A/B/C/D, our current eval baseline (0.562), hardware constraints (M4 Pro 24GB), and the requirement that every change must produce a measurable delta in our eval harness: what is the optimal 3-step implementation sequence that maximizes experiment throughput while minimizing integration risk, and should the experiment loop use OMO's Ralph/Ultrawork primitives or remain Python-native with OMO as a called tool?

## 9. Required Output Schema (JSON only)
```json
{
  "meta": {
    "caller": "planner",
    "confidence_score": 0.0,
    "confidence_rationale": "string"
  },
  "chosen_strategy": {
    "option_id": "A|B|C|D",
    "rationale": "string",
    "expected_outcome": "string"
  },
  "rejected_alternatives": [
    {
      "option_id": "string",
      "reason": "string"
    }
  ],
  "assumptions": ["string"],
  "risk_forecast": [
    {
      "failure_mode": "string",
      "likelihood": "low|medium|high",
      "impact": "low|medium|high",
      "detection_signal": "string",
      "mitigation": "string"
    }
  ],
  "smallest_validating_experiment": {
    "description": "string",
    "duration": "string",
    "success_signal": "string",
    "failure_signal": "string"
  },
  "kill_criteria": {
    "stop_when": ["string"],
    "pivot_to": "string",
    "escalate_when": ["string"]
  },
  "ordered_tasks": [
    {
      "task_id": "T-01",
      "name": "string",
      "description": "string",
      "dependencies": [],
      "evaluation_criteria": ["string"],
      "risk": "low|medium|high"
    }
  ],
  "interface_contract": {
    "artifacts_emitted": ["string"],
    "state_updates_for_project_loop": "string",
    "worker_instructions_format": "string"
  },
  "memory_actions": [
    {
      "layer": "semantic|artifact|episodic",
      "action": "write|update|delete",
      "key": "string",
      "value": "string"
    }
  ],
  "verification": {
    "how_to_confirm_this_was_right": "string",
    "observable_result": "string",
    "reversal_conditions": ["string"]
  }
}
```

## Rules
- Return JSON only (no markdown fences).
- Keep `ordered_tasks` to 3-7 items.
- Make evaluation criteria observable and testable.
- If confidence_score < confidence_threshold, the primary output MUST be `smallest_validating_experiment`, not a full plan.
- Always populate `kill_criteria` — go criteria without stop criteria is reckless.
- `memory_actions` must be intentional — only write heuristics worth retaining.
