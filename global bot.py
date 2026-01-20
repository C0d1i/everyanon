import os
import requests
import secrets
import threading
import time
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# === Настройки ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", "8000"))
WEBHOOK_HOST = os.getenv("RENDER_EXTERNAL_HOSTNAME")
WEBHOOK_URL = f"https://{WEBHOOK_HOST}/{BOT_TOKEN}"

# === Установка webhook ===
def set_webhook():
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
    try:
        response = requests.post(url, json={"url": WEBHOOK_URL})
        if response.json().get("ok"):
            print(f"✅ Webhook установлен: {WEBHOOK_URL}")
        else:
            print(f"❌ Ошибка webhook: {response.json()}")
    except Exception as e:
        print(f"⚠️ Исключение: {e}")

# === Автообновление webhook каждые 12 минут ===
def webhook_refresh_loop():
    while True:
        set_webhook()
        time.sleep(720)  # 12 минут

# === Команда /start ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args

    # Если есть аргумент — это отправитель
    if args:
        code = args[0]
        code_to_user = context.bot_data.get("code_to_user", {})
        if code in code_to_user:
            context.user_data["target_code"] = code
            await update.message.reply_text("🤫 Напишите анонимное сообщение:")
        else:
            await update.message.reply_text("❌ Ссылка недействительна.")
        return

    # Даём владельцу ссылку
    code_to_user = context.bot_data.setdefault("code_to_user", {})
    user_to_code = context.bot_data.setdefault("user_to_code", {})
    
    # Генерируем новый код (даже если был)
    code = secrets.token_urlsafe(8)
    user_to_code[user_id] = code
    code_to_user[code] = user_id

    bot_username = context.bot.username or "AnonGlobalBot"
    link = f"https://t.me/{bot_username}?start={code}"

    keyboard = [[InlineKeyboardButton("🔗 Отправить ссылку", url=f"https://t.me/share/url?url={link}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"📬 Ваша новая личная ссылка:\n{link}\n\n"
        "Старая ссылка больше не работает.",
        reply_markup=reply_markup
    )

# === Обработка сообщений ===
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_code = context.user_data.get("target_code")
    if not target_code:
        await start(update, context)
        return

    text = update.message.text
    if not text or text.startswith("/"):
        return

    owner_id = context.bot_data.get("code_to_user", {}).get(target_code)
    if not owner_id:
        await update.message.reply_text("❌ Ссылка устарела.")
        return

    try:
        await context.bot.send_message(
            chat_id=owner_id,
            text=f"📨 Анонимное сообщение:\n\n{text}"
        )
        await update.message.reply_text("✅ Сообщение отправлено!")
    except Exception:
        await update.message.reply_text("❌ Не удалось доставить.")

# === Запуск ===
def main():
    set_webhook()
    refresh_thread = threading.Thread(target=webhook_refresh_loop, daemon=True)
    refresh_thread.start()

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=BOT_TOKEN,
        webhook_url=WEBHOOK_URL
    )

if __name__ == "__main__":
    main()