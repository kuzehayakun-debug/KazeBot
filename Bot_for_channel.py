import time
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

# Global pending mutes (lowercase keys para consistent)
pending_mutes = {}

async def mute_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /mute @username or /mute username [duration]\nExample: /mute @noisyplayer 6h")
        return

    original_username = context.args[0].lstrip('@')  # Original case for display
    username_key = original_username.lower()  # Lowercase for storage

    duration = timedelta(hours=1)
    duration_text = "1 hour"

    if len(context.args) > 1:
        arg = context.args[1].lower()
        try:
            if arg.endswith('h'):
                hours = int(arg[:-1])
                duration = timedelta(hours=hours)
                duration_text = f"{hours} hour{'s' if hours > 1 else ''}"
            elif arg.endswith('d'):
                days = int(arg[:-1])
                duration = timedelta(days=days)
                duration_text = f"{days} day{'s' if days > 1 else ''}"
        except:
            await update.message.reply_text("⚠️ Invalid duration. Use h or d.")
            return

    requester_name = update.effective_user.full_name or "Member"

    # Save pending request (lowercase key)
    pending_mutes[username_key] = {
        'original_username': original_username,
        'requester': requester_name,
        'duration': duration,
        'duration_text': duration_text
    }

    await update.message.reply_text(
        f"📩 Mute request for @{original_username} ({duration_text}) sent to admins.\n"
        f"Requested by: {requester_name}\nWaiting for approval..."
    )

async def approve_mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.message.chat.id

    # OWNER ID CHECK (gikan sa Render env var – sure gyud ni!)
    OWNER_ID = int(os.getenv("OWNER_ID", "0"))

    # Owner always allowed (direct ID check – bypass everything)
    if user_id == OWNER_ID:
        is_authorized = True
    else:
        # Fallback admin check
        try:
            member = await context.bot.get_chat_member(chat_id, user_id)
            is_authorized = member.status in ("administrator", "creator")
        except:
            is_authorized = False

    if not is_authorized:
        await update.message.reply_text("❌ Only admins or owner can approve mutes.")
        return

    if not context.args:
        await update.message.reply_text("⚠️ Usage: /approve @username or /approve username")
        return

    original_username = context.args[0].lstrip('@')
    username_key = original_username.lower()

    if username_key not in pending_mutes:
        await update.message.reply_text(f"❌ No pending mute request for @{original_username}")
        return

    request = pending_mutes[username_key]
    target_username = request['original_username']

    try:
        # Get target user (use original case with @)
        target_member = await context.bot.get_chat_member(chat_id, f"@{target_username}")
        target_user = target_member.user
        target_name = target_user.full_name or target_username

        # MUTE THE USER
        await context.bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=target_user.id,
            permissions={
                'can_send_messages': False,
                'can_send_media_messages': False,
                'can_send_polls': False,
                'can_send_other_messages': False,
                'can_add_web_page_previews': False,
            },
            until_date=int(time.time() + request['duration'].total_seconds())
        )

        await update.message.reply_text(
            f"🔇 @{target_username} ({target_name}) has been muted for {request['duration_text']}.\n"
            f"Approved by: {update.effective_user.full_name}\n"
            f"Requested by: {request['requester']}"
        )

        # Remove from pending
        del pending_mutes[username_key]

    except Exception as e:
        await update.message.reply_text(f"❌ Failed to mute @{target_username}. User may have left the group or bot lacks permission.\nError: {str(e)}")
        
# Optional: Auto-notify admins kung naay pending request pag mo-join or mo-send message
async def notify_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    member = update.effective_user
    chat_member = await update.effective_chat.get_member(member.id)
    
    if chat_member.status in ("administrator", "creator") and pending_mutes:
        pending_list = "\n".join([f"- @{user}" for user in pending_mutes.keys()])
        await update.message.reply_text(
            f"👮 Admin alert! There are pending mute requests:\n{pending_list}\n"
            "Use /approve @username to approve."
        )

# ===== SA MAIN() FUNCTION =====
def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN env var.")

    app = Application.builder().token(token).build()

    # ===== COMMANDS FIRST (para dili ma-block sa filters.ALL) =====
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("mute", mute_request))
    app.add_handler(CommandHandler("approve", approve_mute))

    # ===== STATUS UPDATES (welcome new members) =====
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))

    # ===== ANTI-SPAM / MODERATION (last para dili ma-block ang commands) =====
    # Gamit specific filters ra, dili filters.ALL para dili ma-catch ang commands
    app.add_handler(MessageHandler(
        (filters.TEXT | filters.CAPTION | filters.FORWARDED) & ~filters.COMMAND,
        moderate  # or anti_spam kung mao imong function name
    ))

    # ===== AUTO-NOTIFY PENDING MUTES (kung mo-send message ang admin) =====
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, notify_pending))

    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    keep_alive()
    main()
