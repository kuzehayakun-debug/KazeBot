# ============================
# full bot.py (complete)
# ============================

import os
import json
import asyncio
import time
from datetime import datetime, timedelta
from pathlib import Path
import secrets
import io
from flask import Flask
from threading import Thread
import sqlite3

# Telegram imports
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
    MessageHandler,
    ContextTypes,
    filters
)

# ---------------- web keepalive ----------------
app_web = Flask('')

@app_web.route('/')
def home():
    return "Bot is online!"

def keep_alive():
    port = int(os.environ.get("PORT", 10000))
    Thread(target=lambda: app_web.run(host="0.0.0.0", port=port)).start()

# ---------------- ENV ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))

if not BOT_TOKEN:
    raise SystemExit("❌ BOT_TOKEN missing in environment variables (BOT_TOKEN)")

# ---------------- DIRECTORIES & FILES ----------------
DATA_DIR = Path("data")
FILES_DIR = Path("files")
ASSETS_DIR = Path("assets")
KEYS_FILE = DATA_DIR / "keys.json"

DATA_DIR.mkdir(exist_ok=True)
FILES_DIR.mkdir(exist_ok=True)
ASSETS_DIR.mkdir(exist_ok=True)

if not KEYS_FILE.exists():
    KEYS_FILE.write_text(json.dumps({"keys": {}, "users": {}}, indent=2))

PH_TIME = lambda: datetime.now().strftime("%Y-%m-%d %I:%M %p")

# ---------------- LOAD / SAVE keys (JSON) ----------------
def load_keys():
    try:
        data = json.loads(KEYS_FILE.read_text(encoding="utf-8"))
        if "keys" not in data: data["keys"] = {}
        if "users" not in data: data["users"] = {}
        return data
    except Exception:
        KEYS_FILE.write_text(json.dumps({"keys": {}, "users": {}}, indent=2))
        return {"keys": {}, "users": {}}

def save_keys(data):
    KEYS_FILE.write_text(json.dumps(data, indent=2))

# ---------------- KEY utils ----------------
def make_key(length=8):
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789"
    return "".join(secrets.choice(chars) for _ in range(length))

def generate_full_key(length=8):
    return "Kaze-" + make_key(length)

def get_key(manual_key=None):
    if manual_key:
        return manual_key.strip()
    return generate_full_key()

def parse_duration(text):
    text = text.lower().strip()
    if text in ("life", "lifetime"):
        return None
    if text.endswith("d"):
        return int(text[:-1]) * 86400
    if text.endswith("h"):
        return int(text[:-1]) * 3600
    return 86400

async def is_user_authorized(uid: int):
    data = load_keys()
    kid = data["users"].get(str(uid))
    if not kid:
        return False
    info = data["keys"].get(kid)
    if not info:
        return False
    exp = info.get("expires_at")
    if exp is None:
        return True
    return time.time() <= exp

# ---------------- FILE MAP + helpers ----------------
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
COOLDOWN = 30

def extract_lines(path: Path, n=100):
    if not path.exists():
        return "", 0
    lines = path.read_text(errors="ignore", encoding="utf-8").splitlines()
    if not lines:
        return "", 0
    take = lines[:n]
    remain = lines[n:]
    path.write_text("\n".join(remain), encoding="utf-8")
    return "\n".join(take), len(take)

async def send_alert(bot, user, typ, count):
    try:
        await bot.send_message(
            ADMIN_CHAT_ID,
            f"📣 New Generation:\n"
            f"👤User: {user.first_name} ({user.id})\n"
            f"📁Type: {typ}\n"
            f"📊Lines: {count}\n"
            f"⏱Time: {PH_TIME()}",
        )
    except Exception:
        pass

