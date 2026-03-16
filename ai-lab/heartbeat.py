"""
heartbeat.py — Kit Telegram Bot + Heartbeat Service

Always-running service on the VPS that:
  1. Listens for Telegram messages → submits goals to the queue
  2. Pushes results back when goals complete
  3. Heartbeat: periodic status pings if work is happening
  4. Command interface: /status, /goals, /kit, /help

This is the "single point of contact" — Mike texts from his phone,
the system does the work, texts back when done.

Usage:
    python heartbeat.py

Requires: TELEGRAM_BOT_TOKEN and TELEGRAM_ADMIN_CHAT_ID in .env
"""

from __future__ import annotations

import json
import logging
import os
import signal
import time
import threading

import httpx
from dotenv import load_dotenv

# Load .env
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("kit-heartbeat")

# ── Config ─────────────────────────────────────────────────────
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
ADMIN_CHAT_ID = os.environ.get("TELEGRAM_ADMIN_CHAT_ID", "")
HEARTBEAT_INTERVAL = int(os.environ.get("HEARTBEAT_INTERVAL", "300"))  # 5 min default
POLL_INTERVAL = 2  # Telegram long-polling interval

if not BOT_TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN not set. Cannot start heartbeat.")
    raise SystemExit(1)

# ── Telegram API ───────────────────────────────────────────────
_client = httpx.Client(timeout=30)
_API = f"https://api.telegram.org/bot{BOT_TOKEN}"


def tg_send(chat_id: str | int, text: str) -> dict:
    """Send a Telegram message."""
    try:
        r = _client.post(f"{_API}/sendMessage", json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
        })
        return r.json()
    except Exception as e:
        logger.error("[TG] Send failed: %s", e)
        return {}


def tg_get_updates(offset: int = 0) -> list:
    """Long-poll for new messages."""
    try:
        r = _client.post(f"{_API}/getUpdates", json={
            "offset": offset,
            "timeout": 20,
        }, timeout=30)
        data = r.json()
        return data.get("result", [])
    except Exception as e:
        logger.error("[TG] Poll failed: %s", e)
        return []


# ── Goal Queue (import from Kit) ──────────────────────────────
import sys
sys.path.insert(0, os.path.dirname(__file__))
import db
import llm


def handle_message(chat_id: int, text: str, user_name: str):
    """Process an incoming Telegram message."""
    text = text.strip()

    if not text:
        return

    # Commands
    if text.startswith("/"):
        handle_command(chat_id, text, user_name)
        return

    # Default: submit as goal
    goal = db.submit_goal(text, source="telegram", reply_to=str(chat_id))
    tg_send(chat_id, f"✅ Goal #{goal.id} queued: _{text}_")
    logger.info("[GOAL] %s submitted: %s", user_name, text[:60])


