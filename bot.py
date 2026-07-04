import asyncio
import logging
import os
from telegram import Update, ChatMember, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.constants import ParseMode
from dotenv import load_dotenv

from db import get_started_users, init_db, save_started_user

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
    phone_number = None

    if update.message and update.message.contact:
        contact = update.message.contact
        if contact.user_id == (user.id if user else None):
            phone_number = contact.phone_number

    if user and not user.is_bot:
        save_started_user(user, chat_id, phone_number)
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
        "• /users — показать пользователей, которые запускали бота\n"
        "• /help — показать это сообщение\n\n"
        "💡 <b>Как это работает:</b>\n"
        "Бот запоминает всех, кто пишет в чат.\n"
        "Администраторы отмечаются автоматически.\n\n"
        "⚙️ <b>Требования:</b>\n"
        "Бот должен быть администратором группы."
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /users — показывает список пользователей из базы."""
    users = get_started_users(limit=50)

    if not users:
        await update.message.reply_text("📭 Пока нет сохранённых пользователей.")
        return

    lines = ["👥 Пользователи, которые запускали бота:"]
    for user in users:
        username = user.get("username") or "—"
        first_name = user.get("first_name") or "—"
        last_name = user.get("last_name") or ""
        full_name = f"{first_name} {last_name}".strip()
        if full_name == "—":
            full_name = "—"
        phone = user.get("phone_number") or "—"
        created_at = user.get("created_at") or "—"
        lines.append(
            f"• {full_name} (@{username}) | id={user.get('user_id')} | chat={user.get('chat_id')} | phone={phone} | first_seen={created_at}"
        )

    text = "\n".join(lines)
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /start."""
    chat = update.effective_chat
    user = update.effective_user

    if user:
        save_started_user(user, chat.id)

    if chat.type == "private":
        keyboard = ReplyKeyboardMarkup(
            [[KeyboardButton("📞 Поделиться номером", request_contact=True)]],
            resize_keyboard=True,
            one_time_keyboard=True,
        )
        await update.message.reply_text(
            "👋 Привет! Я бот для упоминания всех в группе.\n\n"
            "Отправь свой номер телефона, чтобы он был сохранён и показан в списке пользователей.\n\n"
            "Добавь меня в группу как администратора и используй команду /all",
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
        )
    else:
        await update.message.reply_text(
            "✅ Бот активирован! Используй /all чтобы отметить всех.",
            parse_mode=ParseMode.HTML,
        )


def main() -> None:
    init_db()

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
    app.add_handler(CommandHandler("users", users_command))

    # Отслеживаем все сообщения для кеша участников
    app.add_handler(
        MessageHandler((filters.TEXT | filters.CONTACT) & ~filters.COMMAND, track_member)
    )

    logger.info("🤖 Бот запущен...")

    # Фикс для Python 3.10+/3.14 — явно создаём event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
