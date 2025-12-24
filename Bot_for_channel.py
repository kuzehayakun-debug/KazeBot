import os
import re
import asyncio
from datetime import datetime, timedelta
from threading import Thread
from flask import Flask
from telegram import Update
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
        if getattr(e, "url", "").lower().find("t.me/") != -1 or getattr(e, "url", "").lower().find("telegram.me/") != -1:
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


# ===== MUTE SYSTEM =====
pending_mutes = {}  # user_id -> info dict

async def mute_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "⚠️ Usage: /mute @username [duration]\nExample: /mute @user 6h"
        )
        return

    # Try to resolve user by username or ID
    chat_id = update.effective_chat.id
    username_arg = context.args[0].lstrip("@")
    duration = timedelta(hours=1)  # default

    # parse duration
    if len(context.args) > 1:
        arg = context.args[1].lower()
        try:
            if arg.endswith("h"):
                duration = timedelta(hours=int(arg[:-1]))
            elif arg.endswith("d"):
                duration = timedelta(days=int(arg[:-1]))
        except:
            pass

    try:
        # Get user object
        target_member = await context.bot.get_chat_member(chat_id, username_arg)
        target_user = target_member.user
    except:
        await update.message.reply_text(f"❌ Failed to find user {username_arg}.")
        return

    # Save pending mute by user_id
    pending_mutes[target_user.id] = {
        "requester": update.effective_user.full_name,
        "duration": duration,
        "username": target_user.username or target_user.full_name
    }

    await update.message.reply_text(
        f"📩 Mute request for @{pending_mutes[target_user.id]['username']} ({duration}) saved.\n"
        f"Requested by: {update.effective_user.full_name}\nWaiting for admin/owner approval..."
    )

async def approve_mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    member = await update.effective_chat.get_member(update.effective_user.id)
    if member.status not in ("administrator", "creator"):
        await update.message.reply_text("❌ Only admins/owner can approve mutes.")
        return

    if not context.args:
        await update.message.reply_text("⚠️ Usage: /approve <user_id>")
        return

    try:
        target_id = int(context.args[0])
    except:
        await update.message.reply_text("❌ Invalid user ID.")
        return

    if target_id not in pending_mutes:
        await update.message.reply_text("❌ No pending mute request for this user.")
        return

    request = pending_mutes[target_id]

    try:
        until = int((datetime.now() + request["duration"]).timestamp())
        await context.bot.restrict_chat_member(
            chat_id=update.effective_chat.id,
            user_id=target_id,
            permissions={
                "can_send_messages": False,
                "can_send_media_messages": False,
                "can_send_polls": False,
                "can_send_other_messages": False,
                "can_add_web_page_previews": False
            },
            until_date=until
        )

        await update.message.reply_text(
            f"🔇 @{request['username']} has been muted for {request['duration']}.\n"
            f"Approved by: {update.effective_user.full_name}\n"
            f"Originally requested by: {request['requester']}"
        )

        del pending_mutes[target_id]

    except Exception as e:
        await update.message.reply_text(
            f"❌ Failed to mute @{request['username']}. User may have left or bot lacks permission."
        )


async def notify_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    member = update.effective_user
    chat_member = await update.effective_chat.get_member(member.id)

    if chat_member.status in ("administrator", "creator") and pending_mutes:
        pending_list = "\n".join([f"- {info['username']}" for info in pending_mutes.values()])
        await update.message.reply_text(
            f"👮 Admin alert! There are pending mute requests:\n{pending_list}\n"
            "Use /approve <user_id> to approve."
        )


# ===== START COMMAND =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    full_name = user.full_name if user else "Player"
    await update.message.reply_text(
        f"Hi {full_name}! I'm your moderation bot.\n"
        "- I block forwarded messages\n"
        "- I block t.me links\n"
        "- Use /mute and /approve to manage members (admins/owner only)"
    )


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
    # Notify admins on message
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, notify_pending))

    app.run_polling(allowed_updates=Update.ALL_TYPES)


# ===== RUN =====
if __name__ == "__main__":
    keep_alive()
    main()
