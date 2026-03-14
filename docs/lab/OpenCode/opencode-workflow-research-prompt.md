# Deep Research Prompt: OpenCode + Oh-My-OpenCode Workflow Capabilities

## Objective

Produce a ranked inventory of the most powerful workflow patterns available through OpenCode + Oh-My-OpenCode (OMO), mapped to our autonomous R&D lab's improvement loop. We need to know what OMO can do, what we're currently using, and what high-leverage capabilities we're leaving on the table.

## Context

### What We Are

An autonomous R&D lab (`01/ai-lab/`) with three nested loops:
- **Strategic Loop** (O1/reasoning models) — plans task graphs, diagnoses failures
- **Project Loop** (GPT-4o / Gemini) — evaluates results, manages task queue
- **Experiment Loop** (Ollama local / OpenCode workers) — executes tasks, runs 100s of attempts

OpenCode with Oh-My-OpenCode is our **experiment loop executor** — forked terminal agents that receive a task, execute it, and return structured results.

### What We Currently Use OpenCode For

1. **Coding tasks** — bug fixes, feature implementation, refactoring (via `@sisyphus` or `@hephaestus`)
2. **Validation** — running tests, checking imports, CLI help verification
3. **Documentation** — generating docs, extracting code from markdown

### Our Current Config

```json
{
  "agents": {
    "sisyphus": { "model": "anthropic/claude-opus-4-6", "variant": "max" },
    "hephaestus": { "model": "openai/gpt-5.3-codex", "variant": "medium" },
    "oracle": { "model": "openai/gpt-5.2", "variant": "high" },
    "librarian": { "model": "zai-coding-plan/glm-4.7" },
    "explore": { "model": "anthropic/claude-haiku-4-5" },
    "prometheus": { "model": "anthropic/claude-opus-4-6", "variant": "max" },
    "atlas": { "model": "opencode/kimi-k2.5-free" }
  },
  "categories": {
    "ultrabrain": { "model": "openai/gpt-5.3-codex", "variant": "xhigh" },
    "deep": { "model": "openai/gpt-5.3-codex", "variant": "medium" },
    "quick": { "model": "anthropic/claude-haiku-4-5" }
  }
}
```

### Our Eval Harness

We have a working A/B evaluation framework (`ai-lab/evals/knowledge_plane/`) with:
- 10 test cases across 5 buckets (canon retrieval, architecture adjudication, failure diagnosis, heuristic reuse, runbook synthesis)
- Weighted scoring: 35% retrieval recall, 25% gold-fact coverage, 20% schema compliance, 20% citation groundedness
- Baseline results: local stub 0.465, hosted retrieval 0.554

### Hardware

Apple M4 Pro, 24GB unified memory. Ollama runs 70B Q4 models in ~18GB. MLX available for native Apple Silicon acceleration.

## Research Questions

### 1. Workflow Pattern Inventory

Enumerate every distinct workflow pattern OMO supports, including but not limited to:

- **Ralph Loop** — self-referential dev loop. How does it decide when to stop? What signals does it use? Can we inject custom stopping criteria (e.g., eval score threshold)?
- **Ultrawork Loop** — aggressive parallel execution. How does it differ from Ralph? What makes it "ultra"?
- **Prometheus Planning → Atlas Execution** — structured plan-then-execute. Can we feed it our own task graphs from `planner.py`?
- **Background Agents** — parallel multi-agent execution. How many can run simultaneously? Can we orchestrate them programmatically?
- **Category-based Delegation** — routing tasks to specialist models. Can we define custom categories for our experiment types?
- **Tmux Integration** — visual multi-agent panes. How does this interact with our fork-terminal pattern?
- **Babysitting** — what is this feature? How does it monitor agent work?
- **Skills System** — can we write custom skills that inject our lab's memory/state into agent context?
- **Session Tools** — can we programmatically read past session results for our improvement loop?
- **Model Fallback Chains** — automatic fallback on rate limits. Can we customize the chain per task type?

