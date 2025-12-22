import os
import re
import asyncio
from threading import Thread
from flask import Flask

from telegram import Update
from telegram.constants import MessageEntityType
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ===================== CONFIG =====================
# ilagay dito Telegram user_id mo (numeric)
OWNER_ID = int(os.getenv("OWNER_ID", "0"))  # set this in Render env vars
# ==================================================

app_web = Flask(__name__)

@app_web.route("/")
def home():
    return "Bot is online!"

def keep_alive():
    port = int(os.environ.get("PORT", 10000))
    Thread(target=lambda: app_web.run(host="0.0.0.0", port=port)).start()

# -------------------- Commands --------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    full_name = user.full_name.strip() if user and user.full_name else "Player"
    start_message = (
        f"HI {full_name.upper()}, I'M KAZEBOT! ðŸ¤–\n\n"
        "WELCOME TO PALARO!\n"
        "Type /help to see what I can do.\n"
        "Please stay active and cooperative.\n\n"
        "Good luck and have fun!😁"
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
            f"HELLO {full}, WELCOME TO PALARO! ðŸŽ®ðŸ”¥\n\n"
            "THANK YOU FOR JOINING US THIS SEASON! KINDLY REVIEW THE PINNED RULES BEFORE PROCEEDING.\n\n"
            "STAY ACTIVE AND FOLLOW ANNOUNCEMENTS FOR UPDATES.\n\n"
            "IF YOU HAVEN'T JOINED OUR MAIN CHANNEL YET, PLEASE JOIN HERE:\n"
            "https://t.me/+wkXVYyqiRYplZjk1"
        )
        await chat.send_message(welcome_message, disable_web_page_preview=True)

# -------------------- Helpers --------------------
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
    if re.search(r"(https?://|www\.|t\.me/|telegram\.me/)", text, re.I):
        return True

    entities = (msg.entities or []) + (msg.caption_entities or [])
    for e in entities:
        if e.type in (MessageEntityType.URL, MessageEntityType.TEXT_LINK):
            return True
    return False

# -------------------- Moderation --------------------
async def moderate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.from_user:
        return

    user_id = msg.from_user.id

    # Owner exception (ikaw)
    if OWNER_ID and user_id == OWNER_ID:
        return

    try:
        # optional: allow admins/creator (except owner already handled above)
        member = await context.bot.get_chat_member(msg.chat.id, user_id)
        if member.status in ("administrator", "creator"):
            return

        # Rule 1: delete any forwarded message
        if msg_is_forwarded(msg):
            await msg.delete()
            warn = await msg.chat.send_message("Forwarded messages are not allowed.")
            await asyncio.sleep(5)
            try:
                await warn.delete()
            except Exception:
                pass
            return

        # Rule 2: delete any link (kahit hindi forwarded)
        if msg_has_link(msg):
            await msg.delete()
            warn = await msg.chat.send_message("Links are not allowed.")
            await asyncio.sleep(5)
            try:
                await warn.delete()
            except Exception:
                pass

    except Exception as e:
        print("moderate error:", e)

# -------------------- Main --------------------
def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN env var in Render.")

    app = Application.builder().token(token).build()

    # moderation first
    app.add_handler(MessageHandler(filters.ALL, moderate), group=0)

    # others
    app.add_handler(CommandHandler("start", start), group=1)
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome), group=1)

    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    keep_alive()
    main()