# ---------------- COMMANDS ----------------
async def generate_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not await is_user_authorized(user.id):
        return await update.message.reply_text("❌ You are not authorized. Please redeem a valid key.")
    keyboard = [
        [InlineKeyboardButton("🎮 Valorant", callback_data="valorant"),
         InlineKeyboardButton("🤖 Roblox", callback_data="roblox")],
        [InlineKeyboardButton("✨ CODM", callback_data="codm"),
         InlineKeyboardButton("⚔️ Crossfire", callback_data="crossfire")],
        [InlineKeyboardButton("📘 Facebook", callback_data="facebook"),
         InlineKeyboardButton("📧 Gmail", callback_data="gmail")],
        [InlineKeyboardButton("🙈 Mtacc", callback_data="mtacc"),
         InlineKeyboardButton("🔥 Gaslite", callback_data="gaslite")],
        [InlineKeyboardButton("♨ Bloodstrike", callback_data="bloodstrike"),
         InlineKeyboardButton("🎲 Random", callback_data="random")],
        [InlineKeyboardButton("⚡ 100082", callback_data="100082")],
    ]
    await update.message.reply_text("✨ Select an account type to generate:", reply_markup=InlineKeyboardMarkup(keyboard))

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not await is_user_authorized(user.id):
        # show the fancy welcome asking for key
        await update.message.reply_text(
            "💫 *WELCOME TO KAZEHAYA MODZ* 💫\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🔐 *ENTER PREMIUM KEY TO UNLOCK*\n"
            "Your generator is protected by a secure access wall.\n\n"
            "🚀 *Once Activated, You Get:*\n"
            "• Instant account generation\n"
            "• Clean + verified combos\n"
            "• CODM / ML / Gaslite / More\n"
            "• VIP-only features\n\n"
            "💸 *KEY STORE:* @KAZEHAYAMODZ",
            parse_mode="Markdown"
        )
        return

    keyboard = [
        [InlineKeyboardButton("⚡ Generate Accounts", callback_data="menu_generate")],
        [InlineKeyboardButton("🛠 Tools Hub", callback_data="menu_tools")],
        [InlineKeyboardButton("📢 Channel", callback_data="menu_channel")],
    ]
    await update.message.reply_text(
        "✨ *Welcome back!* Choose an option below:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ---------------- KEY MANAGEMENT (admin) ----------------
async def genkey_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        return await update.message.reply_text("⛔ Forbidden")
    args = context.args
    manual_key = None
    duration = "1d"
    if len(args) == 1:
        if args[0].lower().endswith(("d", "h")) or args[0].lower() in ("life", "lifetime"):
            duration = args[0]
        else:
            manual_key = args[0]
    elif len(args) >= 2:
        manual_key = args[0]
        duration = args[1]
    key = get_key(manual_key)
    seconds = parse_duration(duration)
    data = load_keys()
    data["keys"][key] = {
        "owner": None,
        "created_at": time.time(),
        "expires_at": None if seconds is None else time.time() + seconds,
        "used": False
    }
    save_keys(data)
    exp = data["keys"][key]["expires_at"]
    exp_text = "Lifetime" if exp is None else datetime.fromtimestamp(exp).strftime("%Y-%m-%d %I:%M %p")
    await update.message.reply_text(
        f"✨ KEY GENERATED\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🔑 Key: `{key}`\n"
        f"📅 Expires: {exp_text}\n\n"
        "HOW TO REDEEM?\n"
        "1️⃣ Open the bot\n"
        "2️⃣ Type /start\n"
        "3️⃣ Type /key (your key)\n"
        f"4️⃣ Example: /key `{key}`",
        parse_mode="Markdown"
    )

async def key_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not context.args:
        return await update.message.reply_text("❌ Usage: `/key <YOUR_KEY>`", parse_mode="Markdown")
    key = context.args[0].strip()
    data = load_keys()
    info = data["keys"].get(key)
    if not info:
        return await update.message.reply_text("❌ Invalid key. Please try again.")
    # ensure defaults
    if "used" not in info:
        info["used"] = False
    if "owner" not in info:
        info["owner"] = None
    # already used by other
    if info["used"] and info["owner"] != user.id:
        return await update.message.reply_text("❌ This key is already used by another user.")
    exp = info.get("expires_at")
    if exp and time.time() > exp:
        return await update.message.reply_text("⏳ This key has expired.")
    # redeem
    info["used"] = True
    info["owner"] = user.id
    data["users"][str(user.id)] = key
    save_keys(data)
    exp_text = "Lifetime" if exp is None else datetime.fromtimestamp(exp).strftime("%Y-%m-%d %I:%M %p")
    premium_msg = (
        "🎉 *REDEEM KEY SUCCESSFUL!*\n\n"
        "⚡ Enjoy faster processing, priority access, and smooth generation!\n\n"
        "🛡 *KEY DETAILS*\n"
        f"🔑 Key: `{key}`\n"
        f"📅 Expires: {exp_text}\n\n"
        "📘 *COMMANDS YOU CAN USE NOW*\n"
        "• /start – Start the bot and generate\n"
        "• /generate – Generate accounts\n"
        "• /mytime – View your license validity\n"
        "• /tools – Access file utilities\n\n"
        "▶ Type /start to begin!"
    )
    await update.message.reply_text(premium_msg, parse_mode="Markdown")

async def mytime_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    data = load_keys()
    kid = data["users"].get(str(user.id))
    if not kid:
        return await update.message.reply_text("❌ No key.")
    info = data["keys"].get(kid, {})
    exp = info.get("expires_at")
    if exp is None:
        return await update.message.reply_text("♾️ Lifetime key.")
    rem = int(exp - time.time())
    if rem <= 0:
        return await update.message.reply_text("⛔ Expired.")
    d = rem // 86400
    h = (rem % 86400) // 3600
    m = (rem % 3600) // 60
    await update.message.reply_text(f"⏳ Remaining: {d}d {h}h {m}m")

async def revoke_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

async def broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        return await update.message.reply_text("⛔ Forbidden")
    if not context.args:
        return await update.message.reply_text("Usage: /broadcast <message>")
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

# ---------------- CALLBACK MENU ----------------
async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = q.from_user
    data_cb = q.data  # renamed to avoid clashing with load_keys var

    # --- GENERATE MENU ---
    if data_cb == "menu_generate":
        gen_keys = [
            [InlineKeyboardButton("🎮 Valorant", callback_data="valorant"),
             InlineKeyboardButton("🤖 Roblox", callback_data="roblox")],
            [InlineKeyboardButton("✨ CODM", callback_data="codm"),
             InlineKeyboardButton("🔥 Gaslite", callback_data="gaslite")],
            [InlineKeyboardButton("📘 Facebook", callback_data="facebook"),
             InlineKeyboardButton("📧 Gmail", callback_data="gmail")],
            [InlineKeyboardButton("♨ Bloodstrike", callback_data="bloodstrike"),
             InlineKeyboardButton("🎲 Random", callback_data="random")],
            [InlineKeyboardButton("📌 100082", callback_data="100082")],
            [InlineKeyboardButton("⬅ Back", callback_data="back_to_home")],
        ]
        return await q.edit_message_text(
            "⚡ *ACCOUNT GENERATION CENTER*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Welcome to the *Premium Account Generator Hub!* 🔥\n"
            "Here, you can instantly generate *fresh*, *filtered*, and *unused* accounts from multiple platforms.\n\n"
            "🚀 *WHAT YOU CAN EXPECT:*\n"
            "• Ultra–fast generation speed\n"
            "• Cleaned & duplicate–free combos\n"
            "• Stable performance even under heavy usage\n"
            "• Updated databases for maximum hit rate\n"
            "• Easy to copy, paste, and use\n\n"
            "📂 *SUPPORTED CATEGORIES:*\n"
            "Choose any platform below. Each category pulls NEW lines directly from the database.\n\n"
            "👇 *SELECT AN ACCOUNT TYPE TO BEGIN:*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(gen_keys)
        )

    # --- TOOLS HUB ---
    if data_cb == "menu_tools":
        tools = [
            [InlineKeyboardButton("📄 TXT Divider", callback_data="tool_divider")],
            [InlineKeyboardButton("🧹 Duplicate Remover", callback_data="tool_dupe")],
            [InlineKeyboardButton("🔗 URL Cleaner", callback_data="tool_url")],
            [InlineKeyboardButton("📂 File Processor", callback_data="tool_file")],
            [InlineKeyboardButton("⬅ Back", callback_data="back_to_home")],
        ]
        return await q.edit_message_text(
            "🛠 *Essential Tools Hub*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(tools)
        )

    # --- CHANNEL ---
    if data_cb == "menu_channel":
        return await q.edit_message_text(
            "📢 *Join our official channel:*\n"
            "👉 https://t.me/+wkXVYyqiRYplZjk1",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅ Back", callback_data="back_to_home")]
            ])
        )

    # --- BACK ---
    if data_cb == "back_to_home":
        home = [
            [InlineKeyboardButton("⚡ Generate Accounts", callback_data="menu_generate")],
            [InlineKeyboardButton("🛠 Tools Hub", callback_data="menu_tools")],
            [InlineKeyboardButton("📢 Channel", callback_data="menu_channel")],
        ]
        return await q.edit_message_text(
            "✨ *Welcome back!* Choose an option:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(home)
        )

    # --- TOOL ACTIONS (set mode in user_data) ---
    if data_cb == "tool_divider":
        context.user_data["tool_mode"] = "divider"
        context.user_data["await_lines"] = True
        return await q.edit_message_text("📄 TXT Divider selected.\n\n➡ Enter number of lines per file:", parse_mode="Markdown")
    if data_cb == "tool_dupe":
        context.user_data["tool_mode"] = "dupe"
        return await q.edit_message_text("🧹 Duplicate Remover selected.\nSend TXT file now.", parse_mode="Markdown")
    if data_cb == "tool_url":
        context.user_data["tool_mode"] = "url"
        return await q.edit_message_text("🔗 URL Cleaner selected.\nSend TXT file now.", parse_mode="Markdown")
    if data_cb == "tool_file":
        context.user_data["tool_mode"] = "fileproc"
        return await q.edit_message_text("📂 File Processor selected.\nSend TXT file now.", parse_mode="Markdown")

    # --- GENERATION HANDLER (if button corresponds to file keys) ---
    if data_cb in FILE_MAP:
        choice = data_cb
        if not await is_user_authorized(user.id):
            return await q.message.reply_text("❌ Not authorized.")
        now = time.time()
        if now - user_cool.get(user.id, 0) < COOLDOWN:
            return await q.message.reply_text(f"⏳ Please wait {COOLDOWN}s.")
        user_cool[user.id] = now
        msg = await q.message.reply_text(f"🔥 Searching {choice} database…")
        await asyncio.sleep(1.2)
        await msg.delete()
        content, count = extract_lines(FILE_MAP[choice], 100)
        await send_alert(context.bot, user, choice, count)
        if count == 0:
            return await q.message.reply_text("⚠️ No more lines.")
        bio = io.BytesIO(content.encode())
        bio.name = f"{choice}.txt"
        caption = (
            "🎉 GENERATION COMPLETED!\n\n"
            f"📁 Target: {choice}\n"
            f"📊 Lines: {count}\n"
            "🧹 Duplicates: Removed\n"
            f"🕒 Time: {datetime.now().strftime('%H:%M:%S')}\n\n"
            "🤖 Powered by @KAZEHAYAMODZ\n"
            "💎 Thank you for using premium service!"
        )
        return await q.message.reply_document(
            document=bio,
            filename=f"{choice}.txt",
            caption=caption
        )

    # fallback
    await q.answer("Unknown option.", show_alert=False)

