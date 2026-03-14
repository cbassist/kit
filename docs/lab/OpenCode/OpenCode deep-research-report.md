# OpenCode + Oh-My-OpenCode Workflow Capabilities for an Autonomous R&D Lab Experiment Loop

## Executive summary

Oh-My-OpenCode (OMO) is no longer “just a preset config”: in the current codebase (now maintained as **oh-my-openagent**, “previously oh-my-opencode”), it is a multi-agent harness layered on top of OpenCode’s session + tool runtime. It adds (a) opinionated agent roles and orchestration patterns, (b) autonomous loop primitives (Ralph + Ultrawork loops), (c) category + skill routing (model selection by work type), (d) background-agent concurrency with retrieval tools, (e) a plan→execute system (Prometheus→Atlas) with resumable state, and (f) a deep toolchain (hash-anchored edits, LSP tools, AST-grep, refactor workflows). citeturn21view0turn15view4turn18view1turn22view0

For your lab architecture, the key punchline is: **OMO already implements most of what experiment-loop executors typically rebuild**—task decomposition, parallel attempt farming, verification-first completions, and resumable state—while OpenCode provides the missing glue you need for *measurement*: programmatic sessions, structured output formats, and JSON event streams. citeturn18view1turn27view0turn27view2turn29view1

**Important constraint for “what’s actually working”:** several features exist but are (a) flagged experimental, (b) known to have sharp edges, or (c) only provide “resolution-time fallback” rather than robust runtime failover. Examples: `experimental.task_system` has had backup-file growth issues; `oh-my-opencode run` has an open request for JSON streaming parity with `opencode run --format json`; and OpenCode permission enforcement has had a serious regression reported in the plugin’s issue tracker (closed, but relevant for safety gating). citeturn29view3turn29view1turn29view0

The sections below give you a ranked inventory mapped to your three-loop improvement system, with concrete configuration/invocation, measurable tests, and “current gap” framing.

### Summary table of ranked workflow capabilities

| Rank | Capability | Current usage (from your description) | Potential impact (1–10) | Implementation effort (1–10) |
|---:|---|---|---:|---:|
| 1 | Eval-gated autonomous iteration loop (Ralph/Ulw + quality gates) | You do manual retry/eval; not described as loop-integrated | 10 | 7 |
| 2 | Plan→execute task graphs with resumable state (Prometheus→Atlas + boulder/notepads) | Not described as core path | 9 | 4 |
| 3 | Parallel background swarm with concurrency controls + monitoring | You fork terminal agents; likely missing built-in background_task manager | 9 | 4 |
| 4 | Category + skill routing for cost-aware model selection (custom categories) | You have categories configured; unclear if used as routing primitive | 8 | 3 |
| 5 | Programmatic orchestration + telemetry (OpenCode server/SDK + JSON events + structured outputs) | You have an eval harness; not described as OpenCode-native | 8 | 6 |
| 6 | “Toolchain upgrade” for repo-scale correctness (Hashline edit + LSP + AST-grep + /refactor) | You do refactors; unclear if using these tools | 8 | 4 |
| 7 | Context compression + hierarchical repo memory (/init-deep + contextual injection + compaction hooks) | You do docs/extraction; unclear if using hierarchical AGENTS | 7 | 3 |
| 8 | Skill-embedded MCP tooling and reusable lab heuristics (skills + MCP + permissions) | You generate docs and run validations; not described as skillized | 7 | 5 |
| 9 | Session history mining + export for heuristic reuse (session tools, session APIs, stats/export) | You have eval scoring; likely not mining OpenCode session artifacts | 6 | 5 |
| 10 | Tmux multi-pane + interactive Bash sessions for live multi-agent workflows | Not described as used | 5 | 2 |

The capabilities themselves (not the impact/effort scores) are all present in the current ecosystem of oh-my-openagent + OpenCode docs and references. citeturn21view0turn15view4turn17view0turn27view0turn28view2

## Workflow pattern inventory

OMO supports a set of *distinct workflow patterns* that map cleanly to your Strategic / Project / Experiment loops.

### Always-on orchestration patterns inside a single session

