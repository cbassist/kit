"""
db.py — Persistence layer for the 01 Lab.

Abstracts storage behind a simple interface. Supports two backends:
  - JSON files (default, no dependencies)
  - Supabase Postgres (when DATABASE_URL is set)

All other modules call db.* instead of reading/writing files directly.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from config import Paths

logger = logging.getLogger(__name__)

# ── Backend detection ──────────────────────────────────────────
DATABASE_URL = os.environ.get("DATABASE_URL", "")
_USE_POSTGRES = bool(DATABASE_URL)

_pg_conn = None


def _get_pg():
    """Lazy Postgres connection."""
    global _pg_conn
    if _pg_conn is None:
        import psycopg
        _pg_conn = psycopg.connect(DATABASE_URL, autocommit=True)
        logger.info("[DB] Connected to Postgres")
    return _pg_conn


# ════════════════════════════════════════════════════════════════
#  Goal Queue
# ════════════════════════════════════════════════════════════════

@dataclass
class Goal:
    id: int | None = None
    goal: str = ""
    status: str = "queued"  # queued | running | done | failed
    priority: int = 50
    source: str = "cli"     # cli | telegram | slack | web | cron
    result: dict | None = None
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None


_GOALS_FILE = Paths.ROOT / "goals.json"


def _load_goals() -> list[dict]:
    if _GOALS_FILE.exists():
        text = _GOALS_FILE.read_text().strip()
        if text:
            return json.loads(text)
    return []


def _save_goals(goals: list[dict]) -> None:
    _GOALS_FILE.write_text(json.dumps(goals, indent=2, default=str))


def submit_goal(goal_text: str, priority: int = 50, source: str = "cli") -> Goal:
    """Add a new goal to the queue."""
    goal = Goal(goal=goal_text, priority=priority, source=source)

    if _USE_POSTGRES:
        conn = _get_pg()
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO goals (goal, status, priority, source) VALUES (%s, %s, %s, %s) RETURNING id",
                (goal.goal, goal.status, goal.priority, goal.source),
            )
            goal.id = cur.fetchone()[0]
    else:
        goals = _load_goals()
        goal.id = len(goals) + 1
        goals.append(asdict(goal))
        _save_goals(goals)

    logger.info("[GOAL] Submitted: #%s '%s' (priority=%d, source=%s)",
                goal.id, goal.goal[:60], goal.priority, goal.source)
    return goal


def next_goal() -> Goal | None:
    """Get the highest-priority queued goal, mark it as running."""
    if _USE_POSTGRES:
        conn = _get_pg()
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE goals SET status='running', started_at=NOW() "
                "WHERE id = (SELECT id FROM goals WHERE status='queued' ORDER BY priority DESC, id ASC LIMIT 1) "
                "RETURNING id, goal, status, priority, source",
            )
            row = cur.fetchone()
            if row:
                return Goal(id=row[0], goal=row[1], status=row[2], priority=row[3], source=row[4])
            return None
    else:
        goals = _load_goals()
        queued = [g for g in goals if g["status"] == "queued"]
        if not queued:
            return None
        queued.sort(key=lambda g: g.get("priority", 50), reverse=True)
        pick = queued[0]
        pick["status"] = "running"
        pick["started_at"] = time.time()
        _save_goals(goals)
        return Goal(**{k: v for k, v in pick.items() if k in Goal.__dataclass_fields__})


def complete_goal(goal_id: int, status: str = "done", result: dict | None = None) -> None:
    """Mark a goal as done or failed."""
    if _USE_POSTGRES:
        conn = _get_pg()
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE goals SET status=%s, result=%s, completed_at=NOW() WHERE id=%s",
                (status, json.dumps(result or {}), goal_id),
            )
    else:
        goals = _load_goals()
        for g in goals:
            if g.get("id") == goal_id:
                g["status"] = status
                g["result"] = result
                g["completed_at"] = time.time()
                break
        _save_goals(goals)
    logger.info("[GOAL] #%s → %s", goal_id, status)


def list_goals(status: str | None = None) -> list[Goal]:
    """List goals, optionally filtered by status."""
    if _USE_POSTGRES:
        conn = _get_pg()
        with conn.cursor() as cur:
            if status:
                cur.execute("SELECT id, goal, status, priority, source FROM goals WHERE status=%s ORDER BY priority DESC", (status,))
            else:
                cur.execute("SELECT id, goal, status, priority, source FROM goals ORDER BY id DESC LIMIT 50")
            return [Goal(id=r[0], goal=r[1], status=r[2], priority=r[3], source=r[4]) for r in cur.fetchall()]
    else:
        goals = _load_goals()
        if status:
            goals = [g for g in goals if g.get("status") == status]
        return [Goal(**{k: v for k, v in g.items() if k in Goal.__dataclass_fields__}) for g in goals]
