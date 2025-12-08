import os
import json
import asyncio
import time
from datetime import datetime, timedelta
from pathlib import Path
import secrets
import io
from flask import Flask
from flask import Flask
from threading import Thread
import os

app_web = Flask('')

@app_web.route('/')
def home():
    return "Bot is online!"

def keep_alive():
    port = int(os.environ.get("PORT", 10000))
    Thread(target=lambda: app_web.run(host="0.0.0.0", port=port)).start()
    
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputFile,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# ---------------- ENVIRONMENT VARIABLES ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID"))

if not BOT_TOKEN:
    raise SystemExit("❌ BOT_TOKEN missing in Render environment.")

# ---------------- DIRECTORIES ----------------
FILES_DIR = Path("files")
ASSETS_DIR = Path("assets")
KEYS_FILE = Path("keys.json")

FILES_DIR.mkdir(exist_ok=True)
ASSETS_DIR.mkdir(exist_ok=True)

if not KEYS_FILE.exists():
    KEYS_FILE.write_text(json.dumps({"keys": {}, "users": {}}, indent=2))

PH_TIME = lambda: datetime.now().strftime("%Y-%m-%d %I:%M %p")

# ---------------- LOAD KEY SYSTEM ----------------
def load_keys():
    try:
        data = json.loads(KEYS_FILE.read_text())
        if "keys" not in data: data["keys"] = {}
        if "users" not in data: data["users"] = {}
        return data
    except:
        KEYS_FILE.write_text(json.dumps({"keys": {}, "users": {}}, indent=2))
        return {"keys": {}, "users": {}}

def save_keys(data):
    KEYS_FILE.write_text(json.dumps(data, indent=2))

# make random key
def make_key(length=8):
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789"
    return "".join(secrets.choice(chars) for _ in range(length))

def parse_duration(text):
    text = text.lower().strip()
    if text in ("life", "lifetime"):
        return None
    if text.endswith("d"):
        return int(text[:-1]) * 86400
    if text.endswith("h"):
        return int(text[:-1]) * 3600
    return 86400

async def is_user_authorized(uid):
    data = load_keys()
    kid = data["users"].get(str(uid))
    if not kid: return False
    info = data["keys"].get(kid)
    if not info: return False
    exp = info.get("expires_at")
    if exp is None: return True
    return time.time() <= exp