The default “discipline agents” model is: **Sisyphus** orchestrates and delegates; **Prometheus** plans; **Atlas** executes plans by delegating code-writing tasks; **Explore/Librarian** do fast retrieval; **Oracle/Momus/Metis** provide higher-IQ consulting / review. This division is documented both in the orchestration guide (Prometheus→Metis/Momus→Atlas→Workers) and the agent-model matching guidance (models are “developers,” fit matters; deep specialists differ from communicators). citeturn18view1turn23view1turn20view0

### Autonomy loop patterns

Ralph Loop (`/ralph-loop`) runs a self-referential loop until it detects a completion signal (`<promise>DONE</promise>`), reaches a max iteration cap (default 100), or you cancel it; it will auto-continue if the agent stops without completion. Ultrawork Loop (`/ulw-loop`) is explicitly defined as “same as ralph-loop but with ultrawork mode active… maximum intensity—parallel agents, background tasks, aggressive exploration.” citeturn15view4turn21view0

### Plan-then-execute pipeline with resumability

Prometheus produces a plan artifact (`.sisyphus/plans/*.md`), optionally gets a high-accuracy review loop from Momus (“OKAY” gate with explicit criteria), then `/start-work` hands the plan to Atlas. Atlas uses a persisted state file `boulder.json` to resume work across sessions with progress tracking and continuation injection. citeturn18view1turn18view2turn25view0

### Multi-agent parallelism: background tasks + category delegation

Subtasks are delegated via tools (not ad-hoc prompting): the `task` tool routes by categories (built-ins like `deep`, `quick`, `ultrabrain`, `visual-engineering`, etc.), can also choose direct subagent types, and supports background execution with `background_output` / `background_cancel`. Background concurrency is configurable (global default, per-provider, per-model), and there’s a stale timeout. citeturn22view3turn17view0

### Toolchain patterns: correctness and repo-scale refactors

The “refactor” and edit toolchain is a major differentiator: the `edit` tool is hash-anchored (`LINE#ID`) and validated against content hashes; LSP tools provide workspace rename, goto definition, find references, and diagnostics; AST-grep enables AST-aware search/replace; `/refactor` coordinates these with architecture analysis and TDD verification. citeturn15view0turn15view4turn31view5

### Configuration and extensibility patterns

Beyond the README headline features, the config surface includes: background task settings, tmux integration, experimental toggles (e.g., aggressive truncation), skill sources and enable/disable lists, disabling built-in MCP servers, and a long list of built-in hooks that can be disabled individually. This is relevant because you can “compose” new workflows by combining categories + skills + hooks rather than writing a whole new harness. citeturn17view0turn12view2turn14view2

image_group{"layout":"carousel","aspect_ratio":"16:9","query":["OpenCode terminal UI screenshot","oh-my-opencode tmux background agents panes","OpenCode LSP diagnostics terminal"] ,"num_per_query":1}

## Ranked workflow capabilities

**Rank 1: Eval-gated autonomous iteration loop (Ralph/Ulw + quality gates)**  
**What**: Turn `/ralph-loop` (or `/ulw-loop`) into a measurable “attempt→evaluate→retry/escalate” engine for your experiment loop. citeturn15view4turn21view0  
**How**: Use `/ralph-loop` stop semantics (DONE marker + max iterations + cancel) and *move your real stop condition into the completion contract*: require DONE only when your eval harness score ≥ threshold. The loop mechanics are already defined, including the DONE signal and default max iterations. citeturn15view4  
To inject an *external* gate, rely on the Claude Code compatibility hook mechanism (OMO includes a built-in `claude-code-hooks` hook) and/or OpenCode server orchestration to run your eval script at “end-of-turn” and decide whether to continue the session. citeturn17view0turn12view2turn27view0  
**Test**: Add an eval case that requires iterative improvement (e.g., first attempt fails tests; second attempt must fix). Measure (a) number of iterations to pass, (b) % runs that reach the threshold before max iterations, and (c) cost/time per successful completion. OpenCode supports per-session cost/token stats and JSON event output; use those to quantify. citeturn27view2turn27view3  
**Current gap**: You’re already scoring outputs in `ai-lab/evals/knowledge_plane/`, but you’re not using the loop primitive that keeps working until completion; instead you rely on the Project loop to requeue retries.

