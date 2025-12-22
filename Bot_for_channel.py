import os
import asyncio
from threading import Thread
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

app_web = Flask(__name__)

@app_web.route("/")
def home():
    return "Bot is online!"

def keep_alive():
    port = int(os.environ.get("PORT", 10000))
    Thread(target=lambda: app_web.run(host="0.0.0.0", port=port)).start()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    full_name = user.full_name.strip() if user.full_name else "Player"
    
    start_message = (
        f"HI {full_name.upper()}, I'M KAZEBOT! 🤖\n\n"
        "WELCOME TO PALARO!\n"
        "Type /help to see what I can do.\n"
        "Please stay active and cooperative.\n\n"
        "Good luck and have fun! 🔥😁"
    )
    
    await update.message.reply_text(start_message)
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    for m in update.message.new_chat_members:
        full = (m.full_name or m.first_name or "Player").strip()
        
        welcome_message = (
            f"HELLO {full}, WELCOME TO PALARO! 🎮🔥\n\n"
            "THANK YOU FOR JOINING US THIS SEASON! KINDLY REVIEW THE PINNED RULES BEFORE PROCEEDING.\n\n"
            "STAY ACTIVE AND FOLLOW ANNOUNCEMENTS FOR UPDATES.\n\n"
            "IF YOU HAVEN'T JOINED OUR MAIN CHANNEL YET, PLEASE JOIN HERE:\n"
            "https://t.me/+wkXVYyqiRYplZjk1"
        )
        
        # Plain text lang – safe, dili mag-crash
        await chat.send_message(welcome_message)

async def anti_spam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    user_id = update.effective_user.id

    # Check kung naay link or forwarded
    has_link = False
    if message.text and ("http://" in message.text or "https://" in message.text or "t.me/" in message.text):
        has_link = True
    if message.caption and ("http://" in message.caption or "https://" in message.caption or "t.me/" in message.caption):
        has_link = True
    if message.forward_from or message.forward_from_chat:
        has_link = True  # Treat forwarded as spam din

    if has_link:
        # Delete ang original message
        await message.delete()

        # Check kung first offense ba
        if context.user_data.get('spam_warning_sent', False):
            # Second+ offense → silent delete lang (wala nay warning)
            return
        else:
            # First offense → send warning
            warning = await context.bot.send_message(
                chat_id=message.chat_id,
                text="⚠️ Links and forwarded messages are not allowed to prevent ads/spam.",
                reply_to_message_id=None
            )
            # Mark nga na-send na ang warning ani nga user
            context.user_data['spam_warning_sent'] = True

            # Auto-delete ang warning human 3 seconds
            await asyncio.sleep(3)
            await warning.delete()
            
def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN env var.")
    
    app = Application.builder().token(token).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))
    
    # ===== ANTI-SPAM / ANTI-LINK FEATURE =====
    # Delete messages with links OR forwarded messages
    app.add_handler(MessageHandler(
        (filters.TEXT | filters.CAPTION) & filters.Regex(r"https?://|t\.me/") | filters.FORWARDED,
        anti_spam
    ))
    
    app.run_polling()

if __name__ == "__main__":
    keep_alive()
    main()
