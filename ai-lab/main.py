"""
main.py — The Orchestration Engine.

Implements the three nested loops from the architecture:

  ┌─ STRATEGIC LOOP (o1) ──────────────────────────────────────────┐
  │  Called once at startup and on escalation / stuck detection.   │
  │                                                                │
  │  ┌─ PROJECT LOOP (gpt-4o) ─────────────────────────────────┐  │
  │  │  Iterates over the task queue. Evaluates batch results.   │  │
  │  │                                                           │  │
  │  │  ┌─ EXPERIMENT LOOP (gpt-4o-mini / local) ────────────┐  │  │
  │  │  │  Worker → Critic → Retry or Escalate.               │  │  │
  │  │  └────────────────────────────────────────────────────┘  │  │
  │  └─────────────────────────────────────────────────────────┘  │
  └────────────────────────────────────────────────────────────────┘

Usage:
    python main.py "Design a lightweight carbon-fibre prosthetic ankle joint"
"""

from __future__ import annotations

import logging
import sys

from config import Thresholds, Paths
from state import SystemState
import planner
import worker
import critic
import memory
from memory import EpisodicMemory
import opencode_executor
import tools

# ── Persistent episodic memory (Layer 3) ──────────────────────
episodic_memory = EpisodicMemory()

# ── Eval harness gate (optional — runs when cases file exists) ────
_EVAL_CASES = Paths.ROOT / "evals" / "knowledge_plane" / "cases.jsonl"
_EVAL_SCORE_THRESHOLD = float(__import__("os").environ.get("EVAL_SCORE_THRESHOLD", "0.56"))

# ── OpenCode execution mode ───────────────────────────────────────
# Set OPENCODE_EXECUTOR=1 to route experiment-loop tasks through
# opencode run --format json instead of the built-in worker.
_USE_OPENCODE = __import__("os").environ.get("OPENCODE_EXECUTOR", "") == "1"
_OPENCODE_AGENT = __import__("os").environ.get("OPENCODE_AGENT", "")  # e.g. "sisyphus"
_OPENCODE_MODEL = __import__("os").environ.get("OPENCODE_MODEL", "")  # e.g. "openai/gpt-5.3-codex"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

Paths.ensure_dirs()

# ── State checkpoint path ────────────────────────────────────────
_STATE_FILE = Paths.STATE_DB.with_suffix(".json")


def run_eval_gate() -> tuple[float, bool, dict]:
    """
    Run the eval harness and return (score, passed, details).

    Returns per-metric averages for T-03 template matching:
        avg_support_recall, avg_gold_fact_coverage, avg_schema_ok, avg_citations_ok

    Returns (0.0, True, {}) if eval harness is not available.
    """
    if not _EVAL_CASES.exists():
        return 0.0, True, {}

    try:
        import json
        import os
        import subprocess

        result = subprocess.run(
            [
                "uv", "run", "python", "-m", "evals.knowledge_plane.runner",
                "--cases", str(_EVAL_CASES),
                "--arm", "local",
                "--model", os.environ.get("KNOWLEDGE_PLANE_MODEL", "gpt-4o-mini"),
                "--local-backend", "evals.knowledge_plane.local_backend:RepoSearchBackend",
            ],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(Paths.ROOT),
        )

        if result.returncode != 0:
            logger.warning("📊 Eval harness failed: %s", result.stderr[:300])
            return 0.0, True, {}

        # Parse output — first JSON block is summary, rest are per-case
        blocks = result.stdout.split("\n\n")
        summary = json.loads(blocks[0])
        avg = summary.get("avg_case_score", 0.0)
        passed = avg >= _EVAL_SCORE_THRESHOLD

        # Extract per-metric averages from per-case results
        details = {"avg_case_score": avg}
        if len(blocks) > 1:
            recalls, facts, schemas, citations = [], [], [], []
            for block in blocks[1:]:
                block = block.strip()
                if not block:
                    continue
                try:
                    case = json.loads(block)
                    rg = case.get("retrieval_grade", {})
                    recalls.append(rg.get("support_recall", 0.0))
                    fg = case.get("fact_grade", {})
                    facts.append(fg.get("gold_fact_coverage", 0.0))
                    sg = case.get("schema_grade", {})
                    schemas.append(1.0 if sg.get("schema_ok") else 0.0)
                    cg = case.get("citation_grade", {})
                    citations.append(1.0 if cg.get("citations_ok") else 0.0)
                except (json.JSONDecodeError, TypeError):
                    continue
            if recalls:
                details["avg_support_recall"] = sum(recalls) / len(recalls)
                details["avg_gold_fact_coverage"] = sum(facts) / len(facts)
                details["avg_schema_ok"] = sum(schemas) / len(schemas)
                details["avg_citations_ok"] = sum(citations) / len(citations)

        logger.info(
            "📊 Eval gate: %.4f (threshold=%.2f) → %s",
            avg, _EVAL_SCORE_THRESHOLD, "PASS" if passed else "FAIL"
        )
        return avg, passed, details

    except Exception as e:
        logger.warning("📊 Eval gate skipped (error: %s)", e)
        return 0.0, True, {}