**Rank 2: Plan→execute task graphs with resumable state (Prometheus→Atlas + boulder/notepads)**  
**What**: Use OMO’s built-in planning/execution architecture as your experiment-loop “task graph runtime”: plans become artifacts; execution is deterministic and resumable. citeturn18view1turn25view0  
**How**: Drive Prometheus via `@plan` or switching agents; it generates `.sisyphus/plans/{name}.md`. Then run `/start-work` which activates Atlas and creates/uses `boulder.json` to track progress and resume across sessions. citeturn18view2turn25view0  
If you already have a `planner.py` that emits task graphs, you can **emit the plan file artifact yourself** into `.sisyphus/plans/` and let `/start-work` pick it up (Atlas explicitly “reads plan → analyzes tasks → delegates → verifies → reports”). The docs emphasize plans include tasks, dependencies, and acceptance criteria, and the executor operates over those TODOs sequentially with delegation. citeturn18view1turn25view0  
**Test**: Add a “runbook synthesis” eval where the gold output is a plan with correct file references + acceptance criteria. Then measure whether `/start-work` runs to completion without manual steering and whether resuming after an interrupt continues from the correct task. The resumability rules and `boulder.json` semantics are documented. citeturn18view2  
**Current gap**: Your Strategic loop already plans task graphs, but your Experiment loop executor is (by your description) primarily “forked terminal agents” returning results—without a first-class plan artifact + resume state.

**Rank 3: Parallel background swarm with concurrency controls + monitoring**  
**What**: Replace ad-hoc “fork N terminals” with OMO background tasks that are bounded, queryable, cancelable, and aware of provider/model concurrency limits. citeturn17view0turn22view3  
**How**: Configure `background_task` with `defaultConcurrency`, per-provider/per-model limits, and `staleTimeoutMs`. Then spawn background runs through `task` / `call_omo_agent` with `run_in_background`, and collect results via `background_output` or cancel with `background_cancel`. citeturn17view0turn22view3turn26search17  
**Test**: Multi-agent coordination benchmark: create a decomposable task (e.g., “find 5 candidate fixes,” “run tests,” “summarize failing cases,” “draft patch sets”) and compare (a) wall-clock time-to-first-working-patch and (b) success@k between serial vs background swarm. Background TTL and diagnostic procedures are documented in the FAQ. citeturn26search17turn27view3  
**Current gap**: You already run 100s of attempts, but your concurrency control, timeouts, and result collection are likely external; OMO provides built-in primitives aligned to this exact use case.

**Rank 4: Category + skill routing for cost-aware model selection (custom categories + Sisyphus-Junior)**  
**What**: Make routing a *first-class, testable policy*: “what kind of work is this?” selects the model + prompt mindset; “what domain workflow is needed?” injects skills and MCP tooling. citeturn22view0turn22view2  
**How**: Use built-in categories (e.g., `quick`, `deep`, `ultrabrain`, `visual-engineering`) and define custom categories in `oh-my-opencode.json` with fields like `model`, `variant`, `temperature`, `tools`, `thinking`, and `is_unstable_agent`. Delegated execution is performed by Sisyphus-Junior (cannot redelegate, preventing delegation loops). citeturn22view2turn22view3  
For your lab, define categories that map to your experiment buckets, for example:  
- `canon-retrieval` → cheapest fast model + MCP-heavy retrieval  
- `failure-diagnosis` → higher reasoning effort  
- `runbook-synthesis` → writing-focused model  
These are schema-supported patterns (custom category config is explicitly documented). citeturn22view2turn17view0  
**Test**: Model selection test: for each eval case type, assert the session’s delegated tasks used the intended category/model. Then compare scores and costs when routing is enabled vs disabled. OpenCode exposes session APIs and model/cost stats to measure drift. citeturn27view0turn27view2  
**Current gap**: You already have categories in config, but you’re not treating them as a measured policy layer (“routing correctness” as a scored axis).

