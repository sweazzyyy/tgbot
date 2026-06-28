# 🤖 Telegram Bot — Vercel Webhook Deploy

Бот для упоминания всех участников группы (`/all`), задеплоенный на Vercel через Webhook.

## Структура проекта

```
tgbot/
├── api/
│   └── webhook.py      # Serverless-функция (точка входа Vercel)
├── bot.py              # Старая polling-версия (для локального запуска)
├── setup_webhook.py    # Скрипт регистрации webhook в Telegram
├── vercel.json         # Конфигурация Vercel
├── requirements.txt    # Зависимости Python
├── .env                # Локальные переменные (НЕ коммитить!)
└── .gitignore
```

---

## 🚀 Деплой на Vercel (пошаговая инструкция)

### Шаг 1 — Залить код на GitHub

```bash
git init
git add .
git commit -m "feat: webhook mode for Vercel"
git remote add origin https://github.com/ВАШ_АККАУНТ/tgbot.git
git push -u origin main
```

### Шаг 2 — Создать проект на Vercel

1. Зайди на [vercel.com](https://vercel.com) → **Add New Project**
2. Импортируй свой GitHub репозиторий
3. В разделе **Environment Variables** добавь:
   - `BOT_TOKEN` = `твой_токен_от_BotFather`
4. Нажми **Deploy**

### Шаг 3 — Зарегистрировать Webhook в Telegram

После деплоя скопируй URL своего проекта (например `https://tgbot-abc123.vercel.app`) и выполни:

```bash
python setup_webhook.py https://tgbot-abc123.vercel.app
```

Готово! Бот будет получать обновления через Vercel. ✅

---

## ⚠️ Важные ограничения serverless

- **Кеш участников** (тех, кто писал в чат) хранится в памяти и сбрасывается при "холодном старте" инстанса.
- **Администраторы** всегда отмечаются корректно (запрашиваются через Telegram API).
- Если нужен постоянный кеш — подключи Redis (например Upstash).

---

## 🔧 Локальный запуск (старый polling-режим)

```bash
pip install -r requirements.txt
python bot.py
```
