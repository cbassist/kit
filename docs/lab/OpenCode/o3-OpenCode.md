{
"meta": {
"caller": "planner",
"confidence_score": 0.81,
"confidence_rationale": "Option D satisfies structured-plan requirements (via .sisyphus/plans) while giving autonomous, eval-gated iteration with Ralph Loop. Engineering effort fits 2-week envelope (est. 5–6 dev-days) and leverages existing Python orchestrator with minimal refactor."
},
"chosen_strategy": {
"option_id": "D",
"rationale": "Combines the low-risk, well-documented Plan→Execute artifact flow (Atlas) with Ralph Loop’s autonomous retry capability, allowing us to inject the existing eval harness as a DONE gate. This preserves deterministic Python control for strategic/project loops, keeps OMO strictly at execution scope, and avoids heavy API client work.",
"expected_outcome": "Within two improvement cycles, experiment throughput doubles (parallel Ralph loops), eval score rises from 0.562 → ≥ 0.60, and per-iteration cost remains <$0.10 by offloading 90 %+ tokens to local Ollama workers."
},
"rejected_alternatives": [
{
"option_id": "A",
"reason": "Ralph Loop alone lacks structured task graphs and resume state, making orchestration brittle across crashes."
},
{
"option_id": "B",
"reason": "Plan→Execute without per-task autonomous retries would require re-implementing loop logic in Python, duplicating OMO features."
},
{
"option_id": "C",
"reason": "OpenCode server SDK demands new client code, adds network latency, and risks overshooting the 2-week budget."
}
],
"assumptions": [
"Ralph Loop hooks can invoke external Python scripts synchronously.",
"Atlas executes externally generated .sisyphus/plans without schema drift.",
"24 GB RAM suffices for concurrent OpenCode worker + Ollama 14 B model.",
"Eval harness completes in ≤ 5 s, acceptable for loop gating."
],
"risk_forecast": [
{
"failure_mode": "Ralph hook cannot return eval score to loop",
"likelihood": "medium",
"impact": "high",
"detection_signal": "Loop ignores failing score and continues iterations",
"mitigation": "Wrap hook call in test harness first; if unsupported, drop to max-iterations=1 and gate at Python level."
},
{
"failure_mode": "OOM when OpenCode and Ollama co-run",
"likelihood": "low",
"impact": "medium",
"detection_signal": "Kernel OOM logs; crashed worker",
"mitigation": "Lower model quantization to Q8_0 or offload plan parsing to a lightweight container."
},
{
"failure_mode": "Plan schema changes between OMO versions",
"likelihood": "low",
"impact": "medium",
"detection_signal": "Atlas rejects plan with validation error",
"mitigation": "Pin OMO version via package.json; add CI test that compiles a dummy plan."
}
],
"smallest_validating_experiment": {
"description": "Run a single Ralph Loop task invoked via Atlas from an externally generated .sisyphus plan, with a hook that calls the eval harness and stops on score ≥ 0.56.",
"duration": "1 day",
"success_signal": "Loop exits after achieving ≥ 0.56 and emits JSON result captured by Python orchestrator.",
"failure_signal": "Loop overruns max iterations or returns unstructured output."
},
"kill_criteria": {
"stop_when": [
"Eval-gated loop integration takes >4 dev-days without functional demo",
"Per-iteration latency exceeds 2× baseline (>120 s)",
"Memory footprint exceeds 20 GB leading to swap or crashes"
],
"pivot_to": "Option B with Python-native retry logic",
"escalate_when": [
"Ralph hook design blocks eval feedback",
"Atlas plan execution proves unstable across restarts"
]
},
"ordered_tasks": [
{
"task_id": "T-01",
"name": "Verify Ralph Hook Capability",
"description": "Prototype a Ralph Loop with post-iteration shell hook that echoes eval score; confirm hook value accessible for stop condition.",
"dependencies": [],
"evaluation_criteria": ["Hook returns numeric score", "Loop stops when threshold met"],
"risk": "medium"
},
{
"task_id": "T-02",
"name": "Emit Plan Artifacts",
"description": "Extend planner.py to write .sisyphus/plans/<uuid>.md reflecting current task graph and include eval-gate metadata.",
"dependencies": ["T-01"],
"evaluation_criteria": ["Plan passes Atlas validation", "Contains per-step eval-gate tags"],
"risk": "low"
},
{
"task_id": "T-03",
"name": "Integrate Atlas Execution",
"description": "Invoke `opencode run --plan <file>` from Python orchestrator, capture JSON stream, and route to eval harness.",
"dependencies": ["T-02"],
"evaluation_criteria": ["Structured JSON logged", "No unhandled exceptions"],
"risk": "medium"
},
{
"task_id": "T-04",
"name": "Parallel Loop Scaling",
"description": "Configure OMO worker pools (local provider) to run up to 3 Ralph loops concurrently within RAM budget.",
"dependencies": ["T-03"],
"evaluation_criteria": ["3 loops run without OOM", "Throughput ≥ 2× single-loop baseline"],
"risk": "medium"
},
{
"task_id": "T-05",
"name": "Telemetry + Cost Tracking",
"description": "Add token and time metrics per iteration; ensure cost < $0.10 and record to lab dashboard.",
"dependencies": ["T-04"],
"evaluation_criteria": ["Metrics persisted", "Alert on cost breach"],
"risk": "low"
}
],
"interface_contract": {
"artifacts_emitted": [".sisyphus/plans/*.md", "experiment_logs/*.json"],
"state_updates_for_project_loop": "Python orchestrator reads JSON stream and updates run_state.sqlite with status, score, cost, and artifact paths.",
"worker_instructions_format": "Markdown task blocks with `### Intent`, `### Constraints`, `### Deliverable`, followed by fenced code expectations."
},
"memory_actions": [
{
"layer": "artifact",
"action": "write",
"key": "omo_integration_decision_2026-03-14",
"value": "Chose hybrid Option D (plans + Ralph) for OMO integration due to balance of structure and autonomous retries."
}
],
"verification": {
"how_to_confirm_this_was_right": "Run 10-case benchmark after integration; expect mean score ≥ 0.60 and runtime cost report showing <$1 total.",
"observable_result": "CI pipeline passes with new integration tests and emits improved scores in results.json.",
"reversal_conditions": [
"Mean score stagnates (< 0.56) after 3 cycles",
"Integration causes >10 % regression in throughput",
"Major OMO update deprecates plan schema, breaking T-02 artefacts"
]
}
}
