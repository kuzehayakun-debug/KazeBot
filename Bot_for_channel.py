import os
import re
import asyncio
from threading import Thread
from flask import Flask
from telegram import Update
from telegram.constants import MessageEntityType
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
        f"HELLO {full_name.upper()}, I'M KAZEBOT! 🤖\n\n"
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

# -------- Anti-forwarded-links --------
def msg_is_forwarded(msg) -> bool:
    return bool(
        getattr(msg, "forward_origin", None)
        or msg.forward_date
        or msg.forward_from
        or msg.forward_from_chat
        or msg.forward_sender_name
    )

def msg_has_link(msg) -> bool:
    text = (msg.text or msg.caption or "")[:4096]
    if re.search(r"(https?://|www\.)", text, re.I):
        return True
    entities = (msg.entities or []) + (msg.caption_entities or [])
    for e in entities:
        if e.type in (MessageEntityType.URL, MessageEntityType.TEXT_LINK):
            return True
    return False

async def block_forwarded_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return
    try:
        if msg_is_forwarded(msg) and msg_has_link(msg):
            await msg.delete()
            warn = await msg.chat.send_message("⚠️ Links forwarded messages are not allowed to prevent ads/spam.")
            await asyncio.sleep(5)
            try:
                await warn.delete()
            except:
                pass
    except Exception as e:
        # Optional: log e
        pass

async def block_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return

    # (optional) huwag i-delete links galing sa admins
    member = await context.bot.get_chat_member(msg.chat.id, msg.from_user.id)
    if member.status in ("administrator", "creator"):
        return

    try:
        if msg_has_link(msg):   # kahit hindi forwarded
            await msg.delete()
            warn = await msg.chat.send_message("Links are not allowed.")
            await asyncio.sleep(5)
            try:
                await warn.delete()
            except:
                pass
    except:
        pass
        
# -------------------------------------

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN env var.")
    
    app = Application.builder().token(token).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))
    app.add_handler(MessageHandler(filters.ALL, block_links), group=0)
    
    app.run_polling()

if __name__ == "__main__":
    keep_alive()
    main()
