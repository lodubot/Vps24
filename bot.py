"""
bot.py
Main entry point for the Telegram Hosting Bot.
Loads config from config.py (no .env, no os.getenv), registers all
handlers, starts the background monitor, and runs polling.
"""

import logging
import asyncio
import config
from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from handlers import (
    home,
    upload,
    github,
    mybots,
    files,
    logs as logs_handler,
    env,
    dashboard,
    backup,
    settings,
    account,
    admin,
)
from core import monitor
from database.db import init_databases

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("bot")

HANDLER_MODULES = [
    home,
    upload,
    github,
    mybots,
    files,
    logs_handler,
    env,
    dashboard,
    backup,
    settings,
    account,
    admin,
]


async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Several flows (GitHub URL entry, env var entry) wait for the user's
    next plain-text message. This router checks user_data flags in
    priority order and dispatches to the right handler.
    """
    if context.user_data.get(github.AWAITING_REPO_URL):
        await github.handle_text(update, context)
        return
    if context.user_data.get(env.AWAITING_ENV_INPUT):
        await env.handle_text(update, context)
        return
    # No active flow waiting on text — ignore silently.


def build_app() -> Application:
    if not config.BOT_TOKEN:
        raise RuntimeError("config.BOT_TOKEN is empty. Set it in config.py before running the bot.")

    app = Application.builder().token(config.BOT_TOKEN).build()

    for module in HANDLER_MODULES:
        module.register(app)

    # Central router for plain-text replies used by multi-step flows.
    # Registered last / low priority group so it only fires when nothing
    # else in the module claimed the update.
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router), group=10)

    return app


async def _post_init(app: Application):
    init_databases()
    logger.info("Databases initialized.")
    app.create_task(monitor.monitor_loop(app))
    logger.info("Background monitor started.")


def main():
    # Fix 1: Event loop initialization for Python 3.14 & sub-threads
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    app = build_app()
    app.post_init = _post_init
    logger.info("Starting bot...")
    
    # Fix 2: stop_signals=None for CoCalc / Web terminal environment
    app.run_polling(allowed_updates=Update.ALL_TYPES, stop_signals=None)


if __name__ == "__main__":
    main()
