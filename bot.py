import asyncio
import logging
import os
from telegram import Update, ChatMember
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.constants import ParseMode
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Кеш участников чата: {chat_id: {user_id: User}}
members_cache: dict[int, dict[int, object]] = {}


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

    # Только для групп и супергрупп
    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text("❌ Эта команда работает только в группах!")
        return

    await update.message.reply_text("⏳ Собираю список участников...")

    mentions = []

    # Попытка получить список через getChatAdministrators (работает всегда)
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

    # Добавляем участников из кеша (тех, кто писал сообщения)
    cache = members_cache.get(chat.id, {})
    for uid, u in cache.items():
        # Пропускаем уже добавленных администраторов
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

    # Имя вызвавшего команду
    caller_name = user.first_name if user else "Кто-то"

    # Разбиваем на чанки по 20 упоминаний, чтобы не превысить лимит
    chunk_size = 20
    chunks = [mentions[i : i + chunk_size] for i in range(0, len(mentions), chunk_size)]

    for idx, chunk in enumerate(chunks):
        if idx == 0:
            header = f"📢 <b>{caller_name}</b> зовёт всех!\n\n"
        else:
            header = ""
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


def main() -> None:
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise ValueError(
            "❌ Токен бота не найден!\n"
            "Создайте файл .env и добавьте строку:\n"
            "BOT_TOKEN=ваш_токен_здесь"
        )

    app = Application.builder().token(token).build()

    # Хендлеры команд
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("all", all_command))

    # Отслеживаем все сообщения для кеша участников
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, track_member)
    )

    logger.info("🤖 Бот запущен...")

    # Фикс для Python 3.10+/3.14 — явно создаём event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
