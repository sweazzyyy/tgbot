"""
Скрипт для регистрации Webhook URL в Telegram.
Запускать ОДИН РАЗ после деплоя на Vercel.

Использование:
  python setup_webhook.py https://ВАШ-ПРОЕКТ.vercel.app
"""

import io
import sys

# Фикс кодировки Windows (cp1251 не поддерживает эмодзи)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
import os
import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
API = f"https://api.telegram.org/bot{TOKEN}"


def set_webhook(vercel_url: str):
    webhook_url = vercel_url.rstrip("/") + "/api/webhook"

    r = requests.post(
        f"{API}/setWebhook",
        json={
            "url": webhook_url,
            "allowed_updates": ["message", "edited_message"],
            "drop_pending_updates": True,
        },
        timeout=15,
    )
    result = r.json()

    if result.get("ok"):
        print("[OK] Webhook успешно установлен!")
        print(f"     URL: {webhook_url}")
    else:
        print(f"[FAIL] Ошибка: {result.get('description')}")

    # Проверка
    info = requests.get(f"{API}/getWebhookInfo", timeout=10).json().get("result", {})
    print("\n[INFO] Информация о webhook:")
    print(f"   URL:             {info.get('url')}")
    print(f"   Pending updates: {info.get('pending_update_count', 0)}")
    if info.get("last_error_message"):
        print(f"   Последняя ошибка: {info['last_error_message']}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python setup_webhook.py https://ВАШ-ПРОЕКТ.vercel.app")
        sys.exit(1)

    set_webhook(sys.argv[1])