**Rank 5: Programmatic orchestration + telemetry (OpenCode server/SDK + JSON events + structured outputs)**  
**What**: Turn the experiment loop from “text in/text out” into a measurable pipeline with structured outputs, session introspection, and event streams—without rebuilding an agent runtime. citeturn7view3turn27view0turn27view2  
**How**: Run `opencode serve` as a headless server exposing an OpenAPI interface (sessions, messages, todos, diffs, permissions). From your orchestrator you can create sessions, send prompts synchronously or async, run slash commands, and fetch status. citeturn7view3turn27view1  
Two particularly high-leverage measurement hooks:  
- `opencode run --format json` emits raw JSON events (tool calls, thinking/reasoning parts, status). citeturn27view2turn29view1  
- `session.prompt` in the SDK supports `body.outputFormat` for structured output, and can inject context without triggering a reply (`noReply: true`). citeturn27view0  
**Test**: “schema compliance + citation groundedness” can be enforced by requiring structured `outputFormat` responses for specific substeps (e.g., runbook synthesis), and validating them in your harness. For telemetry, store JSON events and compute per-tool usage, retry counts, and time-in-tool. citeturn27view0turn27view2  
**Current gap**: You already have a strong scoring harness, but without OpenCode-native telemetry you’re leaving a lot of signal on the table (tool traces, diffs, per-step costs).

**Rank 6: Repo-scale correctness toolchain (Hashline edit + LSP + AST-grep + /refactor)**  
**What**: Dramatically reduce “agent failure modes” that come from flaky editing and shallow repo navigation, not from model intelligence. citeturn15view0turn31view5  
**How**: Use the hash-anchored `edit` tool (`LINE#ID` hash markers; rejects stale edits), LSP tools for diagnostics/rename/navigation, AST-grep for structural transformations, and `/refactor` for coordinated refactoring with verification and codemap generation. citeturn15view0turn15view4turn31view5  
OMA positions Hashline as a major reliability improvement (stable identifiers for lines; edits rejected if file changed). citeturn31view5turn15view0  
**Test**: Coding quality test: select tasks known to trigger stale-line/edit conflicts (multi-file refactors, renames, large diffs). Compare (a) successful patch rate and (b) “corrupt edit” incidents before/after enabling hashline + LSP-driven rename. citeturn15view0turn27view1  
**Current gap**: You’re using agents for refactors, but if you’re not explicitly using hashline/LSP/AST-grep, you’re absorbing avoidable failure rates.

**Rank 7: Context compression + hierarchical repo memory (/init-deep + rules injection + compaction)**  
**What**: Improve retrieval recall and reduce token spend by making context *structural*, not conversational. citeturn15view4turn31view5turn19search16  
**How**: Use `/init-deep` to generate hierarchical `AGENTS.md` files throughout the repo so agents auto-read local context. Combine with OpenCode “rules”/instructions injection via `AGENTS.md` and configurable instruction file lists. citeturn15view4turn19search16turn6search6  
OpenCode also supports compaction controls (reserved tokens, auto compaction) at the core config layer, which pairs well with OMO truncation/compaction hooks and aggressive truncation experimental settings. citeturn26search3turn17view0turn29view3  
**Test**: “canon retrieval recall” bucket: compare retrieval recall and gold-fact coverage with and without `/init-deep` artifacts committed. Measure token usage deltas using OpenCode stats. citeturn27view2turn31view5  
**Current gap**: You’re already doing documentation/extraction work, but hierarchical context + compaction is the scalable version of that.

**Rank 8: Skill-embedded MCP tooling and reusable lab heuristics (skills + MCP + permissions)**  
**What**: Convert your lab’s best heuristics into loadable skills that also bring the right tool surface (MCP servers, browser automation, permissions). citeturn22view3turn28view4turn28view3  
**How**: OpenCode supports skills discovered via `SKILL.md` in several compatible directories (project/global, and Claude-compatible locations). Skills are loaded on-demand via the `skill` tool. citeturn28view4  
OMO expands this with skill strategies (category+skill combos) and “skill-embedded MCPs” so tool servers can be scoped to the task rather than bloating every context window. citeturn22view3turn31view5turn28view3  
Also, you can lock tool usage via OpenCode’s permission system (ask/allow/deny per tool, wildcards for MCP tools). This matters for your autonomous lab safety posture. citeturn28view2turn10view8  
**Test**: Prompt optimization test: run identical eval cases with a “skills DB” skill disabled vs enabled (e.g., a failure-diagnosis checklist skill). Compare score deltas in gold fact coverage, schema compliance, and citations. citeturn28view4turn22view0  
**Current gap**: Your `memory.py` DB is conceptually aligned; the missing piece is making those heuristics executable *inside* the agent runtime with permissions + tools.

