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
BOT_TOKEN = "8029965764:AAEaGDeVSzeo5Jiz8mckmCM5qflxKYYZ3OQ"
ADMIN_ID = 7360649475
SHEETDB_API = "https://sheetdb.io/api/v1/r5omk7x4ayrq1"

PORT = int(os.environ.get("PORT", 10000))
WEBHOOK_URL = "https://sayedfun-tele-bot.onrender.com"

# Conversation states
MODERATOR, USERNAME, AMOUNT = range(3)

# ================= HELPERS =================
def is_valid_username(username: str):
    return re.fullmatch(r"@?[a-zA-Z0-9_]{5,32}", username)

def moderator_keyboard():
    mods = ["Millat", "Shifat", "Mahin", "Nirob"]
    keyboard = []
    for i in range(0, len(mods), 2):
        row = [InlineKeyboardButton(m, callback_data=f"set_mod:{m}") for m in mods[i:i+2]]
        keyboard.append(row)
    return InlineKeyboardMarkup(keyboard)

def main_menu_keyboard():
    keyboard = [
        [KeyboardButton("🆕 New Send"), KeyboardButton("💰 Total Amount")],
        [KeyboardButton("📋 All Submit")],
        [KeyboardButton("⏳ Pending List"), KeyboardButton("✅ Paid List")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

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

async def get_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender = update.message.text.strip()
    if sender.lower() == "self":
        my_username = update.message.from_user.username
        if not my_username:
            await update.message.reply_text("❌ You don't have a Telegram username.")
            return USERNAME
        context.user_data["sender"] = f"@{my_username}"
        await update.message.reply_text("Now enter amount:")
        return AMOUNT

    if not is_valid_username(sender):
        await update.message.reply_text("❌ Invalid username.")
        return USERNAME

    context.user_data["sender"] = sender if sender.startswith("@") else "@" + sender
    await update.message.reply_text("Now enter amount:")
    return AMOUNT

async def get_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.text.isdigit():
        await update.message.reply_text("❌ Amount must be a number.")
        return AMOUNT

    amount = int(update.message.text)
    sender = context.user_data["sender"]
    mod = context.user_data.get("selected_mod")
    user_name = update.message.from_user.username or update.message.from_user.first_name
    chat_id = update.message.from_user.id
    date_id = datetime.now().strftime("%Y%m%d%H%M%S")

    data = {"data": [{
        "date": date_id,
        "moderator": mod,
        "telegram_user": user_name,
        "chat_id": chat_id,
        "sender_username": sender,
        "amount": amount,
        "status": "pending",
    }]}

    requests.post(SHEETDB_API, json=data, timeout=10)

    admin_msg = (
        f"📩 <b>New Submission</b>\n\n"
        f"👤 @{user_name}\n"
        f"🛡 {mod}\n"
        f"🔁 {sender}\n"
        f"💰 {amount}"
    )

    await context.bot.send_message(
        ADMIN_ID,
        admin_msg,
        reply_markup=admin_buttons(date_id, chat_id),
        parse_mode="HTML",
    )

    await update.message.reply_text("✅ Submitted!", reply_markup=main_menu_keyboard())
    return ConversationHandler.END

async def select_moderator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["selected_mod"] = q.data.split(":")[1]
    await q.edit_message_text("Now enter Sender Username (or type 'self'):")
    return USERNAME

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    action, date_id, chat_id = q.data.split(":")
    status = "accepted" if action == "accept" else "canceled"

    requests.patch(
        f"{SHEETDB_API}/date/{date_id}",
        json={"data": [{"status": status}]},
        timeout=10,
    )

    await q.edit_message_text(f"Submission {status.upper()}")
    await context.bot.send_message(chat_id, f"📢 Submission {status}")

async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "🆕 New Send":
        await update.message.reply_text("Select Moderator:", reply_markup=moderator_keyboard())
        return MODERATOR
    return ConversationHandler.END

# ================= WEBHOOK SETUP =================
flask_app = Flask(__name__)
telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()

conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^(🆕 New Send|💰 Total Amount|📋 All Submit)$"), menu_handler)],
    states={
        MODERATOR: [CallbackQueryHandler(select_moderator, pattern="^set_mod:")],
        USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_username)],
        AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_amount)],
    },
    fallbacks=[CommandHandler("start", start)],
)

telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(conv)
telegram_app.add_handler(CallbackQueryHandler(admin_callback, pattern="^(accept|cancel):"))

@flask_app.route("/")
def home():
    return "Bot is alive", 200

@flask_app.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.json, telegram_app.bot)
    asyncio.run(telegram_app.process_update(update))
    return "OK", 200

async def set_webhook():
    await telegram_app.bot.set_webhook(f"{WEBHOOK_URL}/webhook")

if __name__ == "__main__":
    asyncio.run(set_webhook())
    flask_app.run(host="0.0.0.0", port=PORT)
