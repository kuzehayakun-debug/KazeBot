import os
import re
import asyncio
from threading import Thread
from flask import Flask
from datetime import datetime, timedelta
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

    if "t.me/" in t or "telegram.me/" in t:
        return True

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

# ===== PENDING MUTES STORAGE =====
pending_mutes = {}

# ===== MODERATION FUNCTION =====
async def moderate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.from_user:
        return

    user_id = msg.from_user.id

    # OWNER exception
    if OWNER_ID and user_id == OWNER_ID:
        # Notify pending mutes if any
        if pending_mutes:
            pending_list = "\n".join([f"- @{u}" for u in pending_mutes.keys()])
            await msg.reply_text(f"👮 There are pending mute requests:\n{pending_list}\nUse /approve @username to approve.")
        return

    # ADMIN / CREATOR exception
    try:
        member = await context.bot.get_chat_member(msg.chat.id, user_id)
        if member.status in ("administrator", "creator"):
            # Notify pending mutes if any
            if pending_mutes:
                pending_list = "\n".join([f"- @{u}" for u in pending_mutes.keys()])
                await msg.reply_text(f"👮 There are pending mute requests:\n{pending_list}\nUse /approve @username to approve.")
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
            await send_temp_warning(msg.chat, "⚠️ telegram links are not allowed!")
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

# ===== MUTE REQUEST =====
async def mute_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /mute @username [duration]\nExample: /mute @noisyplayer 6h")
        return

    username_arg = context.args[0].lstrip("@")
    duration = timedelta(hours=1)
    duration_text = "1 hour"

    if len(context.args) > 1:
        arg = context.args[1].lower()
        try:
            if arg.endswith("h"):
                hours = int(arg[:-1])
                duration = timedelta(hours=hours)
                duration_text = f"{hours} hour{'s' if hours > 1 else ''}"
            elif arg.endswith("d"):
                days = int(arg[:-1])
                duration = timedelta(days=days)
                duration_text = f"{days} day{'s' if days > 1 else ''}"
        except:
            await update.message.reply_text("⚠️ Invalid duration. Use h or d (e.g. 6h, 2d)")
            return

    requester_name = update.effective_user.full_name or update.effective_user.username
    pending_mutes[username_arg.lower()] = {"requester": requester_name, "duration": duration, "duration_text": duration_text}
    await update.message.reply_text(
        f"📩 Mute request for @{username_arg} ({duration_text}) has been sent to admins.\n"
        f"Requested by: {requester_name}\nWaiting for approval..."
    )

# ===== APPROVE MUTE =====
async def approve_mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    member = await update.effective_chat.get_member(update.effective_user.id)
    if member.status not in ("administrator", "creator"):
        await update.message.reply_text("❌ Only admins/owner can approve mutes.")
        return

    if not context.args:
        await update.message.reply_text("⚠️ Usage: /approve @username")
        return

    username_arg = context.args[0].lstrip("@").lower()
    if username_arg not in pending_mutes:
        await update.message.reply_text(f"❌ No pending mute request for @{username_arg}")
        return

    request = pending_mutes[username_arg]
    chat_id = update.message.chat.id

    try:
        # Get user ID from username
        target_member = await context.bot.get_chat_member(chat_id, f"@{username_arg}")
        target_user = target_member.user

        await context.bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=target_user.id,
            permissions={
                "can_send_messages": False,
                "can_send_media_messages": False,
                "can_send_polls": False,
                "can_send_other_messages": False,
                "can_add_web_page_previews": False,
            },
            until_date=int(datetime.now().timestamp() + request["duration"].total_seconds()),
        )

        await update.message.reply_text(
            f"🔇 @{username_arg} has been muted for {request['duration_text']}.\n"
            f"Approved by: {update.effective_user.full_name}\n"
            f"Originally requested by: {request['requester']}"
        )

        del pending_mutes[username_arg]

    except Exception as e:
        await update.message.reply_text(f"❌ Failed to mute @{username_arg}. User may have left or I lack permission.")

# ===== MAIN FUNCTION =====
def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN env var.")

    app = Application.builder().token(token).build()

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("mute", mute_request))
    app.add_handler(CommandHandler("approve", approve_mute))

    # Moderation
    app.add_handler(MessageHandler((filters.TEXT | filters.CAPTION | filters.FORWARDED) & ~filters.COMMAND, moderate))

    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    keep_alive()
    main()
