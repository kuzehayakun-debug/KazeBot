import os
import json
import asyncio
import time
import threading
import socketserver
from http.server import SimpleHTTPRequestHandler
from datetime import datetime
from pathlib import Path
import secrets
import io

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# ======================================================
# ENV VARS
# ======================================================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))
TARGET_CHAT = ADMIN_CHAT_ID   # <---- IMPORTANT, ADDED FIX

if not BOT_TOKEN:
    raise SystemExit("❌ BOT_TOKEN missing in Render environment.")

# ======================================================
# DIRECTORIES & FILES
# ======================================================
FILES_DIR = Path("files")
ASSETS_DIR = Path("assets")
KEYS_FILE = Path("keys.json")

FILES_DIR.mkdir(exist_ok=True)
ASSETS_DIR.mkdir(exist_ok=True)

if not KEYS_FILE.exists():
    KEYS_FILE.write_text(json.dumps({"keys": {}, "users": {}}, indent=2))

PH_TIME = lambda: datetime.now().strftime("%Y-%m-%d %I:%M %p")

# ======================================================
# KEY SYSTEM
# ======================================================
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

# ======================================================
# /start
# ======================================================
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if not await is_user_authorized(user.id):
        return await update.message.reply_text(
            "🔐 Please enter a valid key first.\nUse: /key <yourkey>"
        )

    keyboard = [
        [InlineKeyboardButton("🎮 Valorant", callback_data="valorant"),
         InlineKeyboardButton("🤖 Roblox", callback_data="roblox")],
        [InlineKeyboardButton("✨ CODM", callback_data="codm"),
         InlineKeyboardButton("⚔️ Crossfire", callback_data="crossfire")],
    ]

    await update.message.reply_text(
        "✨ Select an account type:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

# ======================================================
# GENERATOR SYSTEM
# ======================================================
FILES = {
    "valorant": FILES_DIR / "Valorant.txt",
    "roblox": FILES_DIR / "Roblox.txt",
    "codm": FILES_DIR / "CODM.txt",
    "crossfire": FILES_DIR / "Crossfire.txt",
}

user_cool = {}
COOLDOWN = 15

def extract_lines(path, n=100):
    if not path.exists(): return "", 0
    lines = path.read_text(errors="ignore").splitlines()
    if not lines: return "", 0
    take = lines[:n]
    remain = lines[n:]
    path.write_text("\n".join(remain))
    return "\n".join(take), len(take)

async def button_callback(update, context):
    q = update.callback_query
    await q.answer()
    user = q.from_user
    choice = q.data.lower()

    if choice not in FILES:
        return await q.message.reply_text("Invalid.")

    now = time.time()
    if now - user_cool.get(user.id, 0) < COOLDOWN:
        return await q.message.reply_text(f"⏳ Cooldown {COOLDOWN}s")
    user_cool[user.id] = now

    msg = await q.message.reply_text(f"🔥 Searching {choice} database...")
    await asyncio.sleep(1)
    await msg.delete()

    content, count = extract_lines(FILES[choice], 100)
    if count == 0:
        return await q.message.reply_text("⚠️ No more lines.")

    bio = io.BytesIO(content.encode())
    bio.name = f"{choice}.txt"

    await q.message.reply_document(bio)

# ======================================================
# AUTO SEND MESSAGE
# ======================================================
async def auto_task(app):
    while True:
        try:
            await app.bot.send_message(
                TARGET_CHAT,
                f"Hello pogi 😍\nAuto: {datetime.now()}"
            )
            print("Auto message sent!")
        except Exception as e:
            print("Auto error:", e)

        await asyncio.sleep(600)

# ======================================================
# KEEP ALIVE WEB SERVER (REQUIRED)
# ======================================================
def keep_alive():
    port = int(os.environ.get("PORT", 10000))
    with socketserver.TCPServer(("", port), SimpleHTTPRequestHandler) as httpd:
        print(f"Keep-alive server running on port {port}")
        httpd.serve_forever()

# ======================================================
# MAIN BOT
# ======================================================
async def run_bot():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CallbackQueryHandler(button_callback))

    await app.initialize()
    await app.start()

    print("BOT RUNNING...")
    app.create_task(auto_task(app))

    await asyncio.Event().wait()

# ======================================================
# ENTRY POINT
# ======================================================
if __name__ == "__main__":
    threading.Thread(target=keep_alive, daemon=True).start()
    asyncio.run(run_bot())        
