import json
import logging
import os
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

import requests

sys.path.append(str(Path(__file__).resolve().parents[1]))
from db import get_started_users, init_db, save_started_user

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN", "")
API = f"https://api.telegram.org/bot{TOKEN}"

# Кеш участников: {chat_id: {user_id: user_dict}}
members_cache: dict = {}


# ── Telegram API helpers ──────────────────────────────────────────────────────

def send_message(chat_id: int, text: str, parse_mode: str = None, reply_to: int = None, reply_markup: dict | None = None):
    payload = {"chat_id": chat_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if reply_to:
        payload["reply_to_message_id"] = reply_to
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    try:
        requests.post(f"{API}/sendMessage", json=payload, timeout=10)
    except Exception as e:
        logger.error(f"sendMessage error: {e}")


def get_admins(chat_id: int) -> list:
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


# ── Команды ───────────────────────────────────────────────────────────────────

def handle_start(message: dict):
    chat_id = message["chat"]["id"]
    chat_type = message["chat"]["type"]
    msg_id = message["message_id"]
    user = message.get("from")

    if user:
        save_started_user(user, chat_id)

    if chat_type == "private":
        reply_markup = {
            "keyboard": [
                [{"text": "📞 Поделиться номером", "request_contact": True}]
            ],
            "resize_keyboard": True,
            "one_time_keyboard": True,
        }
        send_message(
            chat_id,
            "Привет! Я бот для упоминания всех в группе.\n\n"
            "Отправь свой номер телефона, чтобы он был сохранён и показан в списке пользователей.\n\n"
            "Добавь меня в группу как администратора и используй /all",
            reply_to=msg_id,
            reply_markup=reply_markup,
        )
    else:
        send_message(chat_id, "Бот активирован! Используй /all чтобы отметить всех.", reply_to=msg_id)


def handle_help(message: dict):
    chat_id = message["chat"]["id"]
    msg_id = message["message_id"]
    text = (
        "<b>Бот для упоминания всех</b>\n\n"
        "<b>Команды:</b>\n"
        "• /all — отметить всех участников группы\n"
        "• /users — показать пользователей, которые запускали бота\n"
        "• /help — показать это сообщение\n\n"
        "<b>Как это работает:</b>\n"
        "Бот запоминает всех, кто пишет в чат.\n"
        "Администраторы отмечаются автоматически.\n\n"
        "<b>Требования:</b>\n"
        "Бот должен быть администратором группы."
    )
    send_message(chat_id, text, parse_mode="HTML", reply_to=msg_id)


def handle_users(message: dict):
    chat_id = message["chat"]["id"]
    msg_id = message["message_id"]
    users = get_started_users(limit=50)

    if not users:
        send_message(chat_id, "📭 Пока нет сохранённых пользователей.", reply_to=msg_id)
        return

    lines = ["👥 Пользователи, которые запускали бота:"]
    for user in users:
        username = user.get("username") or "—"
        first_name = user.get("first_name") or "—"
        last_name = user.get("last_name") or ""
        full_name = f"{first_name} {last_name}".strip()
        if full_name == "—":
            full_name = "—"
        lines.append(
            f"• {full_name} (@{username}) | id={user.get('user_id')} | chat={user.get('chat_id')}"
        )

    send_message(chat_id, "\n".join(lines), parse_mode="HTML", reply_to=msg_id)


def handle_all(message: dict):
    chat_id = message["chat"]["id"]
    chat_type = message["chat"]["type"]
    msg_id = message["message_id"]
    caller_name = message.get("from", {}).get("first_name", "Кто-то")

    if chat_type not in ("group", "supergroup"):
        send_message(chat_id, "Эта команда работает только в группах!", reply_to=msg_id)
        return

    send_message(chat_id, "Собираю список участников...", reply_to=msg_id)

    mentions = []

    for member in get_admins(chat_id):
        u = member.get("user", {})
        if u.get("is_bot"):
            continue
        if u.get("username"):
            mentions.append(f"@{u['username']}")
        else:
            name = u.get("first_name") or "Участник"
            mentions.append(f'<a href="tg://user?id={u["id"]}">{name}</a>')

    for uid, u in members_cache.get(chat_id, {}).items():
        already = any(
            (f"@{u.get('username')}" in mentions if u.get("username") else False)
            or f'tg://user?id={u.get("id")}' in " ".join(mentions)
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
            "Не удалось найти участников.\n"
            "Подсказка: участники должны хотя бы раз написать что-то в чат.",
            reply_to=msg_id,
        )
        return

    chunk_size = 20
    for idx, i in enumerate(range(0, len(mentions), chunk_size)):
        chunk = mentions[i: i + chunk_size]
        header = f"<b>{caller_name}</b> зовёт всех!\n\n" if idx == 0 else ""
        send_message(chat_id, header + " ".join(chunk), parse_mode="HTML")


# ── Routing ───────────────────────────────────────────────────────────────────

def track_member(message: dict):
    chat_id = message["chat"]["id"]
    user = message.get("from")
    phone_number = None
    contact = message.get("contact")
    if contact and user and contact.get("user_id") == user.get("id"):
        phone_number = contact.get("phone_number")

    if user and not user.get("is_bot"):
        save_started_user(user, chat_id, phone_number)
        members_cache.setdefault(chat_id, {})[user["id"]] = user


def process_message(message: dict):
    init_db()
    text = (message.get("text", "") or "").strip()
    if not text:
        return

    command = text.split()[0].lower()
    track_member(message)

    if command.startswith("/start"):
        handle_start(message)
    elif command.startswith("/help"):
        handle_help(message)
    elif command.startswith("/all"):
        handle_all(message)
    elif command.startswith("/users"):
        handle_users(message)


# ── Vercel native handler ─────────────────────────────────────────────────────

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            update = json.loads(body)
            message = update.get("message") or update.get("edited_message")
            if message:
                process_message(message)
        except Exception as e:
            logger.error(f"Error processing update: {e}")

        self._respond(200, b"ok")

    def do_GET(self):
        token = os.environ.get("BOT_TOKEN", "")
        if token:
            masked = token[:6] + "..." + token[-4:]
            body = f"Bot is running! TOKEN set: {masked}".encode()
        else:
            body = b"ERROR: BOT_TOKEN is NOT set in Vercel environment variables!"
        self._respond(200, body)

    def _respond(self, status: int, body: bytes):
        self.send_response(status)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        logger.info(f"{self.address_string()} - {fmt % args}")
