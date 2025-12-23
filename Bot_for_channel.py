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
            await send_temp_warning(msg.chat, "⚠️ Forward messages are not allowed to prevent ads/spam.")
            return

        # delete link messages (kahit normal chat)
        if msg_has_link(msg):
            await msg.delete()
            await send_temp_warning(msg.chat, "⚠️ Links are not allowed kupal!")
            return

    except Exception as e:
        print("moderate error:", e)


from datetime import timedelta

# Global storage para sa pending mute requests (simple dict: username -> requester)
pending_mutes = {}

async def mute_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /mute @username or /mute username [duration]\nExample: /mute @noisyplayer or /mute @noisyplayer 6h")
        return

    username_arg = context.args[0].lstrip('@')
    duration_text = "1 hour"  # Default
    duration = timedelta(hours=1)

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
            await update.message.reply_text("⚠️ Invalid duration. Use h or d (e.g. 6h, 2d)")
            return

    requester_name = update.effective_user.full_name or update.effective_user.username

    # Save pending request
    pending_mutes[username_arg.lower()] = {
        'requester': requester_name,
        'duration': duration,
        'duration_text': duration_text
    }

    await update.message.reply_text(
        f"📩 Mute request for @{username_arg} ({duration_text}) has been sent to admins.\n"
        f"Requested by: {requester_name}\n"
        "Waiting for approval..."
    )

async def approve_mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Check kung admin or owner ba ang nag-approve
    member = await update.effective_chat.get_member(update.effective_user.id)
    if member.status not in ("administrator", "creator"):
        await update.message.reply_text("❌ Only admins/owner can approve mutes.")
        return

    if not context.args:
        await update.message.reply_text("⚠️ Usage: /approve @username or /approve username")
        return

    username_arg = context.args[0].lstrip('@').lower()

    if username_arg not in pending_mutes:
        await update.message.reply_text(f"❌ No pending mute request for @{username_arg}")
        return

    request = pending_mutes[username_arg]
    chat_id = update.message.chat.id

    try:
        # Kuhaa ang user ID base sa username
        target_member = await context.bot.get_chat_member(chat_id, f"@{username_arg}")
        target_user = target_member.user
        target_name = target_user.full_name or target_user.username

        # Actual mute
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
            f"🔇 @{username_arg} ({target_name}) has been muted for {request['duration_text']}.\n"
            f"Approved by: {update.effective_user.full_name}\n"
            f"Originally requested by: {request['requester']}"
        )

        # Tanggalon ang pending request
        del pending_mutes[username_arg]

    except Exception as e:
        await update.message.reply_text(f"❌ Failed to mute @{username_arg}. User may have left or I lack permission.")

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

async def detect_kaze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text:
        return

    text = msg.text.lower()

    # detect whole word "kaze"
    if re.search(r"\bkaze\b", text):
        await msg.reply_text("Pogi si Kaze!")

async def detect_kuri(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text:
        return

    text = msg.text.lower()

    # detect whole word "kaze"
    if re.search(r"\bkuri\b", text):
        await msg.reply_text("Pogi")
        
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
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, detect_kaze))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, detect_kuri))

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
            
