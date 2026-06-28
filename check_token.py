"""
Диагностика: получаем chat_id и тестируем Vercel webhook с реальным chat_id.
"""
import requests
import os
import json
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
API = f"https://api.telegram.org/bot{TOKEN}"
VERCEL_WEBHOOK = "https://tgbot-pi-three.vercel.app/api/webhook"

print("=== Шаг 1: Временно снимаем webhook ===")
requests.post(f"{API}/deleteWebhook", json={"drop_pending_updates": True}, timeout=10)

print("=== Шаг 2: Получаем твой chat_id ===")
r = requests.get(f"{API}/getUpdates", params={"limit": 10, "timeout": 5}, timeout=15)
updates = r.json().get("result", [])

chat_id = None
for upd in updates:
    msg = upd.get("message")
    if msg:
        chat_id = msg["chat"]["id"]
        name = msg.get("from", {}).get("first_name", "?")
        print(f"  Найден chat_id: {chat_id} (имя: {name})")
        break

if not chat_id:
    print("  [!] updates пусты — восстанавливаем webhook и пробуем иначе")
else:
    print(f"\n=== Шаг 3: Симулируем /start через Vercel с chat_id={chat_id} ===")
    fake_update = {
        "update_id": 999,
        "message": {
            "message_id": 999,
            "from": {"id": chat_id, "is_bot": False, "first_name": "Test"},
            "chat": {"id": chat_id, "type": "private"},
            "text": "/start"
        }
    }
    r2 = requests.post(VERCEL_WEBHOOK, json=fake_update, timeout=15)
    print(f"  Vercel ответил: {r2.status_code} {r2.text}")
    print("  Если бот ответил в Telegram — всё работает!")
    print("  Если нет — BOT_TOKEN не задан в Vercel env vars.")

    print(f"\n=== Шаг 4: Также пробуем sendMessage напрямую (локально) ===")
    r3 = requests.post(
        f"{API}/sendMessage",
        json={"chat_id": chat_id, "text": "Прямой тест локального токена — работает!"},
        timeout=10
    )
    resp = r3.json()
    if resp.get("ok"):
        print("  [OK] Прямой sendMessage работает — токен корректный.")
    else:
        print(f"  [FAIL] {resp}")

print("\n=== Восстанавливаем webhook ===")
r4 = requests.post(
    f"{API}/setWebhook",
    json={"url": VERCEL_WEBHOOK, "drop_pending_updates": True},
    timeout=10
)
print(f"  {r4.json().get('description')}")
