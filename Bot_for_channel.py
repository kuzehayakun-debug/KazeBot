import os
import re
import asyncio
from datetime import datetime, timedelta
from threading import Thread
from flask import Flask
from telegram import Update, ChatPermissions
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# ====== WEBKEEP ALIVE ======
app_web = Flask(__name__)
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

@app_web.route("/")
def home():
    return "Bot is online!"

def keep_alive():
    port = int(os.environ.get("PORT", 10000))
    Thread(target=lambda: app_web.run(host="0.0.0.0", port=port)).start()


# ====== MODERATION HELPERS ======
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
        if hasattr(e, "url"):
            url = e.url or ""
            if "t.me/" in url.lower() or "telegram.me/" in url.lower():
                return True
    return False

async def send_temp_warning(chat, text: str, seconds: int = 5):
    warn = await chat.send_message(text)
    await asyncio.sleep(seconds)
    try:
        await warn.delete()
    except:
        pass

# ====== MODERATION FUNCTION ======
async def moderate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.from_user:
        return
    user_id = msg.from_user.id

    if OWNER_ID and user_id == OWNER_ID:
        return  # Owner allowed

    try:
        member = await context.bot.get_chat_member(msg.chat.id, user_id)
        if member.status in ("administrator", "creator"):
            return  # Admin allowed
    except:
        pass

    try:
        if msg_is_forwarded(msg):
            await msg.delete()
            await send_temp_warning(msg.chat, "⚠️ Forward messages are not allowed!")
            return
        if msg_has_tme_link(msg):
            await msg.delete()
            await send_temp_warning(msg.chat, "⚠️ t.me links are not allowed!")
            return
    except Exception as e:
        print("moderate error:", e)


# ====== START COMMAND ======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    name = user.full_name if user else "Player"
    await update.message.reply_text(
        f"Hi {name}! I am Kazebot 🤖\n"
        "I will help moderate this channel.\n"
        "- Forwarded messages not allowed\n"
        "- t.me links not allowed"
    )


# ====== MUTE SYSTEM ======
pending_mutes = {}  # Store user_id and info

async def mute_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "⚠️ Usage: /mute @username duration reason\nExample: /mute @user 6h Spamming links"
        )
        return

    username_arg = context.args[0].lstrip("@")
    duration = timedelta(hours=1)
    reason = "No reason provided"

    if len(context.args) > 1:
        arg1 = context.args[1].lower()
        if arg1.endswith("h"):
            duration = timedelta(hours=int(arg1[:-1]))
            reason = " ".join(context.args[2:]) if len(context.args) > 2 else reason
        elif arg1.endswith("d"):
            duration = timedelta(days=int(arg1[:-1]))
            reason = " ".join(context.args[2:]) if len(context.args) > 2 else reason
        else:
            reason = " ".join(context.args[1:])

    # Save pending with username (we'll resolve ID later)
    pending_mutes[username_arg.lower()] = {
        "requester": update.effective_user.full_name or update.effective_user.username,
        "duration": duration,
        "reason": reason
    }

    await update.message.reply_text(
        f"📩 Mute request for @{username_arg} ({duration}) saved.\nReason: {reason}\nWaiting for admin/owner approval..."
    )


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
    chat_id = update.effective_chat.id

    # Resolve user_id
    try:
        target_member = await context.bot.get_chat_member(chat_id, f"@{username_arg}")
        target_user = target_member.user
    except:
        await update.message.reply_text(f"❌ Failed to find @{username_arg} in chat.")
        return

    try:
        until = int((datetime.now() + request["duration"]).timestamp())
        await context.bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=target_user.id,
            permissions=ChatPermissions(
                can_send_messages=False,
                can_send_media_messages=False,
                can_send_polls=False,
                can_send_other_messages=False,
                can_add_web_page_previews=False
            ),
            until_date=until
        )

        await update.message.reply_text(
            f"🔇 @{username_arg} has been muted for {request['duration']}.\n"
            f"Reason: {request['reason']}\nApproved by: {update.effective_user.full_name}"
        )

        del pending_mutes[username_arg]

    except Exception as e:
        await update.message.reply_text(
            f"❌ Failed to mute @{username_arg}. User may have left or bot lacks permission."
        )


async def notify_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    member = update.effective_user
    chat_member = await update.effective_chat.get_member(member.id)

    if chat_member.status in ("administrator", "creator") and pending_mutes:
        pending_list = "\n".join([f"- @{user}" for user in pending_mutes.keys()])
        await update.message.reply_text(
            f"👮 Admin alert! There are pending mute requests:\n{pending_list}\n"
            "Use /approve @username to approve."
        )


# ====== MAIN ======
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

    # Notify pending mutes when admin/owner sends message
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, notify_pending))

    app.run_polling(allowed_updates=Update.ALL_TYPES)


# ====== RUN ======
if __name__ == "__main__":
    keep_alive()
    main()
