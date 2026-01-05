import requests
import re
import os
import asyncio
from datetime import datetime
from flask import Flask, request

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    CallbackQueryHandler,
    filters,
)

# ================= CONFIG =================
BOT_TOKEN = "YOUR_BOT_TOKEN"
ADMIN_ID = 7360649475
SHEETDB_API = "https://sheetdb.io/api/v1/r5omk7x4ayrq1"

PORT = int(os.environ.get("PORT", 10000))
WEBHOOK_URL = "https://sayedfun-tele-bot.onrender.com"

MODERATOR, USERNAME, AMOUNT = range(3)

# ================= FLASK =================
flask_app = Flask(__name__)

# ================= TELEGRAM APP =================
telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()

# ---------- INITIALIZE TELEGRAM ----------
async def init_telegram():
    await telegram_app.initialize()

loop = asyncio.get_event_loop()
loop.run_until_complete(init_telegram())

# ================= HELPERS =================
def is_valid_username(username: str):
    return re.fullmatch(r"@?[a-zA-Z0-9_]{5,32}", username)

def moderator_keyboard():
    mods = ["Millat", "Shifat", "Mahin", "Nirob"]
    keyboard = []
    for i in range(0, len(mods), 2):
        keyboard.append(
            [InlineKeyboardButton(m, callback_data=f"set_mod:{m}") for m in mods[i:i+2]]
        )
    return InlineKeyboardMarkup(keyboard)

def main_menu_keyboard():
    return ReplyKeyboardMarkup(
        [
            ["🆕 New Send", "💰 Total Amount"],
            ["📋 All Submit"],
            ["⏳ Pending List", "✅ Paid List"],
        ],
        resize_keyboard=True,
    )

def admin_buttons(submit_date, chat_id):
    return InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("✅ Accept", callback_data=f"accept:{submit_date}:{chat_id}"),
            InlineKeyboardButton("❌ Cancel", callback_data=f"cancel:{submit_date}:{chat_id}")
        ]]
    )

# ================= HANDLERS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome! Please select an action below:",
        reply_markup=main_menu_keyboard()
    )

# (your other handlers remain SAME)

# ================= ADD HANDLERS =================
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CallbackQueryHandler(admin_callback, pattern="^(accept|cancel):"))
telegram_app.add_handler(conv)

# ================= ROUTES =================
@flask_app.route("/")
def home():
    return "Bot is alive", 200

@flask_app.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.json, telegram_app.bot)

    asyncio.get_event_loop().create_task(
        telegram_app.process_update(update)
    )

    return "OK", 200

# ================= WEBHOOK SET =================
async def setup_webhook():
    await telegram_app.bot.set_webhook(f"{WEBHOOK_URL}/webhook")

loop.run_until_complete(setup_webhook())

# ================= START SERVER =================
if __name__ == "__main__":
    flask_app.run(host="0.0.0.0", port=PORT)