# ---------------- FILE HANDLER for Tools ----------------
async def number_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # used when user sets the lines-per-file for divider
    if context.user_data.get("await_lines"):
        try:
            num = int(update.message.text)
            if num <= 0:
                return await update.message.reply_text("⚠️ Number must be greater than 0.")
        except:
            return await update.message.reply_text("❌ Please enter a valid number.")
        context.user_data["lines_per_file"] = num
        context.user_data["await_lines"] = False
        return await update.message.reply_text(f"✅ Divider set to *{num} lines per file*.\nNow send your TXT file.", parse_mode="Markdown")
    # else ignore here (other text handlers may handle)

async def file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ensure file/document exists
    if not update.message.document:
        return await update.message.reply_text("❌ Send a TXT file.")
    tool = context.user_data.get("tool_mode")
    file_id = update.message.document.file_id
    file = await context.bot.get_file(file_id)
    data_bytes = await file.download_as_bytearray()
    try:
        content = data_bytes.decode("utf-8", errors="ignore")
    except:
        content = str(data_bytes)
    # TOOL: divider (custom lines)
    if tool == "divider":
        lines_per_file = context.user_data.get("lines_per_file")
        if not lines_per_file:
            return await update.message.reply_text("❌ Please enter number of lines first.")
        lines = content.splitlines()
        parts = [lines[i:i + lines_per_file] for i in range(0, len(lines), lines_per_file)]
        for idx, part in enumerate(parts, 1):
            part_data = "\n".join(part)
            bio = io.BytesIO(part_data.encode())
            bio.name = f"Part{idx}.txt"
            await update.message.reply_document(document=bio, caption=f"📁 Part {idx}")
        return
    # TOOL: duplicate remover
    if tool == "dupe":
        lines = content.splitlines()
        unique = list(dict.fromkeys(lines))
        result = "\n".join(unique)
        bio = io.BytesIO(result.encode()); bio.name = "Cleaned.txt"
        await update.message.reply_document(document=bio, caption="🧹 Duplicates removed")
        return
    # TOOL: URL cleaner
    if tool == "url":
        import re
        cleaned = re.sub(r"http\S+", "", content)
        bio = io.BytesIO(cleaned.encode()); bio.name = "URL_Cleaned.txt"
        await update.message.reply_document(document=bio, caption="🔗 URLs removed")
        return
    # TOOL: generic file processor (example: count lines)
    if tool == "fileproc":
        lines = content.splitlines()
        await update.message.reply_text(f"📄 Received file with {len(lines)} lines.")
        return
    await update.message.reply_text("❗ Please choose a tool first (Tools Hub → select a tool).")

# ---------------- RUN BOT ----------------
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("genkey", genkey_cmd))
    app.add_handler(CommandHandler("key", key_cmd))
    app.add_handler(CommandHandler("revoke", revoke_cmd))
    app.add_handler(CommandHandler("mytime", mytime_cmd))
    app.add_handler(CommandHandler("broadcast", broadcast_cmd))
    app.add_handler(CommandHandler("generate", generate_cmd))

    # Menus (callback query)
    app.add_handler(CallbackQueryHandler(menu_callback, pattern="^(menu_|back_|tool_)"))
    app.add_handler(CallbackQueryHandler(menu_callback, pattern="^(" + "|".join(FILE_MAP.keys()) + ")$"))

    # File and text handlers
    app.add_handler(MessageHandler(filters.Document.ALL, file_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, number_handler))

    print("BOT RUNNING on Render...")
    app.run_polling()

if __name__ == "__main__":
    keep_alive()
    asyncio.run(main())
