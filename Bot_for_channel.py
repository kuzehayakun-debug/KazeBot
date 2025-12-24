import os
import re
import asyncio
from threading import Thread
from flask import Flask
from datetime import datetime
import pytz
from telegram import Update, MessageEntity
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# ===== WEBKEEP ALIVE =====
app_web = Flask(__name__)
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

@app_web.route("/")
def home():
    return "Bot is online!"

def keep_alive():
    port = int(os.environ.get("PORT", 10000))
    Thread(target=lambda: app_web.run(host="0.0.0.0", port=port)).start()

# ===== MODERATION HELPERS =====
def msg_is_forwarded(msg) -> bool:
    return bool(
        getattr(msg, "forward_origin", None)
        or getattr(msg, "forward_date", None)
        or getattr(msg, "forward_from", None)
        or getattr(msg, "forward_from_chat", None)
        or getattr(msg, "forward_sender_name", None)
    )

def msg_has_tme_link(msg) -> bool:
    text = (msg.text or msg.caption or "")[:4096]
    t = text.lower()

    # Block only t.me or telegram.me links in text
    if "t.me/" in t or "telegram.me/" in t:
        return True

    # Check clickable links (entities)
    entities = (msg.entities or []) + (msg.caption_entities or [])
    for e in entities:
        if e.type in (MessageEntity.URL, MessageEntity.TEXT_LINK):
            url = getattr(e, "url", "") or ""
            if "t.me/" in url.lower() or "telegram.me/" in url.lower():
                return True
    return False

async def send_temp_warning(chat, text: str, seconds: int = 5):
    warn = await chat.send_message(text)
    await asyncio.sleep(seconds)
    try:
        await warn.delete()
    except Exception:
        pass

# ===== MODERATION FUNCTION =====
async def moderate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.from_user:
        return

    user_id = msg.from_user.id

    # OWNER exception
    if OWNER_ID and user_id == OWNER_ID:
        return

    # ADMIN / CREATOR exception
    try:
        member = await context.bot.get_chat_member(msg.chat.id, user_id)
        if member.status in ("administrator", "creator"):
            return
    except Exception:
        pass

    try:
        # DELETE forwarded messages
        if msg_is_forwarded(msg):
            await msg.delete()
            await send_temp_warning(msg.chat, "⚠️ Forward messages are not allowed!")
            return

        # DELETE t.me links
        if msg_has_tme_link(msg):
            await msg.delete()
            await send_temp_warning(msg.chat, "⚠️ t.me links are not allowed!")
            return

    except Exception as e:
        print("moderate error:", e)

# ===== START COMMAND =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    full_name = user.full_name.strip() if user and user.full_name else "Player"
    await update.message.reply_text(
        f"HI {full_name.upper()}, I AM KAZEBOT! 🤖\n"
        "I WILL HELP MODERATE THIS CHANNEL.\n"
        "Forwarded messages and t.me links are not allowed!"
    )

# ===== MAIN FUNCTION =====
def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")  # <-- siguraduhing kapareho sa Render env var
    if not token:
        raise RuntimeError("Missing TELEGRAM_TOKEN env var.")

    app = Application.builder().token(token).build()

    # Commands
    app.add_handler(CommandHandler("start", start))

    # Moderation
    app.add_handler(
        MessageHandler(
            (filters.TEXT | filters.CAPTION | filters.FORWARDED) & ~filters.COMMAND,
            moderate
        )
    )

    app.run_polling(allowed_updates=Update.ALL_TYPES)

# ===== RUN =====
if __name__ == "__main__":
    keep_alive()
    main()
