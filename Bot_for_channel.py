import os
import re
import time
import asyncio
from datetime import timedelta
from threading import Thread
from flask import Flask
from telegram import Update
from telegram.constants import MessageEntityType
from telegram.error import BadRequest
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from Bolt Database import create_client

app_web = Flask(__name__)

# Bolt Database setup
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")
Bolt Database = create_client(SUPABASE_URL, SUPABASE_KEY)

# OWNER_ID from environment variable
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
        f"HI {full_name.upper()}, I'M KAZEBOT!\n\n"
        "WELCOME TO PALARO!\n"
        "Type /help to see what I can do.\n"
        "Please stay active and cooperative.\n\n"
        "Good luck and have fun!"
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
            f"HELLO {full}, WELCOME TO PALARO!\n\n"
            "THANK YOU FOR JOINING US THIS SEASON! KINDLY REVIEW THE PINNED RULES BEFORE PROCEEDING.\n\n"
            "STAY ACTIVE AND FOLLOW ANNOUNCEMENTS FOR UPDATES.\n\n"
            "IF YOU HAVEN'T JOINED OUR MAIN CHANNEL YET, PLEASE JOIN HERE:\n"
            "https://t.me/+wkXVYyqiRYplZjk1"
        )
        await chat.send_message(welcome_message, disable_web_page_preview=True)

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

    if re.search(r"(https?://|www\.|t\.me/|telegram\.me/)", t):
        return True

    if re.search(r"\b[a-z0-9-]+\.(com|net|org|io|co|me|gg|app|xyz|site|dev|ph)\b", t):
        return True

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

    if OWNER_ID and user_id == OWNER_ID:
        return

    try:
        if msg_is_forwarded(msg):
            await msg.delete()
            await send_temp_warning(msg.chat, "⚠️ Forward messages are not allowed to prevent ads/spam.")
            return

        if msg_has_link(msg):
            await msg.delete()
            await send_temp_warning(msg.chat, "⚠️ Links are not allowed kupal!")
            return

    except Exception as e:
        print("moderate error:", e)

async def mute_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /mute @username [duration]\nExample: /mute @noisyplayer 6h")
        return

    username_arg = context.args[0].lstrip('@').lower()
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
            await update.message.reply_text("⚠️ Invalid duration. Use h or d (e.g. 6h, 2d)")
            return

    requester_name = update.effective_user.full_name or "Member"
    original_username = context.args[0].lstrip('@')

    try:
        await supabase.table("mute_requests").insert({
            "group_id": update.effective_chat.id,
            "username": username_arg,
            "original_username": original_username,
            "duration_minutes": int(duration.total_seconds() / 60),
            "duration_text": duration_text,
            "requested_by": requester_name,
            "status": "pending"
        }).execute()

        await update.message.reply_text(
            f"📩 Mute request for @{original_username} ({duration_text}) sent to admins.\n"
            f"Requested by: {requester_name}\nWaiting for approval..."
        )
    except Exception as e:
        print(f"Error storing mute request: {e}")
        await update.message.reply_text("❌ Failed to submit mute request.")

async def approve_mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.message.chat.id
    
    is_authorized = False
    
    if OWNER_ID and user_id == OWNER_ID:
        is_authorized = True
    else:
        try:
            member = await context.bot.get_chat_member(chat_id, user_id)
            is_authorized = member.status in ("administrator", "creator")
        except Exception as e:
            print(f"Error checking member: {e}")
            is_authorized = False
    
    if not is_authorized:
        await update.message.reply_text("❌ Only admins/owner can approve mutes.")
        return
    
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /approve @username")
        return
    
    username_arg = context.args[0].lstrip('@').lower()
    
    try:
        response = supabase.table("mute_requests")\
            .select("*")\
            .eq("username", username_arg)\
            .eq("status", "pending")\
            .maybeSingle()\
            .execute()
        
        if not response.data:
            await update.message.reply_text(f"❌ No pending mute request for that user.")
            return
        
        request = response.data
        original_username = request['original_username']
        duration_minutes = request['duration_minutes']
        duration_text = request['duration_text']
        
        user_chat = await context.bot.get_chat(f"@{original_username}")
        target_user_id = user_chat.id
        
        await context.bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=target_user_id,
            permissions={
                'can_send_messages': False,
                'can_send_media_messages': False,
                'can_send_polls': False,
                'can_send_other_messages': False,
                'can_add_web_page_previews': False,
            },
            until_date=int(time.time() + (duration_minutes * 60))
        )
        
        supabase.table("mute_requests")\
            .update({"status": "approved"})\
            .eq("id", request["id"])\
            .execute()
        
        await update.message.reply_text(
            f"🔇 @{original_username} muted for {duration_text}.\n"
            f"Approved by: {update.effective_user.full_name}"
        )
        
    except BadRequest as e:
        print(f"BadRequest - {e}")
        await update.message.reply_text(f"❌ Cannot find or mute user. Check bot permissions.")
    except Exception as e:
        print(f"Error approving mute: {e}")
        await update.message.reply_text(f"❌ Failed to approve mute.")

async def notify_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    member = update.effective_user
    try:
        chat_member = await update.effective_chat.get_member(member.id)
        
        if chat_member.status in ("administrator", "creator"):
            response = supabase.table("mute_requests")\
                .select("original_username")\
                .eq("status", "pending")\
                .execute()
            
            if response.data and len(response.data) > 0:
                pending_list = "\n".join([f"- @{req['original_username']}" for req in response.data])
                await update.message.reply_text(
                    f"👮 Admin alert! There are pending mute requests:\n{pending_list}\n"
                    "Use /approve @username to approve."
                )
    except Exception as e:
        print(f"Error notifying pending: {e}")

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN env var.")

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("mute", mute_request))
    app.add_handler(CommandHandler("approve", approve_mute))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))
    app.add_handler(MessageHandler(
        (filters.TEXT | filters.CAPTION | filters.FORWARDED) & ~filters.COMMAND,
        moderate
    ))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, notify_pending))

    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    keep_alive()
    main()
    
