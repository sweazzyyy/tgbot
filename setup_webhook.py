"""
Скрипт для регистрации Webhook URL в Telegram.
Запускать ОДИН РАЗ после деплоя на Vercel.

Использование:
  python setup_webhook.py https://ВАШ-ПРОЕКТ.vercel.app
"""

import sys
import asyncio
import os
from dotenv import load_dotenv
from telegram import Bot

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")


async def main(vercel_url: str):
    webhook_url = vercel_url.rstrip("/") + "/api/webhook"
    bot = Bot(token=TOKEN)

    async with bot:
        result = await bot.set_webhook(
            url=webhook_url,
            allowed_updates=["message", "edited_message", "channel_post",
                             "inline_query", "callback_query"],
            drop_pending_updates=True,
        )
        if result:
            print(f"✅ Webhook успешно установлен!")
            print(f"   URL: {webhook_url}")
        else:
            print("❌ Не удалось установить webhook")

        info = await bot.get_webhook_info()
        print(f"\n📋 Информация о webhook:")
        print(f"   URL:            {info.url}")
        print(f"   Pending updates: {info.pending_update_count}")
        if info.last_error_message:
            print(f"   Последняя ошибка: {info.last_error_message}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python setup_webhook.py https://ВАШ-ПРОЕКТ.vercel.app")
        sys.exit(1)

    asyncio.run(main(sys.argv[1]))