# ---------------- /start ----------------
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not await is_user_authorized(user.id):
        await update.message.reply_text(
            f"✨ 𝙒𝙀𝙇𝘾𝙊𝙈𝙀 𝙃𝙄 {user.full_name}! ✨\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🔐 𝙆𝙀𝙔 𝙑𝙀𝙍𝙄𝙁𝙄𝘾𝘼𝙏𝙄𝙊𝙉 𝙍𝙀𝙌𝙐𝙄𝙍𝙀𝘿\n"
            "• Before you can access the generator,\n"
            "• You must enter a valid activation key.\n\n"
            "💠 𝙊𝙉𝙀 𝙆𝙀𝙔 = 𝙇𝙄𝙁𝙀𝙏𝙄𝙈𝙀 𝘼𝘾𝘾𝙀𝙎𝙎\n"
            "✨ Fast activation\n"
            "✨ Secure verification\n\n"
            "🛒 Buy key here: @KAZEHAYAMODZ\n"
            "━━━━━━━━━━━━━━━━━━━━━━"
        )
        return

    keyboard = [
        [InlineKeyboardButton("🎮 Valorant", callback_data="valorant"),
         InlineKeyboardButton("🤖 Roblox", callback_data="roblox")],

        [InlineKeyboardButton("✨ CODM", callback_data="codm"),
         InlineKeyboardButton("⚔️ Crossfire", callback_data="crossfire")],

        [InlineKeyboardButton("🔰 Facebook", callback_data="facebook"),
         InlineKeyboardButton("📧 Gmail", callback_data="gmail")],

        [InlineKeyboardButton("🙈 Mtacc", callback_data="mtacc"),
         InlineKeyboardButton("🔥 Gaslite", callback_data="gaslite")],

        [InlineKeyboardButton("♨️ Bloodstrike", callback_data="bloodstrike"),
         InlineKeyboardButton("🎲 Random", callback_data="random")],

        [InlineKeyboardButton("⚡ 100082", callback_data="100082")],
    ]

    intro = ASSETS_DIR / "Telegram.mp4"
    if intro.exists():
        await update.message.reply_video(
            video=FSInputFile(intro),
            caption="✨ Select an account type:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    else:
        await update.message.reply_text(
            "✨ Select an account type:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

# ---------------- /genkey ----------------
async def genkey_cmd(update, context):
    if update.effective_user.id != ADMIN_CHAT_ID:
        return await update.message.reply_text("⛔ Forbidden")

    duration = context.args[0] if context.args else "1d"
    expires = parse_duration(duration)
    data = load_keys()

    k = make_key(8)
    exp_time = None if expires is None else time.time() + expires

    data["keys"][k] = {
        "used": False,
        "owner": None,
        "created_by": ADMIN_CHAT_ID,
        "created_at": time.time(),
        "expires_at": exp_time,
    }
    save_keys(data)

    exp_disp = "Lifetime" if exp_time is None else PH_TIME()

    msg = (
        "━━━━━━━━━━━━━━━━━━\n"
        "✨ 𝐊𝐄𝐘 𝐆𝐄𝐍𝐄𝐑𝐀𝐓𝐄𝐃\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"🔑 𝐊𝐞𝐲: `{k}`\n"
        f"📅 𝐄𝐱𝐩𝐢𝐫𝐞𝐬: {exp_disp}\n\n"
        "𝐇𝐎𝐖 𝐓𝐎 𝐑𝐄𝐃𝐄𝐄𝐌?\n"
        "1️⃣ Click this link @KAZEHAYAVIPBOT\n"
        "2️⃣ Click start or /start\n"
        "3️⃣ /key (your key)\n"
        f"4️⃣ Example: /key `{k}`\n"
    )

    await update.message.reply_text(msg, parse_mode="Markdown")

# ---------------- /key ----------------
async def key_cmd(update, context):
    user = update.effective_user
    if not context.args:
        return await update.message.reply_text("Usage: /key <KEY>")
    key = context.args[0]

    data = load_keys()
    info = data["keys"].get(key)
    if not info:
        return await update.message.reply_text("❌ Invalid key.")
    if info["used"] and info["owner"] != user.id:
        return await update.message.reply_text("❌ Already used.")
    exp = info.get("expires_at")
    if exp and time.time() > exp:
        return await update.message.reply_text("⏰ Key expired.")

    info["used"] = True
    info["owner"] = user.id
    data["users"][str(user.id)] = key
    save_keys(data)

    await update.message.reply_text("✅ Premium activated!\nUse /start")

# ---------------- /mytime ----------------
async def mytime_cmd(update, context):
    user = update.effective_user
    data = load_keys()
    kid = data["users"].get(str(user.id))
    if not kid:
        return await update.message.reply_text("❌ No key.")
    info = data["keys"].get(kid)
    exp = info.get("expires_at")

    if exp is None:
        return await update.message.reply_text("♾️ Lifetime key.")
    rem = int(exp - time.time())
    if rem <= 0:
        return await update.message.reply_text("⛔ Expired.")

    d = rem // 86400
    h = (rem % 86400) // 3600
    m = (rem % 3600) // 60

    await update.message.reply_text(
        f"⏳ Remaining: {d}d {h}h {m}m"
    )

# ---------------- /revoke ----------------
async def revoke_cmd(update, context):
    if update.effective_user.id != ADMIN_CHAT_ID:
        return await update.message.reply_text("⛔ Forbidden")
    if not context.args:
        return await update.message.reply_text("Usage: /revoke <KEY>")
    k = context.args[0]

    data = load_keys()
    info = data["keys"].pop(k, None)
    if info:
        uid = str(info.get("owner"))
        if uid in data["users"]:
            data["users"].pop(uid)
        save_keys(data)
        await update.message.reply_text(f"Revoked: {k}")
    else:
        await update.message.reply_text("Not found.")

# ---------------- /broadcast ----------------
async def broadcast_cmd(update, context):
    if update.effective_user.id != ADMIN_CHAT_ID:
        return await update.message.reply_text("⛔ Forbidden")
    if not context.args:
        return update.message.reply_text("Usage: /broadcast <message>")

    msg = " ".join(context.args)
    data = load_keys()

    count = 0
    for uid in data["users"]:
        try:
            await context.bot.send_message(uid, f"📢 Owner Notice:\n{msg}")
            count += 1
        except:
            pass

    await update.message.reply_text(f"Sent to {count} users.")

# ---------------- MAIN GENERATOR ----------------
FILE_MAP = {
    "valorant": FILES_DIR / "Valorant.txt",
    "roblox": FILES_DIR / "Roblox.txt",
    "codm": FILES_DIR / "CODM.txt",
    "crossfire": FILES_DIR / "Crossfire.txt",
    "facebook": FILES_DIR / "Facebook.txt",
    "gmail": FILES_DIR / "Gmail.txt",
    "mtacc": FILES_DIR / "Mtacc.txt",
    "gaslite": FILES_DIR / "gaslite.txt",
    "bloodstrike": FILES_DIR / "Bloodstrike.txt",
    "random": FILES_DIR / "Random.txt",
    "100082": FILES_DIR / "100082.txt",
}

user_cool = {}
COOLDOWN = 180

def extract_lines(path, n=100):
    if not path.exists(): return "", 0
    lines = path.read_text(errors="ignore").splitlines()
    if not lines: return "", 0

    take = lines[:n]
    remain = lines[n:]

    path.write_text("\n".join(remain))
    return "\n".join(take), len(take)

async def send_alert(bot, user, typ, count):
    try:
        await bot.send_message(
            ADMIN_CHAT_ID,
            f"📢 New Generation:\n"
            f"User: {user.first_name} ({user.id})\n"
            f"Type: {typ}\n"
            f"Lines: {count}\n"
            f"Time: {PH_TIME()}",
        )
    except:
        pass

async def button_callback(update, context):
    q = update.callback_query
    await q.answer()
    user = q.from_user
    choice = q.data.lower()

    if not await is_user_authorized(user.id):
        return await q.message.reply_text("❌ Not authorized.")

    if choice not in FILE_MAP:
        return await q.message.reply_text("Invalid option.")

    now = time.time()
    if now - user_cool.get(user.id, 0) < COOLDOWN:
        return await q.message.reply_text(f"⏳ Cooldown {COOLDOWN}s")
    user_cool[user.id] = now

    # Loading message
    msg = await q.message.reply_text(f"🔥 Searching {choice} database...")
    await asyncio.sleep(2)
    await msg.delete()

    content, count = extract_lines(FILE_MAP[choice], 100)
    if count == 0:
        return await q.message.reply_text("⚠️ No more lines.")

    bio = io.BytesIO(content.encode())
    bio.name = f"{choice}.txt"

    await q.message.reply_text(
        "✨ Generation Complete!\n"
        f"🗂 Lines: {count}\n"
        f"🔍 Type: {choice.capitalize()}"
    )

    await q.message.reply_document(bio)
    await send_alert(context.bot, user, choice, count)

# ---------------- RUN BOT ----------------
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("genkey", genkey_cmd))
    app.add_handler(CommandHandler("key", key_cmd))
    app.add_handler(CommandHandler("revoke", revoke_cmd))
    app.add_handler(CommandHandler("mytime", mytime_cmd))
    app.add_handler(CommandHandler("broadcast", broadcast_cmd))
    app.add_handler(CallbackQueryHandler(button_callback))

    print("BOT RUNNING on Render...")
    app.run_polling()

if __name__ == "__main__":
    keep_alive()
    asyncio.run(main())
