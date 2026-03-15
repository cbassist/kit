"""
daemon.py — The 01 Lab agent daemon.

Always-running service that:
  1. Polls the goal queue for new goals
  2. Runs the appropriate loop (strategic or autonomous improvement)
  3. Reports results back to the goal queue
  4. Survives crashes via external watchdog (launchd/systemd)

Usage:
    python daemon.py                    # Run daemon (foreground)
    python daemon.py --submit "goal"    # Submit a goal to the queue
    python daemon.py --status           # Show queue status
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("01-daemon")

# Import after logging setup
import db
import main as engine

# ── Graceful shutdown ──────────────────────────────────────────
_running = True


def _handle_signal(signum, frame):
    global _running
    logger.info("🛑 Received signal %d. Shutting down gracefully...", signum)
    _running = False


signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)

# ── Configuration ──────────────────────────────────────────────
POLL_INTERVAL = int(__import__("os").environ.get("DAEMON_POLL_INTERVAL", "10"))
HEARTBEAT_INTERVAL = 60  # log heartbeat every N seconds


def run_goal(goal: db.Goal) -> dict:
    """Execute a goal through the engine and return results."""
    logger.info("═══ Starting goal #%s: %s ═══", goal.id, goal.goal[:80])

    try:
        # Check if this is an autonomous improvement request
        if goal.goal.lower().startswith("improve") or goal.goal.lower().startswith("autonomous"):
            max_cycles = goal.priority if goal.priority > 5 else 5
            result = engine.autonomous_improvement_loop(max_cycles=max_cycles)
            return {"type": "autonomous", **result}
        else:
            # Standard strategic loop
            state = engine.strategic_loop(goal.goal)
            return {
                "type": "strategic",
                "completed_tasks": state.completed_tasks,
                "loop_iterations": state.loop_iteration,
                "experiments": len(state.recent_experiments),
            }
    except Exception as e:
        logger.error("❌ Goal #%s failed: %s", goal.id, e)
        return {"type": "error", "error": str(e)}


def daemon_loop():
    """Main daemon loop — poll for goals, execute, repeat."""
    logger.info("🚀 01 Lab Daemon starting. Poll interval: %ds", POLL_INTERVAL)

    last_heartbeat = time.time()

    while _running:
        # Check for next goal
        goal = db.next_goal()

        if goal:
            result = run_goal(goal)
            status = "done" if result.get("type") != "error" else "failed"
            db.complete_goal(goal.id, status=status, result=result)
            logger.info("═══ Goal #%s completed: %s ═══", goal.id, status)
        else:
            # Heartbeat
            now = time.time()
            if now - last_heartbeat >= HEARTBEAT_INTERVAL:
                queued = db.list_goals(status="queued")
                logger.info("💓 Heartbeat — %d goals queued, waiting...", len(queued))
                last_heartbeat = now

            time.sleep(POLL_INTERVAL)

    logger.info("🛑 Daemon stopped.")


def cli():
    """CLI interface for submitting goals and checking status."""
    parser = argparse.ArgumentParser(description="01 Lab Agent Daemon")
    parser.add_argument("--submit", type=str, help="Submit a goal to the queue")
    parser.add_argument("--priority", type=int, default=50, help="Goal priority (0-100)")
    parser.add_argument("--source", type=str, default="cli", help="Goal source tag")
    parser.add_argument("--status", action="store_true", help="Show queue status")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon (default if no args)")

    args = parser.parse_args()

    if args.submit:
        goal = db.submit_goal(args.submit, priority=args.priority, source=args.source)
        print(f"✅ Goal #{goal.id} submitted: {goal.goal}")
        return

    if args.status:
        print("── Goal Queue ──")
        for status in ["running", "queued", "done", "failed"]:
            goals = db.list_goals(status=status)
            if goals:
                print(f"\n{status.upper()} ({len(goals)}):")
                for g in goals[:10]:
                    print(f"  #{g.id} [{g.priority}] {g.goal[:60]}")
        return

    # Default: run daemon
    daemon_loop()


if __name__ == "__main__":
    cli()