**Rank 9: Session history mining + export for heuristic reuse (session tools, export, stats)**  
**What**: Make “heuristic reuse” literal: query prior sessions, extract patterns, and feed them back as skills or notepad entries. citeturn21view0turn27view2turn27view0  
**How**: OpenCode exposes session list/get/messages APIs and can export session data as JSON; the SDK also supports enumerating sessions and messages. citeturn27view0turn27view2turn27view1  
OMO’s orchestration design explicitly includes “Wisdom Accumulation” and a notepad system (.sisyphus/notepads/{plan-name}/ with learnings/decisions/issues/verification). citeturn18view1  
**Test**: Heuristic reuse benchmark: run a two-phase eval where Phase A discovers a repo-specific convention, Phase B requires reapplying it in a different module. Score improvement when the convention is harvested into notepads/skills vs when it is not. citeturn18view1turn27view0  
**Current gap**: You score “heuristic reuse” today, but you may not be using the platform’s native session/notepad artifacts as the mem-store feeding that metric.

**Rank 10: Tmux multi-pane + interactive Bash sessions for live multi-agent workflows**  
**What**: Make multi-agent execution visible and interactive (REPLs, debuggers, TUIs “stay live”) while background agents work in their own panes. citeturn17view0turn31view5  
**How**: Enable `tmux` config (`enabled`, `layout`, pane sizes). Requirements include running inside tmux and running OpenCode with an explicit `--port` (server mode). The reference includes a shell function pattern for auto-allocating ports per session. citeturn17view0turn27view3  
**Test**: For your “validation” use case, measure reduction in human babysitting time (time to detect a stuck test run; time to resume after an interactive prompt) and incidence of “lost REPL state” when validating long-running tasks. (This is less about raw score and more about operator throughput.) citeturn17view0turn26search17  
**Current gap**: You already fork terminals, but tmux integration gives you standardized visibility + a principled way to keep interactive sessions alive.

## Multi-model orchestration patterns

Your requested patterns map directly onto OMO’s “models are developers” philosophy and its agent+category system.

### GPT reasons, Claude executes

This is effectively the separation between “deep specialist” and “communicator/orchestrator.” The agent-model matching guide explicitly assigns Hephaestus to a GPT Codex model for deep autonomous work, while recommending Claude/Kimi/GLM-family models for Sisyphus orchestration because they follow complex multi-step prompts more reliably. citeturn20view0  
In practice: run Oracle/Hephaestus to produce an architecture decision or failure diagnosis, then delegate implementation as `task(category="deep" or "quick")` so Sisyphus-Junior executes with constrained scope. citeturn22view3turn18view1  
Cost profile: expensive reasoning should happen in bounded bursts; the system explicitly says utility runners should remain fast/cheap and not be “upgraded to Opus.” citeturn20view0turn22view0

### Parallel model racing

OMO already supports concurrent background tasks with per-provider/per-model caps and a stale timeout, which is exactly what “model racing” needs (N attempts, pick best). citeturn17view0turn22view3  
You implement racing as: spawn 3–5 background tasks with different categories/models for the same objective; then choose by an objective metric (tests pass, lint clean, eval score). OpenCode’s JSON event stream (`--format json`) makes the selection step auditable. citeturn27view2turn29view1

### Cascading complexity escalation

OMO categories provide a clean escalation ladder (`quick` → `unspecified-low` → `deep`/`ultrabrain`). Custom categories add your own “cheap local first” tiers. citeturn22view0turn22view2  
A pragmatic hardware-aware twist: for local execution via Ollama, the configuration reference warns to set `stream: false` to avoid JSON parse errors (Ollama returns NDJSON while the SDK expects a single JSON object). That matters if you want “cheap local first” to be stable. citeturn17view0

### Cross-model review

The orchestration pipeline already contains review agents: Momus (“ruthless reviewer” with explicit acceptance criteria thresholds) and Oracle (architecture/debugging consultation). citeturn18view1turn20view0  
A strong pattern for your lab: “Sisyphus-Junior writes code → Momus reviews plan/patch → Oracle adjudicates architecture disputes.” This aligns to your “architecture adjudication” bucket. citeturn18view1turn20view0