def load_or_create_state(goal: str) -> SystemState:
    if _STATE_FILE.exists():
        state = SystemState.load(_STATE_FILE)
        if state.current_goal == goal:
            logger.info("Resuming from checkpoint (loop #%d).", state.loop_iteration)
            return state
    state = SystemState(current_goal=goal)
    # Inject persisted heuristics into the working constraints
    state.heuristics = memory.retrieve_skills(top_k=10)
    # Log episodic memory status
    ep_count = len(episodic_memory.entries)
    if ep_count:
        logger.info("📓 Loaded %d episodic entries from prior runs.", ep_count)
    else:
        logger.info("📓 No prior episodic memory — starting fresh.")
    return state


def experiment_loop(
    state: SystemState,
    task: str,
    success_criteria: list[str] | None = None,
) -> tuple[SystemState, bool]:
    """
    Inner loop: try a task, evaluate, retry with hints on failure.
    Returns (updated_state, success_flag).

    When OPENCODE_EXECUTOR=1, routes execution through opencode run
    instead of the built-in worker. OpenCode handles its own retries
    via OMO agent loops, so we run it once and check the result.
    """
    # ── OpenCode execution path ───────────────────────────────────
    if _USE_OPENCODE and opencode_executor.is_available():
        logger.info("[OPENCODE] Executing task via OpenCode: %s", task[:80])
        result = opencode_executor.run_task(
            task,
            agent=_OPENCODE_AGENT or None,
            model=_OPENCODE_MODEL or None,
        )

        if result.success:
            logger.info(
                "✅ OpenCode task completed: %d steps, %d tokens, $%.4f, files=%s",
                result.steps, result.total_tokens, result.total_cost,
                result.files_changed or "none",
            )
            # Record as successful experiment
            from state import ExperimentResult
            exp_meta = {
                "executor": "opencode",
                "agent": _OPENCODE_AGENT or "default",
                "session_id": result.session_id,
                "tokens": result.total_tokens,
                "cost": result.total_cost,
                "files_changed": result.files_changed,
                "tools_used": [t["tool"] for t in result.tools_used],
            }
            state.record_experiment(ExperimentResult(
                hypothesis=task,
                outcome="success",
                output=result.text_output[:2000],
                metadata=exp_meta,
            ))
            # Persist to episodic memory (Layer 3)
            episodic_memory.record(
                goal=state.current_goal,
                hypothesis=task,
                action=f"opencode:{_OPENCODE_AGENT or 'default'}",
                outcome="success",
                metadata=exp_meta,
            )
            return state, True
        else:
            logger.warning(
                "❌ OpenCode task failed: %s", result.error or "no DONE signal"
            )
            fail_meta = {"executor": "opencode", "session_id": result.session_id}
            state.record_experiment(ExperimentResult(
                hypothesis=task,
                outcome="failure",
                output=result.error or result.text_output[:2000],
                metadata=fail_meta,
            ))
            episodic_memory.record(
                goal=state.current_goal,
                hypothesis=task,
                action=f"opencode:{_OPENCODE_AGENT or 'default'}",
                outcome="failure",
                metadata=fail_meta,
            )
            return state, False

    # ── Built-in worker path ──────────────────────────────────────
    improvement_hint = ""
    criteria = success_criteria or [
        "Output is directly relevant to the stated task.",
        "Output is complete and actionable.",
        "No hallucinated facts or contradictions with constraints.",
    ]

    for attempt in range(Thresholds.ESCALATE_TO_STRATEGIC_AFTER):
        output = worker.run_task(state, task, improvement_hint=improvement_hint)
        verdict = critic.evaluate(state, task, output, criteria)

        if verdict.passed:
            logger.info("✅ Task passed on attempt %d.", attempt + 1)
            episodic_memory.record(
                goal=state.current_goal,
                hypothesis=task,
                action=f"worker:attempt-{attempt + 1}",
                outcome="success",
                metadata={"score": verdict.score, "attempts": attempt + 1},
            )
            return state, True
        else:
            logger.info(
                "❌ Attempt %d failed (score=%.2f). Issues: %s",
                attempt + 1,
                verdict.score,
                verdict.issues,
            )
            improvement_hint = verdict.improvement_suggestion

    logger.warning("⚠️  Task failed after %d attempts → escalating.", attempt + 1)
    episodic_memory.record(
        goal=state.current_goal,
        hypothesis=task,
        action=f"worker:exhausted-{Thresholds.ESCALATE_TO_STRATEGIC_AFTER}-attempts",
        outcome="failure",
        metadata={"last_score": verdict.score, "issues": verdict.issues},
    )
    return state, False


