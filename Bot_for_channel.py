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

# ===== GLOBAL STORAGE =====
pending_bans = {}  # Pending temp or permanent bans
ban_logs = []      # Stores logs of bans

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
        if e.type in ("url", "text_link"):
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

# ===== MODERATION =====
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
    except:
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

# ===== COMMANDS =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    full_name = user.full_name.strip() if user and user.full_name else "Player"
    await update.message.reply_text(
        f"HI {full_name.upper()}, I AM KAZEBOT! 🤖\n"
        "I WILL HELP MODERATE THIS CHANNEL.\n"
        "Forwarded messages and t.me links are not allowed!"
    )

# ===== BAN REQUESTS =====
async def temp_ban_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not context.args:
        await msg.reply_text("⚠️ Usage: /tempban @username 1h30m reason")
        return
    username = context.args[0].lstrip('@').lower()
    duration_str = context.args[1] if len(context.args) > 1 else "1h"
    reason = " ".join(context.args[2:]) if len(context.args) > 2 else "No reason"

    # Parse duration
    hours, minutes, days = 0, 0, 0
    m_h = re.search(r"(\d+)h", duration_str)
    m_m = re.search(r"(\d+)m", duration_str)
    m_d = re.search(r"(\d+)d", duration_str)
    if m_h: hours = int(m_h.group(1))
    if m_m: minutes = int(m_m.group(1))
    if m_d: days = int(m_d.group(1))
    duration = timedelta(days=days, hours=hours, minutes=minutes)

    pending_bans[username] = {
        "type": "temp",
        "duration": duration,
        "reason": reason,
        "requester": msg.from_user.full_name or msg.from_user.username,
        "time": datetime.now()
    }

    await msg.reply_text(f"📩 Temporary ban request for @{username} saved ({duration}). Waiting for approval.")
    await notify_pending_bans(update, context)

async def perm_ban_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not context.args:
        await msg.reply_text("⚠️ Usage: /permban @username reason")
        return
    username = context.args[0].lstrip('@').lower()
    reason = " ".join(context.args[1:]) if len(context.args) > 1 else "No reason"

    pending_bans[username] = {
        "type": "perm",
        "reason": reason,
        "requester": msg.from_user.full_name or msg.from_user.username,
        "time": datetime.now()
    }

    await msg.reply_text(f"📩 Permanent ban request for @{username} saved. Waiting for approval.")
    await notify_pending_bans(update, context)

# ===== APPROVE BAN =====
async def approve_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    user_id = msg.from_user.id
    chat_id = update.effective_chat.id
    member = await update.effective_chat.get_member(user_id)
    if member.status not in ("administrator", "creator") and user_id != OWNER_ID:
        await msg.reply_text("❌ Only admin/owner can approve bans.")
        return
    if not context.args:
        await msg.reply_text("⚠️ Usage: /approve @username")
        return

    username = context.args[0].lstrip('@').lower()
    if username not in pending_bans:
        await msg.reply_text(f"❌ No pending ban request for @{username}")
        return

    request = pending_bans[username]
    try:
        target_member = await context.bot.get_chat_member(chat_id, f"@{username}")
        target_id = target_member.user.id
    except:
        await msg.reply_text(f"❌ Could not find @{username} in chat.")
        return

    try:
        if request["type"] == "temp":
            until_ts = int((datetime.now() + request["duration"]).timestamp())
            await context.bot.ban_chat_member(chat_id, target_id, until_date=until_ts)
            await msg.reply_text(f"🔒 @{username} TEMP banned for {request['duration']}. Reason: {request['reason']}")
        else:
            await context.bot.ban_chat_member(chat_id, target_id)
            await msg.reply_text(f"🔒 @{username} PERMANENTLY banned. Reason: {request['reason']}")

        # Log
        ban_logs.append({
            "username": username,
            "type": request["type"],
            "reason": request["reason"],
            "approved_by": msg.from_user.full_name,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        del pending_bans[username]
    except Exception:
        await msg.reply_text(f"❌ Failed to ban @{username}. User may have left or bot lacks permission.")

# ===== NOTIFY PENDING BANS =====
async def notify_pending_bans(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not pending_bans: return
    chat_id = update.effective_chat.id
    admins = await context.bot.get_chat_administrators(chat_id)
    pending_list = "\n".join([f"- @{u}" for u in pending_bans.keys()])
    for admin in admins:
        if admin.user.is_bot: continue
        try:
            await context.bot.send_message(admin.user.id,
                f"👮 Pending ban requests:\n{pending_list}\nUse /approve @username to approve.")
        except: pass

# ===== UNBAN =====
async def unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    chat_id = update.effective_chat.id
    if not context.args:
        await msg.reply_text("⚠️ Usage: /unban @username")
        return
    username = context.args[0].lstrip('@').lower()
    try:
        target_member = await context.bot.get_chat_member(chat_id, f"@{username}")
        await context.bot.unban_chat_member(chat_id, target_member.user.id)
        await msg.reply_text(f"✅ @{username} has been unbanned.")
    except:
        await msg.reply_text(f"❌ Failed to unban @{username}. User may have left or bot lacks permission.")

# ===== BAN LOGS =====
async def ban_logs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not ban_logs:
        await update.message.reply_text("No bans yet.")
        return
    lines = []
    for log in ban_logs:
        lines.append(f"- @{log['username']} | {log['type']} | {log['reason']} | Approved by: {log['approved_by']} | {log['time']}")
    text = "\n".join(lines)
    await update.message.reply_text(f"📜 Ban Logs:\n{text}")

# ===== MAIN =====
def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN env var.")

    app = Application.builder().token(token).build()

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tempban", temp_ban_request))
    app.add_handler(CommandHandler("permban", perm_ban_request))
    app.add_handler(CommandHandler("approve", approve_ban))
    app.add_handler(CommandHandler("unban", unban_user))
    app.add_handler(CommandHandler("banlogs", ban_logs_command))

    # Moderation
    app.add_handler(MessageHandler((filters.TEXT | filters.CAPTION | filters.FORWARDED) & ~filters.COMMAND, moderate))

    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    keep_alive()
    main()
