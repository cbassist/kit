"""
api.py — FastAPI server for the 01 Lab.

Exposes:
  - POST /goals          — submit a goal (from any source)
  - GET  /goals          — list goals
  - GET  /status         — current daemon status + cost summary
  - POST /telegram       — Telegram webhook endpoint

Also runs a background thread that pushes results back to messaging
platforms when goals complete.

Usage:
    uvicorn api:app --host 0.0.0.0 --port 8100
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import httpx

import db
import llm
from memory import EpisodicMemory
from config import Paths

logger = logging.getLogger(__name__)

app = FastAPI(title="01 Lab Agent", version="0.1.0")

# ── Telegram config ────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_IDS = os.environ.get("TELEGRAM_CHAT_IDS", "")  # comma-separated allowed chat IDs


def _telegram_api(method: str, **kwargs) -> dict:
    """Call Telegram Bot API."""
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("[TELEGRAM] Bot token not configured")
        return {}
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}"
    try:
        resp = httpx.post(url, json=kwargs, timeout=10)
        return resp.json()
    except Exception as e:
        logger.error("[TELEGRAM] API call failed: %s", e)
        return {}


def send_telegram(chat_id: int | str, text: str) -> dict:
    """Send a message to a Telegram chat."""
    return _telegram_api("sendMessage", chat_id=chat_id, text=text, parse_mode="Markdown")


def _is_allowed_chat(chat_id: int | str) -> bool:
    """Check if a chat ID is in the allowed list. Empty list = allow all."""
    if not TELEGRAM_CHAT_IDS:
        return True  # No restriction configured
    allowed = [s.strip() for s in TELEGRAM_CHAT_IDS.split(",")]
    return str(chat_id) in allowed


# ════════════════════════════════════════════════════════════════
#  API Routes
# ════════════════════════════════════════════════════════════════

@app.post("/goals")
async def submit_goal(request: Request):
    """Submit a goal from any source."""
    body = await request.json()
    goal_text = body.get("goal", "").strip()
    if not goal_text:
        return JSONResponse({"error": "goal is required"}, status_code=400)

    goal = db.submit_goal(
        goal_text,
        priority=body.get("priority", 50),
        source=body.get("source", "api"),
    )
    return {"ok": True, "goal_id": goal.id, "goal": goal.goal}


@app.get("/goals")
async def list_goals(status: str | None = None):
    """List goals, optionally filtered by status."""
    goals = db.list_goals(status=status)
    return {
        "goals": [
            {"id": g.id, "goal": g.goal, "status": g.status, "priority": g.priority, "source": g.source}
            for g in goals
        ]
    }


@app.get("/status")
async def get_status():
    """Current system status."""
    cost = llm.get_cost_summary()
    queued = db.list_goals(status="queued")
    running = db.list_goals(status="running")
    done = db.list_goals(status="done")
    return {
        "queued": len(queued),
        "running": len(running),
        "done": len(done),
        "cost": cost,
        "running_goals": [{"id": g.id, "goal": g.goal[:80]} for g in running],
    }


# ════════════════════════════════════════════════════════════════
#  Status Feed + Session History
# ════════════════════════════════════════════════════════════════

@app.get("/episodes")
async def get_episodes(n: int = 20):
    """Recent episodic memory entries."""
    ep = EpisodicMemory()
    entries = ep.recent(n)
    return {
        "total": len(ep.entries),
        "episodes": [
            {
                "cycle_id": e.cycle_id,
                "goal": e.goal,
                "hypothesis": e.hypothesis[:100],
                "outcome": e.outcome,
                "score_before": e.score_before,
                "score_after": e.score_after,
                "score_delta": e.score_delta,
                "kept": e.kept,
                "timestamp": e.timestamp,
            }
            for e in entries
        ],
    }


@app.get("/heuristics")
async def get_heuristics():
    """Learned heuristics from successful improvements."""
    import memory
    heuristics = memory.retrieve_heuristics(top_k=20)
    return {"count": len(heuristics), "heuristics": heuristics}


@app.get("/sessions")
async def get_sessions():
    """Group episodic entries by goal to show session history."""
    ep = EpisodicMemory()
    sessions: dict[str, list] = {}
    for e in ep.entries:
        key = e.goal
        if key not in sessions:
            sessions[key] = []
        sessions[key].append({
            "cycle_id": e.cycle_id,
            "outcome": e.outcome,
            "score_delta": e.score_delta,
            "kept": e.kept,
            "timestamp": e.timestamp,
        })
    return {
        "session_count": len(sessions),
        "sessions": [
            {
                "goal": goal,
                "episodes": entries,
                "total_delta": sum(e.get("score_delta", 0) or 0 for e in entries),
                "keeps": sum(1 for e in entries if e.get("kept") is True),
                "reverts": sum(1 for e in entries if e.get("kept") is False),
            }
            for goal, entries in sessions.items()
        ],
    }


from fastapi.responses import StreamingResponse


@app.get("/stream")
async def status_stream():
    """Server-Sent Events stream of system status. Connect and watch in real-time."""
    async def event_generator():
        last_ep_count = 0
        while True:
            ep = EpisodicMemory()
            cost = llm.get_cost_summary()
            queued = db.list_goals(status="queued")
            running = db.list_goals(status="running")

            data = json.dumps({
                "queued": len(queued),
                "running": len(running),
                "running_goals": [{"id": g.id, "goal": g.goal[:60]} for g in running],
                "episodes": len(ep.entries),
                "cost": cost,
            })

            yield f"data: {data}\n\n"

            # Push new episodes as they happen
            if len(ep.entries) > last_ep_count:
                for e in ep.entries[last_ep_count:]:
                    ep_data = json.dumps({
                        "type": "episode",
                        "cycle_id": e.cycle_id,
                        "outcome": e.outcome,
                        "score_delta": e.score_delta,
                        "kept": e.kept,
                        "hypothesis": e.hypothesis[:80],
                    })
                    yield f"data: {ep_data}\n\n"
                last_ep_count = len(ep.entries)

            await asyncio.sleep(5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ════════════════════════════════════════════════════════════════
#  Telegram Webhook
# ════════════════════════════════════════════════════════════════

@app.post("/telegram")
async def telegram_webhook(request: Request):
    """
    Receive Telegram messages and submit them as goals.

    Setup: Set webhook via:
      curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
           -d '{"url": "https://your-domain/telegram"}'
    """
    body = await request.json()
    message = body.get("message", {})
    text = message.get("text", "").strip()
    chat_id = message.get("chat", {}).get("id")
    user_name = message.get("from", {}).get("first_name", "User")

    if not text or not chat_id:
        return {"ok": True}

    if not _is_allowed_chat(chat_id):
        send_telegram(chat_id, "⛔ Not authorized. Contact the admin.")
        return {"ok": True}

    # Handle commands
    if text.startswith("/"):
        return await _handle_telegram_command(text, chat_id, user_name)

    # Default: submit as goal
    goal = db.submit_goal(text, source="telegram", reply_to=str(chat_id))
    send_telegram(chat_id, f"✅ Goal #{goal.id} queued: _{text}_")
    return {"ok": True}


async def _handle_telegram_command(text: str, chat_id: int, user_name: str):
    """Handle Telegram bot commands."""
    cmd = text.split()[0].lower()

    if cmd == "/start":
        send_telegram(chat_id, (
            "🤖 *01 Lab Agent*\n\n"
            "Send me a message and I'll add it as a goal.\n\n"
            "Commands:\n"
            "/status — what's running\n"
            "/goals — show queue\n"
            "/help — this message"
        ))
    elif cmd == "/status":
        cost = llm.get_cost_summary()
        queued = db.list_goals(status="queued")
        running = db.list_goals(status="running")
        msg = (
            f"📊 *Status*\n"
            f"Running: {len(running)}\n"
            f"Queued: {len(queued)}\n"
            f"Budget: ${cost['cumulative_usd']:.2f} / ${cost['cap_usd']:.2f} ({cost['pct_used']:.0f}%)"
        )
        if running:
            msg += "\n\n🏃 *Running:*\n"
            for g in running:
                msg += f"  #{g.id} {g.goal[:50]}\n"
        send_telegram(chat_id, msg)
    elif cmd == "/goals":
        goals = db.list_goals()
        if not goals:
            send_telegram(chat_id, "📭 No goals in queue.")
        else:
            lines = ["📋 *Goals:*"]
            for g in goals[:10]:
                icon = {"queued": "⏳", "running": "🏃", "done": "✅", "failed": "❌"}.get(g.status, "❓")
                lines.append(f"  {icon} #{g.id} [{g.priority}] {g.goal[:50]}")
            send_telegram(chat_id, "\n".join(lines))
    elif cmd == "/help":
        send_telegram(chat_id, (
            "Send any text → becomes a goal\n"
            "/status — system status\n"
            "/goals — show queue\n"
            "/start — intro"
        ))
    else:
        send_telegram(chat_id, f"Unknown command: {cmd}")

    return {"ok": True}


# ════════════════════════════════════════════════════════════════
#  Result Push (background thread)
# ════════════════════════════════════════════════════════════════

def _result_pusher():
    """
    Background thread that watches for completed goals and pushes
    results back to the originating messaging platform.
    """
    seen_done: set[int] = set()

    while True:
        try:
            done = db.list_goals(status="done") + db.list_goals(status="failed")
            for g in done:
                if g.id in seen_done:
                    continue
                seen_done.add(g.id)

                # Push result to originating platform
                if g.reply_to and g.source == "telegram":
                    icon = "✅" if g.status == "done" else "❌"
                    result_summary = ""
                    if g.result:
                        if g.result.get("type") == "autonomous":
                            result_summary = (
                                f"\nKept: {g.result.get('keeps', 0)} | "
                                f"Reverted: {g.result.get('reverts', 0)} | "
                                f"Net: Δ{g.result.get('net_delta', 0):+.4f}"
                            )
                        elif g.result.get("type") == "error":
                            result_summary = f"\nError: {g.result.get('error', '')[:200]}"
                    msg = f"{icon} Goal #{g.id} *{g.status}*: {g.goal[:60]}{result_summary}"
                    send_telegram(g.reply_to, msg)
                    logger.info("[PUSH] Sent result to telegram chat %s", g.reply_to)
        except Exception as e:
            logger.error("[PUSH] Error: %s", e)

        time.sleep(10)


# Start pusher thread when app loads
_pusher_thread = threading.Thread(target=_result_pusher, daemon=True)
_pusher_thread.start()