### Speculative execution (fast model starts, slow model validates)

This is “background Agents + main agent focus”: let Explore/Librarian gather evidence in the background so the main agent stays pointed at core logic. The README and docs highlight background agents as a core feature. citeturn21view0turn26search17turn22view3  
For measurement, you can bind “validation responsibility” to a specific agent and track it through session APIs and exported tool events. citeturn27view1turn27view2

## Integration with your three-loop improvement architecture

### Strategic loop alignment

Your Strategic loop (O1/reasoning models) plans task graphs and diagnoses failures. OMO can consume those outputs as either:  
- a Prometheus-style plan artifact (drop a `.sisyphus/plans/*.md` plan and run `/start-work`), or  
- a direct per-task delegation list executed via category-based `task` calls. citeturn18view1turn25view0turn22view3

### Project loop alignment

Your Project loop (result evaluation + queue management) becomes more powerful when it can “see inside” the experiment loop. OpenCode provides that visibility:

- Programmatic sessions (create/list/messages/status/todos/diffs) via HTTP, and a generated SDK. citeturn7view3turn27view1turn27view0  
- Structured output control (`outputFormat`) for schema compliance. citeturn27view0  
- Exporting sessions and computing stats/costs. citeturn27view2  

This is where your scoring weights (schema compliance, citation groundedness) can become enforceable, not aspirational.

### Experiment loop alignment

OMO is already designed as “execution by delegation,” with Atlas forced to delegate code writing and a Sisyphus-Junior executor that cannot redelegate, preventing runaway delegation loops—a good structural match to “run 100s of attempts.” citeturn18view1turn22view3  
For raw throughput, the built-in background_task concurrency model gives you “how many can run simultaneously” semantics more precise than “how many terminals can I open.” citeturn17view0turn26search17

### Injecting structured lab state

You asked specifically about injecting `state.db.json` into prompts. Two platform-native ways:

1) **Context injection without a reply** via OpenCode’s `noReply` message (useful for injecting state/memory into a session before giving the real task). citeturn27view0  
2) **Skills**: represent state as a skill and load it on demand; OpenCode’s skill discovery locations and OMO’s category+skill combos make this reusable. citeturn28view4turn22view3  

### Capturing structured output and tool traces

For “structured output (not just text),” OpenCode gives you two measurement-grade streams:

- JSON event stream from `opencode run --format json`. citeturn27view2turn29view1  
- Structured response format via `outputFormat` in the SDK prompt call. citeturn27view0  

A key caveat: programmatic use of `oh-my-opencode run` does **not** currently provide the same JSON stream on stdout (open request), so you should favor `opencode run --format json` or server APIs when integrating with `main.py`. citeturn29view1turn27view2

## Measurement and test suite design for iteration-over-iteration improvement

Your harness already scores retrieval recall, gold-fact coverage, schema compliance, citation groundedness. The missing piece is making OMO workflows produce *repeatable, comparable artifacts* (plans, diffs, tool traces, session exports). OpenCode directly supports exporting sessions and retrieving diffs/todos, which is ideal for regression tests. citeturn27view1turn27view2

### Coding quality test

Design: each test case includes repo state + task description + acceptance criterion (“tests pass”). Run the task through one of:
- `/start-work` from a plan file (measures plan→execute path), or citeturn25view0turn18view1  
- `/ralph-loop` with a hard stop condition that requires passing tests before DONE. citeturn15view4  

Metric: binary pass/fail + time-to-green + number of retries. Use OpenCode session diff and stats to measure churn and cost. citeturn27view1turn27view2

### Model selection test

Design: task cases labeled by “intended category” (quick/deep/ultrabrain/writing/visual-engineering). Assert that delegated subtasks used the expected category/model mapping and that performance improves vs a single fixed model. Categories and custom category schemas are explicit in the features reference. citeturn22view0turn22view2  
Metric: routing accuracy + overall eval score + cost per point. Collect model usage via session logs/stats. citeturn27view2turn27view0

### Prompt optimization via skills DB

