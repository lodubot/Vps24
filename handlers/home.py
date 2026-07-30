"""
handlers/home.py
/start command and the main inline menu shared by every other handler.
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
import config
from database.db import users_db
from handlers.common import safe_edit, esc


def main_menu_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("⬆️ Upload Bot", callback_data="upload:start"),
         InlineKeyboardButton("🐙 Deploy from GitHub", callback_data="github:start")],
        [InlineKeyboardButton("🤖 My Bots", callback_data="mybots:list"),
         InlineKeyboardButton("📁 Files", callback_data="files:menu")],
        [InlineKeyboardButton("📜 Logs", callback_data="logs:menu"),
         InlineKeyboardButton("🔑 Env Vars", callback_data="env:menu")],
        [InlineKeyboardButton("📊 Dashboard", callback_data="dashboard:show"),
         InlineKeyboardButton("💾 Backup", callback_data="backup:menu")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="settings:menu"),
         InlineKeyboardButton("👤 Account", callback_data="account:show")],
        [InlineKeyboardButton("📢 Channel", url=config.CREDIT_TELEGRAM_CHANNEL),
         InlineKeyboardButton("▶️ YouTube", url=config.CREDIT_YOUTUBE_CHANNEL)],
    ]
    return InlineKeyboardMarkup(rows)


def home_caption(user_first_name: str) -> str:
    return (
        f"👋 Welcome, *{esc(user_first_name)}*!\n\n"
        "This bot lets you host your own Telegram bots (or any Python/Node app) "
        "straight from Telegram — upload a file, paste a GitHub link, and it's live.\n\n"
        "Use the menu below to get started."
        + config.CREDIT_FOOTER
    )


def _ensure_user(user_id: int, username: str | None):
    with users_db() as conn:
        conn.execute(
            "INSERT INTO users (user_id, username, is_admin) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET username=excluded.username",
            (user_id, username, 1 if user_id in config.ADMIN_IDS else 0),
        )


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    _ensure_user(user.id, user.username)

    caption = home_caption(user.first_name or "there")
    keyboard = main_menu_keyboard()

    try:
        await update.effective_chat.send_video(
            video=config.CREDIT_HOME_VIDEO_URL,
            caption=caption,
            parse_mode="Markdown",
            reply_markup=keyboard,
        )
    except Exception:
        # Fallback in case the video URL is unreachable
        await update.effective_chat.send_message(
            caption, parse_mode="Markdown", reply_markup=keyboard
        )


async def go_home_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    caption = home_caption(user.first_name or "there")
    keyboard = main_menu_keyboard()
    await safe_edit(query, caption, reply_markup=keyboard)


def register(app):
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(go_home_callback, pattern="^home:go$"))