def project_loop(state: SystemState) -> SystemState:
    """
    Middle loop: process task queue, escalate stuck tasks to planner.
    """
    while state.task_queue:
        if state.loop_iteration >= Thresholds.MAX_PROJECT_ITERATIONS:
            raise RuntimeError(
                "Project loop exceeded MAX_PROJECT_ITERATIONS. "
                "Stopping to prevent infinite execution."
            )

        task_id = state.task_queue.pop(0)
        task_def = next(
            (t for t in state.project_graph if t["id"] == task_id),
            {"name": task_id, "description": task_id},
        )
        task_description = task_def.get("description", task_id)
        task_criteria = task_def.get("evaluation_criteria", [])
        if not isinstance(task_criteria, list):
            task_criteria = []
        state.active_hypothesis = task_description

        logger.info("── Project Loop: starting task [%s] %s", task_id, task_def["name"])

        # T-02: Step 4 — Git commit (snapshot before change)
        score_before, _, _ = run_eval_gate()
        snapshot = tools.git_commit_snapshot(
            message=f"auto: snapshot before [{task_id}] {task_def['name']}"
        )
        if snapshot["success"]:
            logger.info("📸 Git snapshot: %s", snapshot["commit_hash"])
        else:
            logger.warning("📸 Git snapshot failed: %s", snapshot.get("error", "unknown"))

        state, success = experiment_loop(
            state,
            task_description,
            success_criteria=task_criteria,
        )

        if success:
            state.completed_tasks.append(task_id)
            state.task_replan_counts.pop(task_id, None)

            # T-02: Step 6 — Run eval harness, compare before/after
            score_after, eval_passed, eval_details = run_eval_gate()

            if not eval_passed and score_before > 0 and score_after < score_before:
                # T-02: Score regressed → git revert
                logger.warning(
                    "📊 Eval REGRESSION after task %s (%.4f → %.4f). Reverting.",
                    task_id, score_before, score_after,
                )
                revert_result = tools.git_revert_last()
                if revert_result["success"]:
                    logger.info("⏪ Reverted commit %s", revert_result["reverted_hash"])
                else:
                    logger.error("⏪ Revert failed: %s", revert_result.get("error"))

                # Record revert in episodic memory
                episodic_memory.record(
                    goal=state.current_goal,
                    hypothesis=task_description,
                    action=f"git-revert:{revert_result.get('reverted_hash', '?')}",
                    outcome="failure",
                    score_before=score_before,
                    score_after=score_after,
                    kept=False,
                    metadata={"task_id": task_id, "revert": revert_result},
                )

                state.last_error = f"Eval gate regression: {score_after:.4f} < {score_before:.4f}"
                state = planner.diagnose_failures(state)
            elif not eval_passed:
                # Eval failed but no clear regression (e.g., first run)
                logger.warning(
                    "📊 Eval gate FAILED after task %s (score=%.4f < %.2f). "
                    "Escalating to strategic tier.",
                    task_id, score_after, _EVAL_SCORE_THRESHOLD,
                )
                episodic_memory.record(
                    goal=state.current_goal,
                    hypothesis=task_description,
                    action=f"git-keep:{snapshot.get('commit_hash', '?')}",
                    outcome="partial",
                    score_before=score_before,
                    score_after=score_after,
                    kept=True,
                    metadata={"task_id": task_id, "reason": "below threshold but no regression"},
                )
                state.last_error = f"Eval gate regression: {score_after:.4f} < {_EVAL_SCORE_THRESHOLD}"
                state = planner.diagnose_failures(state)
            else:
                # T-02: Score held or improved → keep change
                logger.info(
                    "✅ Eval gate PASSED after task %s (%.4f → %.4f). Keeping change.",
                    task_id, score_before, score_after,
                )
                episodic_memory.record(
                    goal=state.current_goal,
                    hypothesis=task_description,
                    action=f"git-keep:{snapshot.get('commit_hash', '?')}",
                    outcome="success",
                    score_before=score_before,
                    score_after=score_after,
                    kept=True,
                    metadata={"task_id": task_id},
                )

            # Unlock dependent tasks
            for t in state.project_graph:
                if task_id in t.get("depends_on", []):
                    all_deps_done = all(
                        d in state.completed_tasks for d in t["depends_on"]
                    )
                    if all_deps_done and t["id"] not in state.task_queue:
                        state.task_queue.append(t["id"])
        else:
            state.task_replan_counts[task_id] = state.task_replan_counts.get(task_id, 0) + 1
            if (
                state.task_replan_counts[task_id]
                > Thresholds.MAX_STRATEGIC_REPLANS_PER_TASK
            ):
                raise RuntimeError(
                    f"Task {task_id} exceeded MAX_STRATEGIC_REPLANS_PER_TASK="
                    f"{Thresholds.MAX_STRATEGIC_REPLANS_PER_TASK}. "
                    "Manual intervention required."
                )

            # Escalate to strategic planner for diagnosis
            state = planner.diagnose_failures(state)
            # Re-queue the task with the new hypothesis
            state.task_queue.insert(0, task_id)

        state.loop_iteration += 1
        state.save(_STATE_FILE)
        logger.info("State checkpoint saved.")

    return state


