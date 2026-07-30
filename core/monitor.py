"""
core/monitor.py
Background loop: periodically checks every "running" bot, and if it has
crashed, tries auto_fix once before marking it crashed and (optionally)
notifying the owner.
"""

import asyncio
import logging
import config
from core import docker_manager, process_manager, deploy, auto_fix
from database.db import bots_db

logger = logging.getLogger("monitor")

CHECK_INTERVAL_SECONDS = 30


async def monitor_loop(bot_app):
    """Run forever as a background task on the PTB application."""
    while True:
        try:
            await _check_all_bots(bot_app)
        except Exception:
            logger.exception("monitor loop iteration failed")
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)


async def _check_all_bots(bot_app):
    with bots_db() as conn:
        rows = [dict(r) for r in conn.execute("SELECT * FROM bots WHERE status='running'").fetchall()]

    for row in rows:
        alive = await asyncio.to_thread(_is_alive, row)
        if alive:
            continue

        logger.info("bot_id=%s appears crashed, attempting auto-fix", row["bot_id"])
        logs = await asyncio.to_thread(deploy.get_logs, row, 200)
        fixed, message = await asyncio.to_thread(auto_fix.attempt_fix, row["path"], row["runtime"], logs)

        with bots_db() as conn:
            restarts = row["restarts"] + 1
            if fixed and restarts <= config.MAX_AUTO_RESTARTS:
                conn.execute("UPDATE bots SET restarts=? WHERE bot_id=?", (restarts, row["bot_id"]))
                try:
                    await asyncio.to_thread(deploy.restart_bot, row)
                except Exception:
                    conn.execute("UPDATE bots SET status='crashed' WHERE bot_id=?", (row["bot_id"],))
            else:
                conn.execute("UPDATE bots SET status='crashed' WHERE bot_id=?", (row["bot_id"],))

        await _notify_owner(bot_app, row, fixed, message)


def _is_alive(row: dict) -> bool:
    if row.get("container_id"):
        try:
            stats = docker_manager.get_stats(row["container_id"])
            return stats["status"] == "running"
        except Exception:
            return False
    if row.get("pid"):
        return process_manager.is_running(row["pid"])
    return False


async def _notify_owner(bot_app, row: dict, fixed: bool, message: str):
    text = f"⚠️ *{row['name']}* stopped unexpectedly.\n\n"
    text += f"✅ Auto-fix applied: {message}" if fixed else f"❌ {message}"
    text += config.CREDIT_FOOTER
    try:
        await bot_app.bot.send_message(chat_id=row["owner_id"], text=text, parse_mode="Markdown")
    except Exception:
        logger.warning("could not notify owner %s", row["owner_id"])
