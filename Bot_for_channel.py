import os
import re
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
        f"HI {full_name.upper()}, I'M KAZEBOT! 🤖🎮\n\n"
        "WELCOME TO PALARO!\n"
        "Type /help to see what I can do.\n"
        "Please stay active and cooperative.\n\n"
        "Good luck and have fun! 🔥🏆"
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
        
        await chat.send_message(welcome_message)

# ===== ANTI-SPAM: AUTO DELETE LINKS & FORWARDED MESSAGES (EXCEPT OWNER) =====
async def anti_spam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.from_user:
        return

    user_id = msg.from_user.id

    # Kuhaa ang OWNER_ID gikan sa Render environment variable (safe gyud ni!)
    OWNER_ID = int(os.getenv("BOT_OWNER_ID", "0"))  # Default 0 kung wala

    # Exempt ang owner – ikaw ra pwede mag-link ug mag-forward
    if user_id == OWNER_ID:
        return

    # Check kung forwarded message
    is_forwarded = bool(
        msg.forward_origin or
        msg.forward_from or
        msg.forward_from_chat or
        msg.forward_sender_name
    )

    # Check kung naay link
    has_link = False
    text = (msg.text or msg.caption or "")
    if re.search(r"https?://|www\.|t\.me/", text, re.IGNORECASE):
        has_link = True
    entities = (msg.entities or []) + (msg.caption_entities or [])
    for entity in entities:
        if entity.type in ("url", "text_link"):
            has_link = True
            break

    # Kung forwarded or naay link → auto delete (silent lang)
    if is_forwarded or has_link:
        try:
            await msg.delete()
        except:
            pass  # Kung dili pwede i-delete

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN env var.")
    
    app = Application.builder().token(token).build()
    
    # Regular handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))
    
    # ANTI-SPAM HANDLER – delete links & forwarded messages (except owner)
    app.add_handler(MessageHandler(
        filters.TEXT | filters.CAPTION | filters.FORWARDED,
        anti_spam
    ))
    
    app.run_polling()

if __name__ == "__main__":
    keep_alive()
    main()