def strategic_loop(goal: str) -> SystemState:
    """
    Outer loop: plan → project → (escalate back to plan if stuck).
    """
    state = load_or_create_state(goal)

    if not state.project_graph:
        logger.info("══ Strategic Loop: building project graph via o1.")
        state = planner.build_project_graph(state)
        if not state.task_queue:
            raise RuntimeError("Planner returned no executable tasks.")
        # T-01: Emit .sisyphus plan for OMO Atlas execution
        plan_path = planner.emit_sisyphus_plan(state)
        logger.info("══ Plan emitted: %s", plan_path)

        # If OpenCode executor is active, execute the plan directly
        if _USE_OPENCODE and opencode_executor.is_available():
            logger.info("══ Executing plan via OpenCode agent=%s", _OPENCODE_AGENT or "default")
            plan_result = opencode_executor.run_plan(
                plan_path,
                agent=_OPENCODE_AGENT or "sisyphus",
                model=_OPENCODE_MODEL or None,
                timeout=600,
            )
            if plan_result.success:
                logger.info("══ Plan executed successfully via OpenCode (%d steps, $%.4f)",
                            plan_result.steps, plan_result.total_cost)
            else:
                logger.warning("══ Plan execution failed: %s", plan_result.error)
        state.save(_STATE_FILE)

    logger.info("══ Entering project loop with %d tasks.", len(state.task_queue))
    state = project_loop(state)

    logger.info("══ All tasks complete. Goal achieved.")
    return state


