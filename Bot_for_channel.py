import os
import re
import asyncio
from threading import Thread
from flask import Flask
from telegram import Update
from telegram.constants import MessageEntityType
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

app_web = Flask(__name__)

# OWNER_ID from Render environment variable (numeric Telegram user id mo)
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

@app_web.route("/")
def home():
    return "Bot is online!"

def keep_alive():
    port = int(os.environ.get("PORT", 10000))
    Thread(target=lambda: app_web.run(host="0.0.0.0", port=port)).start()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    full_name = user.full_name.strip() if user and user.full_name else "Player"

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
    msg = update.message
    if not msg or not msg.new_chat_members:
        return

    for m in msg.new_chat_members:
        full = (m.full_name or m.first_name or "Player").strip()

        welcome_message = (
            f"HELLO {full}, WELCOME TO PALARO! 🎮🔥\n\n"
            "THANK YOU FOR JOINING US THIS SEASON! KINDLY REVIEW THE PINNED RULES BEFORE PROCEEDING.\n\n"
            "STAY ACTIVE AND FOLLOW ANNOUNCEMENTS FOR UPDATES.\n\n"
            "IF YOU HAVEN'T JOINED OUR MAIN CHANNEL YET, PLEASE JOIN HERE:\n"
            "https://t.me/+wkXVYyqiRYplZjk1"
        )

        await chat.send_message(welcome_message, disable_web_page_preview=True)


# -------------------- Moderation Helpers --------------------
def msg_is_forwarded(msg) -> bool:
    return bool(
        getattr(msg, "forward_origin", None)
        or getattr(msg, "forward_date", None)
        or getattr(msg, "forward_from", None)
        or getattr(msg, "forward_from_chat", None)
        or getattr(msg, "forward_sender_name", None)
    )

def msg_has_link(msg) -> bool:
    text = (msg.text or msg.caption or "")[:4096]
    t = text.lower()

    # common link patterns
    if re.search(r"(https?://|www\.|t\.me/|telegram\.me/)", t):
        return True

    # plain domains without http(s), ex: google.com
    if re.search(r"\b[a-z0-9-]+\.(com|net|org|io|co|me|gg|app|xyz|site|dev|ph)\b", t):
        return True

    # telegram entities (clickable links)
    entities = (msg.entities or []) + (msg.caption_entities or [])
    for e in entities:
        if e.type in (MessageEntityType.URL, MessageEntityType.TEXT_LINK):
            return True

    return False

async def send_temp_warning(chat, text: str, seconds: int = 5):
    warn = await chat.send_message(text)
    await asyncio.sleep(seconds)
    try:
        await warn.delete()
    except Exception:
        pass


async def moderate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.from_user:
        return

    user_id = msg.from_user.id

    # OWNER exception: ikaw pwede mag-forward at mag-link
    if OWNER_ID and user_id == OWNER_ID:
        return

    # Optional: if you want admins also allowed, uncomment below:
    # member = await context.bot.get_chat_member(msg.chat.id, user_id)
    # if member.status in ("administrator", "creator"):
    #     return

    try:
        # delete forwarded messages
        if msg_is_forwarded(msg):
            await msg.delete()
            await send_temp_warning(msg.chat, "No forward allowed.")
            return

        # delete link messages (kahit normal chat)
        if msg_has_link(msg):
            await msg.delete()
            await send_temp_warning(msg.chat, "No chat link allowed.")
            return

    except Exception as e:
        print("moderate error:", e)


def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN env var.")

    app = Application.builder().token(token).build()

    # Moderation FIRST (group=0)
    app.add_handler(MessageHandler(filters.ALL, moderate), group=0)

    # Other handlers
    app.add_handler(CommandHandler("start", start), group=1)
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome), group=1)

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    keep_alive()
    main()
