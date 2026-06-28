import asyncio
import logging
import os

from flask import Flask, request, Response
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")

flask_app = Flask(__name__)

# Кеш участников чата: {chat_id: {user_id: User}}
# Примечание: в serverless этот кеш живёт в рамках одного "тёплого" инстанса.
# При холодном старте сбрасывается — это ограничение serverless-архитектуры.
members_cache: dict[int, dict[int, object]] = {}


# ── Хендлеры ─────────────────────────────────────────────────────────────────

async def track_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отслеживает участников, которые пишут в чат."""
    chat_id = update.effective_chat.id
    user = update.effective_user
    if user and not user.is_bot:
        if chat_id not in members_cache:
            members_cache[chat_id] = {}
        members_cache[chat_id][user.id] = user


async def all_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /all — отмечает всех участников группы."""
    chat = update.effective_chat
    user = update.effective_user

    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text("❌ Эта команда работает только в группах!")
        return

    await update.message.reply_text("⏳ Собираю список участников...")

    mentions = []

    try:
        admins = await context.bot.get_chat_administrators(chat.id)
        for member in admins:
            u = member.user
            if not u.is_bot:
                if u.username:
                    mentions.append(f"@{u.username}")
                else:
                    name = u.first_name or "Участник"
                    mentions.append(f'<a href="tg://user?id={u.id}">{name}</a>')
    except Exception as e:
        logger.error(f"Ошибка получения администраторов: {e}")

    cache = members_cache.get(chat.id, {})
    for uid, u in cache.items():
        already = any(
            (f"@{u.username}" in mentions if u.username else False)
            or f'tg://user?id={u.id}' in " ".join(mentions)
        )
        if not already and not u.is_bot:
            if u.username:
                mentions.append(f"@{u.username}")
            else:
                name = u.first_name or "Участник"
                mentions.append(f'<a href="tg://user?id={u.id}">{name}</a>')

    if not mentions:
        await update.message.reply_text(
            "⚠️ Не удалось найти участников.\n"
            "Подсказка: участники должны хотя бы раз написать что-то в чат, "
            "чтобы бот их запомнил."
        )
        return

    caller_name = user.first_name if user else "Кто-то"
    chunk_size = 20
    chunks = [mentions[i: i + chunk_size] for i in range(0, len(mentions), chunk_size)]

    for idx, chunk in enumerate(chunks):
        header = f"📢 <b>{caller_name}</b> зовёт всех!\n\n" if idx == 0 else ""
        text = header + " ".join(chunk)
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /help."""
    text = (
        "🤖 <b>Бот для упоминания всех</b>\n\n"
        "📋 <b>Команды:</b>\n"
        "• /all — отметить всех участников группы\n"
        "• /help — показать это сообщение\n\n"
        "💡 <b>Как это работает:</b>\n"
        "Бот запоминает всех, кто пишет в чат.\n"
        "Администраторы отмечаются автоматически.\n\n"
        "⚙️ <b>Требования:</b>\n"
        "Бот должен быть администратором группы."
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /start."""
    chat = update.effective_chat
    if chat.type == "private":
        await update.message.reply_text(
            "👋 Привет! Я бот для упоминания всех в группе.\n\n"
            "Добавь меня в группу как администратора и используй команду /all",
            parse_mode=ParseMode.HTML,
        )
    else:
        await update.message.reply_text(
            "✅ Бот активирован! Используй /all чтобы отметить всех.",
            parse_mode=ParseMode.HTML,
        )


# ── Telegram Application ──────────────────────────────────────────────────────

def build_application() -> Application:
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("all", all_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, track_member))
    return app


telegram_app = build_application()


# ── Flask routes ──────────────────────────────────────────────────────────────

@flask_app.route("/api/webhook", methods=["POST"])
def webhook():
    """Точка входа для Telegram Webhook."""
    update_data = request.get_json(force=True)
    if not update_data:
        return Response("Bad request", status=400)

    async def process():
        async with telegram_app:
            update = Update.de_json(update_data, telegram_app.bot)
            await telegram_app.process_update(update)

    asyncio.run(process())
    return Response("ok", status=200)


@flask_app.route("/", methods=["GET"])
def index():
    return Response("🤖 Telegram bot is running on Vercel!", status=200)


# ── WSGI entry point (Vercel) ─────────────────────────────────────────────────

app = flask_app
