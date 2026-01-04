import requests
import re
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    CallbackQueryHandler,
    filters
)
from datetime import datetime

# ================= CONFIG =================
BOT_TOKEN = "8029965764:AAEaGDeVSzeo5Jiz8mckmCM5qflxKYYZ3OQ"
ADMIN_ID = 7360649475
SHEETDB_API = "https://sheetdb.io/api/v1/r5omk7x4ayrq1"

# Conversation states
USERNAME, AMOUNT = range(2)

# ================= HELPERS =================
def is_valid_username(username: str):
    return re.fullmatch(r"@?[a-zA-Z0-9_]{5,32}", username)

def main_menu_keyboard():
    keyboard = [
        [KeyboardButton("🆕 New Send"), KeyboardButton("💰 Total Amount")],
        [KeyboardButton("📋 All Submit")],
        [KeyboardButton("⏳ Pending List"), KeyboardButton("✅ Paid List")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

def admin_buttons(submit_date, chat_id):
    # callback_data তে chat_id পাস করা হচ্ছে যাতে পরে মেসেজ পাঠানো যায়
    keyboard = [
        [InlineKeyboardButton("✅ Accept", callback_data=f"accept:{submit_date}:{chat_id}"),
         InlineKeyboardButton("❌ Cancel", callback_data=f"cancel:{submit_date}:{chat_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ================= HANDLERS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome! Please select an action below:",
        reply_markup=main_menu_keyboard()
    )

# ----------------- NEW SEND -----------------
async def get_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender = update.message.text.strip()
    if sender.lower() == "self":
        my_username = update.message.from_user.username
        if not my_username:
            await update.message.reply_text("❌ You don't have a Telegram username.\nPlease enter a valid @username.")
            return USERNAME
        context.user_data["sender"] = f"@{my_username}"
        await update.message.reply_text(f"✅ Sender set as: @{my_username}\nNow enter amount:")
        return AMOUNT

    if not is_valid_username(sender):
        await update.message.reply_text("❌ Invalid username format. Example: @username123")
        return USERNAME

    if not sender.startswith("@"):
        sender = "@" + sender
    context.user_data["sender"] = sender
    await update.message.reply_text(f"✅ Sender saved: {sender}\nNow enter amount:")
    return AMOUNT

async def get_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    amount_text = update.message.text.strip()
    if not amount_text.isdigit():
        await update.message.reply_text("❌ Amount must be a number. Please enter again:")
        return AMOUNT

    amount = int(amount_text)
    sender = context.user_data["sender"]
    user_name = update.message.from_user.username or update.message.from_user.first_name
    chat_id = update.message.from_user.id
    date_id = datetime.now().strftime("%Y%m%d%H%M%S")

    # ================= send to SheetDB =================
    data = {"data": [{
        "date": date_id, 
        "telegram_user": user_name, 
        "chat_id": chat_id, 
        "sender_username": sender, 
        "amount": amount, 
        "status": "pending"
    }]}
    
    try:
        requests.post(SHEETDB_API, json=data, timeout=10)
    except Exception as e:
        print(f"SheetDB Error: {e}")

    # ================= send to admin =================
    admin_msg = (
        f"📩 **New Submission**\n\n"
        f"👤 From: @{user_name}\n"
        f"🔁 Sender: {sender}\n"
        f"💰 Amount: {amount}\n"
        f"🕒 Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        f"`{sender} | {amount}`\n\n"
        f"Status: ⏳ Pending"
    )
    
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=admin_msg,
        reply_markup=admin_buttons(date_id, chat_id),
        parse_mode="Markdown"
    )

    await update.message.reply_text(
        "✅ Submitted! Wait for admin Approval.",
        reply_markup=main_menu_keyboard()
    )
    return ConversationHandler.END

# ----------------- ADMIN CALLBACK -----------------
async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()

    # --- তারিখের বাটন ক্লিক করলে এই অংশটি কাজ করবে ---
    if data.startswith("view_date:"):
        selected_date = data.split(":")[1]
        user_name = query.from_user.username or query.from_user.first_name
        
        try:
            # SheetDB থেকে ডাটা নিয়ে আসা
            res = requests.get(SHEETDB_API, timeout=10).json()
            
            # ওই ইউজার এবং ওই তারিখের ডাটা ফিল্টার
            filtered_rows = [r for r in res if (r.get("telegram_user") == user_name) and (r.get("date", "").startswith(selected_date))]
            
            if not filtered_rows:
                await query.edit_message_text(f"❌ No records found for this date.")
                return

            pretty_date = f"{selected_date[:4]}-{selected_date[4:6]}-{selected_date[6:8]}"
            msg = f"📋 **Report: {pretty_date}**\n━━━━━━━━━━━━━━\n"
            
            day_total = 0
            for r in filtered_rows:
                status = r.get('status', 'pending')
                icon = "⏳" if status == "pending" else "✅" if status == "accepted" else "❌"
                amount = r.get('amount', '0')
                sender = r.get('sender_username', 'Unknown')
                msg += f"{icon} {amount} | {sender}\n"
                
                if status == "accepted":
                    day_total += int(amount)
            
            msg += f"━━━━━━━━━━━━━━\n💰 **Daily Total: {day_total}**"
            
            # বাটন সরিয়ে ডাটা দেখানো
            await query.edit_message_text(msg, parse_mode="Markdown")
            
        except Exception as e:
            print(f"Error: {e}")
            await query.edit_message_text("❌ Data could not be loaded.")
        return

    try:
        action, submit_date, target_chat_id = query.data.split(":")
    except:
        await query.edit_message_text("❌ Error: Invalid callback data.")
        return

    new_status = "accepted" if action == "accept" else "canceled"
    status_icon = "✅" if action == "accept" else "❌"

    try:
        # 1. Update SheetDB
        patch_url = f"{SHEETDB_API}/date/{submit_date}"
        payload = {"data": [{"status": new_status}]}
        r = requests.patch(patch_url, json=payload, timeout=10)

        if r.status_code in [200, 201]:
            # 2. Update Admin Message
            await query.edit_message_text(f"Submission {new_status.capitalize()} {status_icon}")

            search_res = requests.get(f"{SHEETDB_API}/search?date={submit_date}", timeout=10).json()
            sender_name = "N/A"
            amount_val = "0"
            
            if search_res:
                sender_name = search_res[0].get('sender_username', 'Unknown')
                amount_val = search_res[0].get('amount', '0')
            
            # 3. Notify User (Using target_chat_id)
            user_notif = (
                f"📢 **Submission Update**\n\n"
                f"{sender_name} - {amount_val} : {status_icon}\n\n"
                f"Thank you!"
            )
            await context.bot.send_message(chat_id=target_chat_id, text=user_notif, parse_mode="Markdown")
        else:
            await query.edit_message_text(f"❌ DB Update Failed (Code: {r.status_code})")

    except Exception as e:
        await query.edit_message_text(f"❌ System Error: {str(e)}")

# ----------------- MENU HANDLER -----------------
async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_name = update.message.from_user.username or update.message.from_user.first_name

    if text == "🆕 New Send":
        await update.message.reply_text("Enter sender username.\n\nType:\n👉 self (your username)\n👉 @username")
        return USERNAME

    elif text == "💰 Total Amount":
        try:
            res = requests.get(SHEETDB_API, timeout=10).json()
            user_rows = [item for item in res if item.get("telegram_user") == user_name]
            total = sum(int(item.get("amount", 0)) for item in user_rows if item.get("status") == "accepted")
            await update.message.reply_text(f"💰 Your Approved Total: {total}", reply_markup=main_menu_keyboard())
        except:
            await update.message.reply_text("❌ Error fetching amount.")

    elif text == "📋 All Submit":
        try:
            res = requests.get(SHEETDB_API, timeout=10).json()
            user_rows = [item for item in res if item.get("telegram_user") == user_name]
            
            if not user_rows:
                await update.message.reply_text("📋 No data found.")
                return

            # ইউনিক তারিখগুলো বের করা (Set ব্যবহার করে)
            unique_dates = sorted(list(set(row.get("date", "")[:8] for row in user_rows)), reverse=True)

            keyboard = []
            # প্রতি লাইনে ২টা করে তারিখের বাটন তৈরি
            for i in range(0, len(unique_dates[:10]), 2):
                row_btns = []
                for d in unique_dates[i:i+2]:
                    # ফরম্যাট: YYYY-MM-DD
                    pretty_date = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
                    row_btns.append(InlineKeyboardButton(pretty_date, callback_data=f"view_date:{d}"))
                keyboard.append(row_btns)

            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("📅 Select date:", reply_markup=reply_markup)
            
        except Exception as e:
            await update.message.reply_text("❌ Error fetching dates.")

    else:
        await update.message.reply_text("Please use the menu buttons.", reply_markup=main_menu_keyboard())
    
    return ConversationHandler.END

# ================= MAIN =================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, menu_handler)],
        states={
            USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_username)],
            AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_amount)],
        },
        fallbacks=[CommandHandler("start", start)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)
    
    # এখানে প্যাটার্নটি আপডেট করা হয়েছে (view_date যোগ করা হয়েছে)
    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^(accept|cancel|view_date):"))
    
    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()