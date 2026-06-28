import logging
import os

import requests
from flask import Flask, request, Response

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")
API = f"https://api.telegram.org/bot{TOKEN}"

app = Flask(__name__)

# Кеш участников чата: {chat_id: {user_id: user_dict}}
# Живёт в рамках одного "тёплого" инстанса Vercel.
members_cache: dict = {}


# ── Telegram API helpers ──────────────────────────────────────────────────────

def send_message(chat_id: int, text: str, parse_mode: str = None, reply_to: int = None):
    payload = {"chat_id": chat_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if reply_to:
        payload["reply_to_message_id"] = reply_to
    try:
        requests.post(f"{API}/sendMessage", json=payload, timeout=10)
    except Exception as e:
        logger.error(f"sendMessage error: {e}")


def get_chat_administrators(chat_id: int) -> list:
    try:
        r = requests.get(
            f"{API}/getChatAdministrators",
            params={"chat_id": chat_id},
            timeout=10,
        )
        data = r.json()
        return data.get("result", []) if data.get("ok") else []
    except Exception as e:
        logger.error(f"getChatAdministrators error: {e}")
        return []


# ── Хендлеры команд ───────────────────────────────────────────────────────────

def handle_start(message: dict):
    chat_id = message["chat"]["id"]
    chat_type = message["chat"]["type"]
    msg_id = message["message_id"]

    if chat_type == "private":
        send_message(
            chat_id,
            "👋 Привет! Я бот для упоминания всех в группе.\n\n"
            "Добавь меня в группу как администратора и используй команду /all",
            reply_to=msg_id,
        )
    else:
        send_message(
            chat_id,
            "✅ Бот активирован! Используй /all чтобы отметить всех.",
            reply_to=msg_id,
        )


def handle_help(message: dict):
    chat_id = message["chat"]["id"]
    msg_id = message["message_id"]
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
    send_message(chat_id, text, parse_mode="HTML", reply_to=msg_id)


def handle_all(message: dict):
    chat_id = message["chat"]["id"]
    chat_type = message["chat"]["type"]
    msg_id = message["message_id"]
    caller_name = message.get("from", {}).get("first_name", "Кто-то")

    if chat_type not in ("group", "supergroup"):
        send_message(chat_id, "❌ Эта команда работает только в группах!", reply_to=msg_id)
        return

    send_message(chat_id, "⏳ Собираю список участников...", reply_to=msg_id)

    mentions = []

    # Администраторы (всегда доступны через API)
    for member in get_chat_administrators(chat_id):
        u = member.get("user", {})
        if u.get("is_bot"):
            continue
        if u.get("username"):
            mentions.append(f"@{u['username']}")
        else:
            name = u.get("first_name") or "Участник"
            mentions.append(f'<a href="tg://user?id={u["id"]}">{name}</a>')

    # Участники из кеша (те, кто писал в чат)
    for uid, u in members_cache.get(chat_id, {}).items():
        already = any(
            (f"@{u.get('username')}" in mentions if u.get("username") else False)
            or f'tg://user?id={u["id"]}' in " ".join(mentions)
        )
        if not already and not u.get("is_bot"):
            if u.get("username"):
                mentions.append(f"@{u['username']}")
            else:
                name = u.get("first_name") or "Участник"
                mentions.append(f'<a href="tg://user?id={uid}">{name}</a>')

    if not mentions:
        send_message(
            chat_id,
            "⚠️ Не удалось найти участников.\n"
            "Подсказка: участники должны хотя бы раз написать что-то в чат, "
            "чтобы бот их запомнил.",
            reply_to=msg_id,
        )
        return

    chunk_size = 20
    for idx, i in enumerate(range(0, len(mentions), chunk_size)):
        chunk = mentions[i: i + chunk_size]
        header = f"📢 <b>{caller_name}</b> зовёт всех!\n\n" if idx == 0 else ""
        send_message(chat_id, header + " ".join(chunk), parse_mode="HTML")


# ── Обработка входящих сообщений ──────────────────────────────────────────────

def track_member(message: dict):
    """Кеширует пользователя, написавшего сообщение."""
    chat_id = message["chat"]["id"]
    user = message.get("from")
    if user and not user.get("is_bot"):
        members_cache.setdefault(chat_id, {})[user["id"]] = user


def process_message(message: dict):
    text = message.get("text", "")
    track_member(message)

    if text.startswith("/start"):
        handle_start(message)
    elif text.startswith("/help"):
        handle_help(message)
    elif text.startswith("/all"):
        handle_all(message)


# ── Flask routes ──────────────────────────────────────────────────────────────

@app.route("/api/webhook", methods=["POST"])
def webhook():
    update = request.get_json(force=True)
    if not update:
        return Response("Bad request", status=400)
    try:
        message = update.get("message") or update.get("edited_message")
        if message:
            process_message(message)
    except Exception as e:
        logger.error(f"Error processing update: {e}")
    return Response("ok", status=200)


@app.route("/", methods=["GET"])
def index():
    return Response("🤖 Telegram bot is running on Vercel!", status=200)
