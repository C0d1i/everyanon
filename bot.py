import os
import json
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
    filters,
    CallbackQueryHandler
)

# === Настройки ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", "8000"))
WEBHOOK_HOST = os.getenv("RENDER_EXTERNAL_HOSTNAME")
WEBHOOK_URL = f"https://{WEBHOOK_HOST}/{BOT_TOKEN}"
STORAGE_FILE = "storage.json"

# === Загрузка данных из файла ===
def load_storage():
    if os.path.exists(STORAGE_FILE):
        try:
            with open(STORAGE_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {"user_to_code": {}, "code_to_user": {}}

# === Сохранение данных в файл ===
def save_storage(data):
    with open(STORAGE_FILE, "w") as f:
        json.dump(data, f)

# === Webhook setup ===
def set_webhook():
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
    try:
        response = requests.post(url, json={"url": WEBHOOK_URL})
        if response.json().get("ok"):
            print(f"✅ Webhook установлен: {WEBHOOK_URL}")
        else:
            print(f"❌ Ошибка: {response.json()}")
    except Exception as e:
        print(f"⚠️ Исключение: {e}")

def webhook_refresh_loop():
    while True:
        set_webhook()
        time.sleep(720)

# === Основные функции ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)  # JSON keys must be strings
    args = context.args

    if args:
        code = args[0]
        storage = load_storage()
        if code in storage["code_to_user"]:
            context.user_data["target_code"] = code
            await update.message.reply_text("🤫 Напишите анонимное сообщение:")
        else:
            await update.message.reply_text("❌ Ссылка недействительна.")
        return

    storage = load_storage()
    if user_id not in storage["user_to_code"]:
        code = secrets.token_urlsafe(8)
        storage["user_to_code"][user_id] = code
        storage["code_to_user"][code] = user_id
        save_storage(storage)
        is_new = True
    else:
        code = storage["user_to_code"][user_id]
        is_new = False

    bot_username = context.bot.username or "AnonGlobalBot"
    link = f"https://t.me/{bot_username}?start={code}"

    keyboard = [
        [InlineKeyboardButton("🔗 Отправить ссылку", url=f"https://t.me/share/url?url={link}")],
        [InlineKeyboardButton("🔄 Сбросить ссылку", callback_data="reset_link")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if is_new:
        msg = f"📬 Ваша личная ссылка:\n{link}\n\nОна будет работать, пока вы не сбросите её."
    else:
        msg = f"Ваша текущая ссылка:\n{link}\n\nОна уже активна."

    await update.message.reply_text(msg, reply_markup=reply_markup)

async def reset_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        user_id = str(query.from_user.id)
    else:
        user_id = str(update.effective_user.id)

    storage = load_storage()

    if user_id in storage["user_to_code"]:
        old_code = storage["user_to_code"][user_id]
        storage["code_to_user"].pop(old_code, None)
        storage["user_to_code"].pop(user_id, None)

    new_code = secrets.token_urlsafe(8)
    storage["user_to_code"][user_id] = new_code
    storage["code_to_user"][new_code] = user_id
    save_storage(storage)

    bot_username = context.bot.username or "AnonGlobalBot"
    link = f"https://t.me/{bot_username}?start={new_code}"

    keyboard = [
        [InlineKeyboardButton("🔗 Отправить ссылку", url=f"https://t.me/share/url?url={link}")],
        [InlineKeyboardButton("🔄 Сбросить ссылку", callback_data="reset_link")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        await query.edit_message_text(
            f"✅ Ссылка сброшена!\nНовая ссылка:\n{link}",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            f"✅ Ссылка сброшена!\nНовая ссылка:\n{link}",
            reply_markup=reply_markup
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_code = context.user_data.get("target_code")
    if not target_code:
        await start(update, context)
        return

    text = update.message.text
    if not text or text.startswith("/"):
        return

    storage = load_storage()
    owner_id = storage["code_to_user"].get(target_code)
    if not owner_id:
        await update.message.reply_text("❌ Ссылка устарела.")
        return

    try:
        await context.bot.send_message(
            chat_id=int(owner_id),
            text=f"📨 Анонимное сообщение:\n\n{text}"
        )
        await update.message.reply_text("✅ Сообщение отправлено!")
    except Exception:
        await update.message.reply_text("❌ Не удалось доставить.")

def main():
    set_webhook()
    refresh_thread = threading.Thread(target=webhook_refresh_loop, daemon=True)
    refresh_thread.start()

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("newlink", reset_link))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(reset_link, pattern="^reset_link$"))

    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=BOT_TOKEN,
        webhook_url=WEBHOOK_URL
    )

if __name__ == "__main__":
    main()