# ════════════════════════════════════════════════════════════════
#  Autonomous Self-Improvement Loop (T-05)
#
#  The Oracle's loop: analyze → hypothesis → plan → git commit →
#  execute → eval → keep/revert → episodic → heuristic → repeat
# ════════════════════════════════════════════════════════════════

_MAX_IMPROVEMENT_CYCLES = int(__import__("os").environ.get("MAX_IMPROVEMENT_CYCLES", "5"))


def autonomous_improvement_loop(max_cycles: int | None = None) -> dict:
    """
    Run the autonomous self-improvement loop.

    Each cycle:
      1. Run eval harness → get per-metric scores
      2. Select improvement template (weakest metric)
      3. Git snapshot (before change)
      4. Execute improvement via OpenCode or built-in worker
      5. Run eval harness again (compare before/after)
      6. Keep or revert based on score delta
      7. Record in episodic memory (kept=True/False)
      8. Save heuristic on successful improvement

    Returns summary dict with cycle results.
    """
    cycles = max_cycles or _MAX_IMPROVEMENT_CYCLES
    results = []

    logger.info("═══ Autonomous Improvement Loop: %d cycles ═══", cycles)

    for cycle in range(1, cycles + 1):
        logger.info("── Cycle %d/%d ──", cycle, cycles)

        # Step 1: Analyze eval results
        score_before, _, eval_details = run_eval_gate()
        if score_before == 0.0 and not eval_details:
            logger.warning("📊 No eval harness available. Stopping.")
            break

        logger.info("📊 Current score: %.4f | Metrics: %s",
                     score_before,
                     {k: f"{v:.3f}" for k, v in eval_details.items() if k != "avg_case_score"})

        # Step 2: Select improvement template, or LLM fallback (T-06)
        template = planner.select_improvement(eval_details)
        if template is None:
            logger.info("📋 No template matches. Trying LLM fallback (T-06)...")
            template = planner.generate_novel_improvement(
                eval_details,
                episodic_summary=episodic_memory.summary(),
                heuristics=memory.retrieve_heuristics(top_k=5),
            )
        if template is None:
            logger.info("✅ No improvements found (templates or LLM). Stopping.")
            results.append({"cycle": cycle, "action": "none", "reason": "no improvement available"})
            break

        task_description = planner.format_improvement_task(template)
        logger.info("📋 Template %s: %s", template["id"], template["condition"])

        # Step 3: Git snapshot
        snapshot = tools.git_commit_snapshot(
            message=f"auto: snapshot before improvement cycle {cycle} [{template['id']}]"
        )
        if snapshot["success"]:
            logger.info("📸 Snapshot: %s", snapshot["commit_hash"])

        # Step 4: Execute improvement
        state = load_or_create_state(f"autonomous-improvement-cycle-{cycle}")
        state.active_hypothesis = template["hypothesis"]

        state, success = experiment_loop(state, task_description)

        if not success:
            logger.warning("❌ Cycle %d: experiment failed. Skipping eval.", cycle)
            episodic_memory.record(
                goal="autonomous-improvement",
                hypothesis=template["hypothesis"],
                action=f"cycle-{cycle}:experiment-failed",
                outcome="failure",
                score_before=score_before,
                metadata={"template_id": template["id"], "cycle": cycle},
            )
            results.append({"cycle": cycle, "action": "failed", "template": template["id"]})
            continue

        # Step 5: Run eval again
        score_after, _, details_after = run_eval_gate()
        delta = round(score_after - score_before, 6)
        logger.info("📊 Score: %.4f → %.4f (Δ%+.4f)", score_before, score_after, delta)

        # Step 6: Keep or revert
        if delta >= 0:
            # Keep
            logger.info("✅ Cycle %d: KEEP (Δ%+.4f)", cycle, delta)
            episodic_memory.record(
                goal="autonomous-improvement",
                hypothesis=template["hypothesis"],
                action=f"cycle-{cycle}:keep:{snapshot.get('commit_hash', '?')}",
                outcome="success",
                score_before=score_before,
                score_after=score_after,
                kept=True,
                metadata={"template_id": template["id"], "cycle": cycle},
            )
            # Step 7: Save heuristic
            memory.save_heuristic(
                metric=template["metric"],
                action=template["action"],
                score_before=score_before,
                score_after=score_after,
                template_id=template["id"],
            )
            results.append({"cycle": cycle, "action": "keep", "delta": delta, "template": template["id"]})
        else:
            # Revert
            logger.warning("⏪ Cycle %d: REVERT (Δ%+.4f)", cycle, delta)
            revert = tools.git_revert_last()
            episodic_memory.record(
                goal="autonomous-improvement",
                hypothesis=template["hypothesis"],
                action=f"cycle-{cycle}:revert:{revert.get('reverted_hash', '?')}",
                outcome="failure",
                score_before=score_before,
                score_after=score_after,
                kept=False,
                metadata={"template_id": template["id"], "cycle": cycle},
            )
            results.append({"cycle": cycle, "action": "revert", "delta": delta, "template": template["id"]})

    # Summary
    keeps = sum(1 for r in results if r.get("action") == "keep")
    reverts = sum(1 for r in results if r.get("action") == "revert")
    total_delta = sum(r.get("delta", 0) for r in results if r.get("action") == "keep")

    logger.info(
        "═══ Autonomous Loop Complete: %d cycles, %d kept, %d reverted, net Δ%+.4f ═══",
        len(results), keeps, reverts, total_delta,
    )

    return {
        "cycles": results,
        "keeps": keeps,
        "reverts": reverts,
        "net_delta": total_delta,
        "episodic_entries": len(episodic_memory.entries),
        "heuristics_saved": len(memory.load_heuristics()),
    }


if __name__ == "__main__":
    import os

    if os.environ.get("AUTONOMOUS_LOOP") == "1":
        # Run the autonomous self-improvement loop
        max_cycles = int(os.environ.get("MAX_IMPROVEMENT_CYCLES", "5"))
        summary = autonomous_improvement_loop(max_cycles)
        print("\n── AUTONOMOUS LOOP RESULTS ──")
        for r in summary["cycles"]:
            action = r["action"].upper()
            delta = f" Δ{r.get('delta', 0):+.4f}" if "delta" in r else ""
            tpl = f" [{r.get('template', '')}]" if "template" in r else ""
            print(f"  Cycle {r['cycle']}: {action}{delta}{tpl}")
        print(f"\n  Kept: {summary['keeps']} | Reverted: {summary['reverts']} | Net: Δ{summary['net_delta']:+.4f}")
        print(f"  Episodic entries: {summary['episodic_entries']} | Heuristics: {summary['heuristics_saved']}")
    else:
        goal = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Research task"
        final_state = strategic_loop(goal)
        print("\n── COMPLETED TASKS ──")
        for t in final_state.completed_tasks:
            print(f"  ✅ {t}")
        print(f"\nArtifacts saved to: {Paths.ARTIFACTS}")