### 2. Multi-Model Orchestration Patterns

For each pattern, describe:
- Which models are involved and why
- Cost profile (token usage, API calls)
- When it outperforms single-model execution
- How to configure it in `oh-my-opencode.json`

Specific patterns to evaluate:
- **GPT reasons, Claude executes** — Oracle analyzes, Sisyphus implements
- **Parallel model racing** — same task to multiple models, pick best result
- **Cascading complexity** — start with Haiku, escalate to Sonnet, then Opus
- **Cross-model review** — one model writes code, different model reviews it
- **Speculative execution** — fast model starts, slow model validates

### 3. Improvement Loop Integration

How can we wire OMO into our three-loop architecture?

- Can Ralph Loop be our experiment loop? (task → attempt → evaluate → retry/escalate)
- Can we programmatically launch OMO agents from Python (our `main.py`)?
- Can we inject structured context (our `state.db.json`) into agent prompts?
- Can we capture structured output (not just text) from agent completions?
- Can we set custom evaluation criteria that the loop uses for keep/revert decisions?
- How does OMO's memory/learning compare to our `memory.py` skills DB?

### 4. Recommended Test Suite for Measuring Improvement

Based on our existing eval harness, design tests that would clearly show iteration-over-iteration improvement when running OMO workflows. Tests should:

- Use our existing 5 buckets as a starting framework
- Be runnable via `python -m evals.knowledge_plane.runner`
- Have clear numeric scores that can be compared across runs
- Cover the three use cases we currently execute (coding, validation, documentation)

Specific test recommendations needed:
- **Coding quality test**: Given a task description and repo context, does the agent produce code that passes tests?
- **Model selection test**: Given a task type, does the system route to the optimal model?
- **Prompt optimization test**: Does storing model-specific prompting heuristics (our skills DB) improve scores over time?
- **Multi-agent coordination test**: Does parallel execution outperform serial on decomposable tasks?
- **Context injection test**: Does providing structured state improve answer quality vs raw context?

### 5. Power User Capabilities We May Be Missing

What advanced OMO features exist that aren't obvious from the README? Look at:
- The plugin/hook system
- Custom tool definitions
- MCP server integration
- The `experimental` config section
- Any undocumented CLI flags or environment variables
- Community-discovered workflows from Discord/GitHub issues

## Output Format

Produce a ranked list of workflow capabilities, ordered by potential impact on our improvement loop:

```
## Rank 1: [Capability Name]
**What**: One-line description
**How**: Configuration and invocation
**Impact**: Why this matters for our lab
**Test**: How to measure if it's working
**Current gap**: What we're doing instead (or not doing at all)
```

Include a summary table at the top with columns: Rank, Capability, Current Usage, Potential Impact (1-10), Implementation Effort (1-10).

## Constraints

- Focus on what's actually implemented and working, not roadmap items
- Prefer patterns that can run on our hardware (M4 Pro 24GB)
- Cost-consciousness: we want to maximize local/cheap model usage, reserve expensive models for strategic decisions
- Everything should be measurable — if we can't score it, we can't improve it

## Reference Files

Read these for full context:
- `oh-my-opencode/README.md` — overview
- `oh-my-opencode/docs/reference/features.md` — full feature reference
- `oh-my-opencode/docs/guide/orchestration.md` — planning/execution architecture
- `oh-my-opencode/docs/guide/agent-model-matching.md` — model selection philosophy
- `oh-my-opencode/docs/manifesto.md` — design philosophy
- `oh-my-opencode/assets/oh-my-opencode.schema.json` — full config schema
- `01/CANON.md` — our product spec
- `01/DEVLOG.md` — current status and decision log
- `01/ai-lab/evals/knowledge_plane/cases.jsonl` — our 10-case eval benchmark
- `01/docs/ORIGIN.md` — design philosophy and architecture narrative
