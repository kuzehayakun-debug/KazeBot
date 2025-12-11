# bot.py
import os
import json
import asyncio
import time
import sqlite3
from datetime import datetime
from pathlib import Path
import secrets
import io
from threading import Thread

from flask import Flask
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    FSInputFile,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ---------------- WEB KEEP-ALIVE (optional for Render) ----------------
app_web = Flask("")

@app_web.route("/")
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

# ---------------- DIRECTORIES & DB ----------------
DATA_DIR = Path("data")
FILES_DIR = Path("files")
ASSETS_DIR = Path("assets")
DB_PATH = DATA_DIR / "database.db"

DATA_DIR.mkdir(exist_ok=True)
FILES_DIR.mkdir(exist_ok=True)
ASSETS_DIR.mkdir(exist_ok=True)

# ---------------- HELPER: time formatting ----------------
PH_TIME = lambda: datetime.now().strftime("%Y-%m-%d %I:%M %p")

# ---------------- SQLITE INIT ----------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS keys (
            key TEXT PRIMARY KEY,
            expires_at INTEGER,
            owner_id INTEGER,
            used INTEGER DEFAULT 0
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            key TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ---------------- DB Helpers ----------------
def save_key_to_db(key, expires_at, owner_id=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    used = 1 if owner_id else 0
    c.execute("INSERT OR REPLACE INTO keys (key, expires_at, owner_id, used) VALUES (?, ?, ?, ?)",
              (key, expires_at, owner_id, used))
    conn.commit()
    conn.close()

def bind_user_to_key(user_id, key):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # update keys table owner
    c.execute("UPDATE keys SET owner_id = ?, used = 1 WHERE key = ?", (user_id, key))
    # upsert user
    c.execute("INSERT OR REPLACE INTO users (user_id, key) VALUES (?, ?)", (user_id, key))
    conn.commit()
    conn.close()

def unbind_user(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT key FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    if row:
        k = row[0]
        c.execute("UPDATE keys SET owner_id = NULL, used = 0 WHERE key = ?", (k,))
    c.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def get_user_key(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT key FROM users WHERE user_id = ?", (user_id,))
    r = c.fetchone()
    conn.close()
    return r[0] if r else None

def get_key_info(key):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT expires_at, owner_id, used FROM keys WHERE key = ?", (key,))
    r = c.fetchone()
    conn.close()
    return r  # (expires_at, owner_id, used) or None

def revoke_key_db(key):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # unbind owner
    c.execute("SELECT owner_id FROM keys WHERE key = ?", (key,))
    r = c.fetchone()
    if r and r[0]:
        c.execute("DELETE FROM users WHERE user_id = ?", (r[0],))
    c.execute("DELETE FROM keys WHERE key = ?", (key,))
    conn.commit()
    conn.close()

# ---------------- KEY UTIL ----------------
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
    return 86400  # default 1 day

# ---------------- AUTH CHECK (async wrapper) ----------------
async def is_user_authorized(uid):
    user_key = get_user_key(uid)
    if not user_key:
        return False
    info = get_key_info(user_key)
    if not info:
        return False
    expires_at = info[0]
    if expires_at is None:
        return True
    return time.time() <= expires_at

# ---------------- FILE GENERATOR ----------------
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
    if not path.exists(): return "", 0
    lines = path.read_text(errors="ignore").splitlines()
    if not lines: return "", 0
    take = lines[:n]
    remain = lines[n:]
    path.write_text("\n".join(remain))
    return "\n".join(take), len(take)

async def send_alert(bot, user, typ, count):
    try:
        username = f"@{user.username}" if user.username else f"{user.first_name}"
        await bot.send_message(
            ADMIN_CHAT_ID,
            f"📢 New Generation:\n"
            f"🔰 User: {username} ({user.id})\n"
            f"📁 Type: {typ}\n"
            f"📊 Lines: {count}\n"
            f"⌛ Time: {PH_TIME()}",
        )
    except:
        pass

# ---------------- COMMANDS ----------------
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not await is_user_authorized(user.id):
        # Welcome for non-premium
        await update.message.reply_text(
            "💫 *HI WELCOME* {}\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🔐 *ENTER PREMIUM KEY TO UNLOCK*\n"
            "Your generator is protected by a secure access wall.\n\n"
            "🚀 *Once Activated, You Get:*\n"
            "• Instant account generation\n"
            "• Clean + verified combos\n"
            "• CODM / ML / Gaslite / More\n\n"
            "💸 *KEY STORE:* @KAZEHAYAMODZ".format(user.first_name),
            parse_mode="Markdown"
        )
        return

    keyboard = [
        [InlineKeyboardButton("⚡ Generate Accounts", callback_data="menu_generate")],
        [InlineKeyboardButton("🛠 Tools Hub", callback_data="menu_tools")],
        [InlineKeyboardButton("📢 Channel", callback_data="menu_channel")],
    ]
    await update.message.reply_text(
        "✨ *Choose an option below:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ---------------- GENKEY (admin) ----------------
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
    elif len(args) == 2:
        manual_key = args[0]
        duration = args[1]

    key = get_key(manual_key)
    seconds = parse_duration(duration)
    expires_at = None if seconds is None else int(time.time() + seconds)
    save_key_to_db(key, expires_at, None)

    exp_text = "♾ Lifetime" if expires_at is None else datetime.fromtimestamp(expires_at).strftime("%Y-%m-%d %I:%M %p")

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

# ---------------- /key (redeem) ----------------
async def key_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not context.args:
        return await update.message.reply_text("❗ Usage: `/key <YOUR_KEY>`", parse_mode="Markdown")
    key = context.args[0].strip()
    info = get_key_info(key)
    if not info:
        return await update.message.reply_text("❌ Invalid key.")
    expires_at, owner_id, used = info
    # if used and owned by different person
    if used and owner_id and owner_id != user.id:
        return await update.message.reply_text("❌ This key is already used by another user.")
    # if expired
    if expires_at and time.time() > expires_at:
        return await update.message.reply_text("⏳ This key has expired.")

    bind_user_to_key(user.id, key)

    exp_text = "♾ Lifetime" if expires_at is None else datetime.fromtimestamp(expires_at).strftime("%Y-%m-%d %I:%M %p")
    premium_msg = (
        "🎉 *REDEEM KEY SUCCESSFUL!*\n\n"
        "⚡ Enjoy faster processing, priority access, and smooth generation!\n\n"
        "🛡 *KEY DETAILS*\n"
        f"🔑 Key: `{key}`\n"
        f"📅 Expires: {exp_text}\n\n"
        "📘 *COMMANDS YOU CAN USE NOW*\n"
        "• /start – Open main menu\n"
        "• /generate – Generate accounts\n"
        "• /mytime – View license validity\n"
        "• /tools – Access file utilities (via menu)\n\n"
        "▶ Type /start to begin!"
    )
    await update.message.reply_text(premium_msg, parse_mode="Markdown")

# ---------------- /mytime ----------------
async def mytime_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    key = get_user_key(user.id)
    if not key:
        return await update.message.reply_text("❌ No key.")
    info = get_key_info(key)
    if not info:
        return await update.message.reply_text("❌ Key data missing.")
    expires_at = info[0]
    if expires_at is None:
        return await update.message.reply_text("♾️ Lifetime key.")
    rem = int(expires_at - time.time())
    if rem <= 0:
        return await update.message.reply_text("⛔ Expired.")
    d = rem // 86400
    h = (rem % 86400) // 3600
    m = (rem % 3600) // 60
    await update.message.reply_text(f"⏳ Remaining: {d}d {h}h {m}m")

# ---------------- /revoke (admin) ----------------
async def revoke_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        return await update.message.reply_text("⛔ Forbidden")
    if not context.args:
        return await update.message.reply_text("Usage: /revoke <KEY>")
    k = context.args[0]
    revoke_key_db(k)
    await update.message.reply_text(f"Revoked: {k}")

# ---------------- /broadcast (admin) ----------------
async def broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        return await update.message.reply_text("⛔ Forbidden")
    if not context.args:
        return await update.message.reply_text("Usage: /broadcast <message>")
    msg = " ".join(context.args)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id FROM users")
    rows = c.fetchall()
    conn.close()
    count = 0
    for (uid,) in rows:
        try:
            await context.bot.send_message(uid, f"📢 Owner Notice:\n{msg}")
            count += 1
        except:
            pass
    await update.message.reply_text(f"Sent to {count} users.")

# ---------------- /generate command (menu) ----------------
async def generate_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not await is_user_authorized(user.id):
        return await update.message.reply_text("❌ You are not authorized. Please redeem a valid key.")
    keyboard = [
        [InlineKeyboardButton("🎮 Valorant", callback_data="valorant"),
         InlineKeyboardButton("🤖 Roblox", callback_data="roblox")],
        [InlineKeyboardButton("✨ CODM", callback_data="codm"),
         InlineKeyboardButton("🔥 Gaslite", callback_data="gaslite")],
        [InlineKeyboardButton("📘 Facebook", callback_data="facebook"),
         InlineKeyboardButton("📧 Gmail", callback_data="gmail")],
        [InlineKeyboardButton("♨ Bloodstrike", callback_data="bloodstrike"),
         InlineKeyboardButton("🎲 Random", callback_data="random")],
        [InlineKeyboardButton("⚡ 100082", callback_data="100082")],
    ]
    await update.message.reply_text("✨ Select an account type to generate:", reply_markup=InlineKeyboardMarkup(keyboard))

# ---------------- MENU CALLBACK ----------------
async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = q.from_user
    data = q.data

    # GENERATE ACCOUNTS MENU (fancy text)
    if data == "menu_generate":
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
        msg = (
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
            "👇 *SELECT AN ACCOUNT TYPE TO BEGIN:*"
        )
        return await q.edit_message_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(gen_keys))

    # TOOLS HUB
    if data == "menu_tools":
        tools = [
            [InlineKeyboardButton("📄 TXT Divider", callback_data="tool_divider")],
            [InlineKeyboardButton("🧹 Duplicate Remover", callback_data="tool_dupe")],
            [InlineKeyboardButton("🔗 URL Cleaner", callback_data="tool_url")],
            [InlineKeyboardButton("📂 File Processor", callback_data="tool_file")],
            [InlineKeyboardButton("⬅ Back", callback_data="back_to_home")],
        ]
        return await q.edit_message_text("🛠 *Essential Tools Hub*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(tools))

    # CHANNEL (open link directly)
    if data == "menu_channel":
        return await q.edit_message_text(
            "📢 Tap the button below to join:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👉 JOIN CHANNEL", url="https://t.me/+wkXVYyqiRYplZjk1")],
                [InlineKeyboardButton("⬅ Back", callback_data="back_to_home")]
            ])
        )

    # BACK HOME
    if data == "back_to_home":
        home = [
            [InlineKeyboardButton("⚡ Generate Accounts", callback_data="menu_generate")],
            [InlineKeyboardButton("🛠 Tools Hub", callback_data="menu_tools")],
            [InlineKeyboardButton("📢 Channel", callback_data="menu_channel")],
        ]
        return await q.edit_message_text("✨ *Choose an option below:*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(home))

    # TOOLS selection: sets mode and prompts user to send a file or number
    if data == "tool_divider":
        context.user_data["tool_mode"] = "divider"
        context.user_data["await_lines"] = True
        return await q.edit_message_text("📄 TXT Divider selected.\n\n➡ Enter number of lines per file:", parse_mode="Markdown")
    if data == "tool_dupe":
        context.user_data["tool_mode"] = "dupe"
        return await q.edit_message_text("🧹 Duplicate Remover selected.\nSend TXT file now.", parse_mode="Markdown")
    if data == "tool_url":
        context.user_data["tool_mode"] = "url"
        return await q.edit_message_text("🔗 URL Cleaner selected.\nSend TXT file now.", parse_mode="Markdown")
    if data == "tool_file":
        context.user_data["tool_mode"] = "file"
        return await q.edit_message_text("📂 File Processor selected.\nSend TXT file now.", parse_mode="Markdown")

    # GENERATION CHOICES (if callback equals file keys)
    if data in FILE_MAP:
        choice = data
        if not await is_user_authorized(user.id):
            return await q.message.reply_text("❌ Not authorized.")
        now = time.time()
        if now - user_cool.get(user.id, 0) < COOLDOWN:
            return await q.message.reply_text(f"⏳ Please wait {COOLDOWN}s.")
        user_cool[user.id] = now
        msg = await q.message.reply_text(f"🔥 Searching {choice} database…")
        await asyncio.sleep(1.5)
        await msg.delete()
        content, count = extract_lines(FILE_MAP[choice], 100)
        await send_alert(context.bot, user, choice, count)
        if count == 0:
            return await q.message.reply_text("⚠️ No more lines.")
        bio = io.BytesIO(content.encode()); bio.name = f"{choice}.txt"
        caption = (
            "🎉 GENERATION COMPLETED!\n\n"
            f"📁 Target: {choice}\n"
            f"📊 Lines: {count}\n"
            "🧹 Duplicates: Removed\n"
            f"🕒 Time: {datetime.now().strftime('%H:%M:%S')}\n\n"
            "🤖 Powered by @KAZEHAYAMODZ\n"
            "💎 Thank you for using premium service!"
        )
        return await q.message.reply_document(bio, filename=f"{choice}.txt", caption=caption)

    await q.answer("Unknown option.", show_alert=False)

# ---------------- FILE HANDLER (TOOLS) ----------------
async def file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.document:
        return await update.message.reply_text("Send a document file (.txt).")
    tool = context.user_data.get("tool_mode")
    file_id = update.message.document.file_id
    file = await context.bot.get_file(file_id)
    content = (await file.download_as_bytearray()).decode("utf-8", errors="ignore")

    # TXT DIVIDER (custom lines)
    if tool == "divider":
        lines_per_file = context.user_data.get("lines_per_file")
        if not lines_per_file:
            return await update.message.reply_text("❌ Please enter number of lines first.")
        lines = content.splitlines()
        parts = [lines[i:i + lines_per_file] for i in range(0, len(lines), lines_per_file)]
        for idx, part in enumerate(parts, 1):
            part_data = "\n".join(part)
            bio = io.BytesIO(part_data.encode()); bio.name = f"Part{idx}.txt"
            await update.message.reply_document(document=bio, caption=f"📁 Part {idx}")
        return

    # DUPLICATE REMOVER
    if tool == "dupe":
        lines = content.splitlines()
        unique = list(dict.fromkeys(lines))
        result = "\n".join(unique)
        bio = io.BytesIO(result.encode()); bio.name = "Cleaned.txt"
        await update.message.reply_document(bio)
        return

    # URL CLEANER
    if tool == "url":
        import re
        cleaned = re.sub(r"http\S+", "", content)
        bio = io.BytesIO(cleaned.encode()); bio.name = "URL_Cleaned.txt"
        await update.message.reply_document(bio)
        return

    # FILE processor (generic)
    if tool == "file":
        await update.message.reply_text("📂 File received. (No extra processing implemented yet).")
        return

    await update.message.reply_text("❗ Please choose a tool first (use /start -> Tools Hub).")

# ---------------- NUMBER HANDLER (for divider) ----------------
async def number_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("await_lines"):
        text = update.message.text.strip()
        try:
            num = int(text)
            if num <= 0:
                return await update.message.reply_text("⚠️ Number must be greater than 0.")
        except:
            return await update.message.reply_text("❌ Please enter a valid number.")
        context.user_data["lines_per_file"] = num
        context.user_data["await_lines"] = False
        return await update.message.reply_text(f"✅ Divider set to *{num} lines per file*.\nNow send your TXT file.", parse_mode="Markdown")
    # if not awaiting, ignore or provide help
    # (optional) respond to normal text:
    # await update.message.reply_text("Command not recognized. Use /start to open menu.")

# ---------------- RUN ----------------
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

    # Menus & callbacks
    app.add_handler(CallbackQueryHandler(menu_callback, pattern="^(menu_|back_|tool_)"))
    # generator buttons (file keys)
    app.add_handler(CallbackQueryHandler(menu_callback, pattern="^(" + "|".join(FILE_MAP.keys()) + ")$"))

    # File uploads and number input
    app.add_handler(MessageHandler(filters.Document.ALL, file_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, number_handler))

    print("BOT RUNNING...")
    app.run_polling()

if __name__ == "__main__":
    keep_alive()
    asyncio.run(main())