def handle_command(chat_id: int, text: str, user_name: str):
    """Handle bot commands."""
    cmd = text.split()[0].lower()
    args = text[len(cmd):].strip()

    if cmd == "/start" or cmd == "/help":
        tg_send(chat_id, (
            "🤖 *Kit Agent*\n\n"
            "Send any message → becomes a goal\n\n"
            "*Commands:*\n"
            "/status — system status + cost\n"
            "/goals — show queue\n"
            "/ask — quick question (uses Ollama, free)\n"
            "/episodes — recent memory\n"
            "/help — this message"
        ))

    elif cmd == "/status":
        cost = llm.get_cost_summary()
        queued = db.list_goals(status="queued")
        running = db.list_goals(status="running")
        done = db.list_goals(status="done")
        tg_send(chat_id, (
            f"📊 *Kit Status*\n"
            f"Queued: {len(queued)} | Running: {len(running)} | Done: {len(done)}\n"
            f"Budget: ${cost['cumulative_usd']:.2f} / ${cost['cap_usd']:.2f} ({cost['pct_used']:.0f}%)\n"
        ))

    elif cmd == "/goals":
        goals = db.list_goals()
        if not goals:
            tg_send(chat_id, "📭 Queue is empty.")
        else:
            lines = ["📋 *Goals:*"]
            for g in goals[:10]:
                icon = {"queued": "⏳", "running": "🏃", "done": "✅", "failed": "❌"}.get(g.status, "❓")
                lines.append(f"  {icon} #{g.id} {g.goal[:50]}")
            tg_send(chat_id, "\n".join(lines))

    elif cmd == "/ask":
        if not args:
            tg_send(chat_id, "Usage: /ask your question here")
            return
        tg_send(chat_id, "🤔 Thinking...")
        try:
            answer = llm.call(
                [{"role": "user", "content": args}],
                model=os.environ.get("LOCAL_WORKER_MODEL", "qwen2.5:7b-instruct-q4_K_M"),
                system_prompt="You are Kit, a helpful assistant. Be concise.",
            )
            tg_send(chat_id, f"💬 {answer[:4000]}")
        except Exception as e:
            tg_send(chat_id, f"❌ Error: {e}")

    elif cmd == "/episodes":
        from memory import EpisodicMemory
        ep = EpisodicMemory()
        if not ep.entries:
            tg_send(chat_id, "📓 No episodes recorded yet.")
        else:
            tg_send(chat_id, f"📓 {ep.summary(n=5)}")

    else:
        tg_send(chat_id, f"Unknown command: {cmd}\nType /help for available commands.")


# ── Result Pusher (background thread) ─────────────────────────
_seen_done: set[int] = set()


def result_pusher():
    """Watch for completed goals and push results to Telegram."""
    global _seen_done
    while True:
        try:
            for status in ["done", "failed"]:
                for g in db.list_goals(status=status):
                    if g.id in _seen_done:
                        continue
                    _seen_done.add(g.id)
                    if g.reply_to:
                        icon = "✅" if g.status == "done" else "❌"
                        msg = f"{icon} Goal #{g.id} *{g.status}*: {g.goal[:60]}"
                        if g.result:
                            r = g.result if isinstance(g.result, dict) else {}
                            if r.get("type") == "autonomous":
                                msg += (f"\nKept: {r.get('keeps', 0)} | "
                                       f"Reverted: {r.get('reverts', 0)} | "
                                       f"Net: Δ{r.get('net_delta', 0):+.4f}")
                        tg_send(g.reply_to, msg)
        except Exception as e:
            logger.error("[PUSHER] %s", e)
        time.sleep(10)


# ── Heartbeat (background thread) ─────────────────────────────
def heartbeat():
    """Periodic status ping — only when something is running."""
    while True:
        try:
            running = db.list_goals(status="running")
            if running and ADMIN_CHAT_ID:
                goals_str = ", ".join(f"#{g.id}" for g in running)
                tg_send(ADMIN_CHAT_ID, f"💓 Heartbeat — working on: {goals_str}")
        except Exception as e:
            logger.error("[HEARTBEAT] %s", e)
        time.sleep(HEARTBEAT_INTERVAL)


# ── Main Loop ─────────────────────────────────────────────────
_running = True


def _handle_signal(signum, frame):
    global _running
    logger.info("🛑 Signal %d received. Shutting down...", signum)
    _running = False


signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)


def main():
    logger.info("🤖 Kit Heartbeat starting. Polling Telegram...")

    if ADMIN_CHAT_ID:
        tg_send(ADMIN_CHAT_ID, "🤖 Kit is online. Send me a goal or type /help.")

    # Start background threads
    threading.Thread(target=result_pusher, daemon=True).start()
    threading.Thread(target=heartbeat, daemon=True).start()

    offset = 0
    while _running:
        updates = tg_get_updates(offset)
        for update in updates:
            offset = update["update_id"] + 1
            msg = update.get("message", {})
            text = msg.get("text", "")
            chat_id = msg.get("chat", {}).get("id")
            user_name = msg.get("from", {}).get("first_name", "User")

            if chat_id:
                handle_message(chat_id, text, user_name)

        if not updates:
            time.sleep(POLL_INTERVAL)

    logger.info("🛑 Kit Heartbeat stopped.")


if __name__ == "__main__":
    main()