Design: for each bucket, create a corresponding skill that encodes your “best known prompt + checklist + tool policy.” Enable/disable the skill and run A/B. OpenCode skills are first-class (`SKILL.md` discovery + `skill` tool). citeturn28view4turn17view0  
Metric: deltas in schema compliance and citation groundedness (skills can enforce structure). Use `outputFormat` where possible to remove ambiguity. citeturn27view0

### Multi-agent coordination test

Design: decomposable tasks where parallelism should win (e.g., “investigate failure,” “search docs,” “grep repo,” “draft fix options,” “implement chosen fix”). Run serial vs background swarm with controlled concurrency (`background_task` config). citeturn17view0turn22view3  
Metric: wall-clock time, success rate, cost. Use JSON event streams to compute “parallel utilization.” citeturn27view2turn29view1

### Context injection test

Design: provide the agent either (a) raw text blob of state, (b) structured injection via `noReply` message, or (c) a skill that loads state. Compare answer quality and hallucination rate. citeturn27view0turn28view4  
Metric: retrieval recall + gold-fact coverage + citation groundedness.

## Power-user capabilities and caveats

### High-leverage features that are easy to miss

- **Background task governance**: per-provider/per-model concurrency and stale timeouts are configurable, which matters if you’re doing 100-attempt farms. citeturn17view0turn26search17  
- **“Unstable agent” monitoring hooks**: OMO includes hooks like `unstable-agent-babysitter` and supports an `is_unstable_agent` flag in category definitions (forces background mode for monitoring). citeturn2view3turn22view2  
- **Non-interactive environment support**: a built-in hook list includes `non-interactive-env` and `interactive-bash-session`, which are directly relevant when you run OpenCode/OMO inside automation shells rather than interactive terminals. citeturn17view0turn12view2  
- **Browser automation as a first-class skill/tooling choice**: the config reference documents a browser automation engine provider and the built-in `playwright` skill. That can turn UI validation into a measurable workflow rather than a screenshot guess. citeturn17view0turn21view0  
- **OpenCode extensibility beyond OMO**: custom commands, custom tools, and plugins are officially supported by OpenCode (commands can inject shell output into prompts; plugins hook into events). citeturn28view0turn28view1turn28view3  

### Caveats you should explicitly architect around

- **Programmatic streaming gap**: `oh-my-opencode run` currently lacks machine-readable JSON streaming on stdout (open issue); if your experiment loop depends on streaming traces, prefer OpenCode server APIs or `opencode run --format json`. citeturn29view1turn27view2turn7view3  
- **Experimental features can bite**: `experimental.task_system: true` has had a reported bug causing growing backup files, even though the doctor output shows it as a supported config field along with other experimental toggles (`truncate_all_tool_outputs`, `aggressive_truncation`, `auto_resume`). Treat experiments as opt-in and measurable. citeturn29view3turn17view0  
- **Safety/permissions regressions**: a serious regression was reported where OpenCode permissions (e.g., `external_directory: deny`) became unenforced after installing the plugin. Even if closed, you should treat tool-permission enforcement as something you verify in CI before running autonomous destructive workflows. citeturn29view0turn28view2  
- **Model fallback isn’t “magic runtime failover” yet**: while docs and references describe provider fallback chains and model resolution mechanisms, issues and feature requests indicate runtime request-failure fallback (e.g., on 429/quota exhaustion) is not consistently handled the way production harnesses need. Plan for explicit escalation and/or a routing layer you control. citeturn17view0turn26search6turn26search4  
- **Ecosystem reality**: OpenCode is positioned as an open-source terminal coding agent (built by the team at entity["company","Anomaly","ai devtools company"]), and the community maintains an ecosystem of plugins/SDKs including a Python SDK—useful if you want your experiment loop to be Python-native. citeturn34view0turn7view3turn27view0  

### Note on sources vs your internal reference files

You asked to base this on specific internal files (`01/CANON.md`, `01/DEVLOG.md`, your eval cases JSONL, etc.). Those weren’t accessible in the connected sources available to me in this session, so the mapping to your lab is based on the architecture and harness details you provided verbatim, plus the public OMO/OpenCode docs and issue trackers cited throughout. citeturn21view0turn17view0turn27view0turn15view4turn18view1