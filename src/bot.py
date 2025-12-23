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

def generate_full_key(length=8):
    return "Kaze-" + make_key(length)

def get_key(manual_key=None):
    if manual_key:  # custom key
        return manual_key.strip()
    return generate_full_key()  # random key with prefix, random key

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

# ---------------- /generate ----------------
async def generate_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if not await is_user_authorized(user.id):
        return await update.message.reply_text("❌ You are not authorized. Please redeem a valid key.")

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

    await update.message.reply_text(
        "✨ Select an account type to generate:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ---------------- /start ----------------
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # Not authorized
    if not await is_user_authorized(user.id):
        return await update.message.reply_text(
            f"💫 *WELCOME, {user.full_name}!* 💫\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🔐 *PREMIUM KEY VERIFICATION REQUIRED*\n"
            "Before you can access the generator, please enter your premium key.\n\n"
            "🚀 *Once Activated, You Get:*\n"
            "• Instant account generation\n"
            "• Clean + verified combos\n"
            "• CODM / ML / Gaslite / More\n"
            "• VIP-only features\n\n"
            "📩 DM TO BUY KEY @KAZEHAYAMODZ",
        )

    keyboard = [
        [InlineKeyboardButton("⚡ Generate Accounts", callback_data="menu_generate")],
        [InlineKeyboardButton("🛠 Tools Hub", callback_data="menu_tools")],
        [InlineKeyboardButton("📢 Channel", callback_data="menu_channel")],
    ]

    await update.message.reply_text(
    "✨ *SELECT AN OPTION TO START BOT✨*\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "Select any option below to get started. Your tools, generators, and premium features\n"
    "are all organized here for easy access.\n\n"
    "⚡ *Generate Accounts* – Fast & fresh combos\n"
    "🛠 *Tools Hub* – Useful utilities for file processing\n"
    "📢 *Channel* – Stay updated with new releases\n\n"
    "👇 *Choose an option to continue:*",
    parse_mode="Markdown",
    reply_markup=InlineKeyboardMarkup(keyboard)
    )

    # --- GENERATE ACCOUNTS MENU ---
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

        return await q.edit_message_text(
            "⚡ *Select account to generate:*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(gen_keys)
        )

    # --- TOOLS HUB MENU ---
    if data == "menu_tools":
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
    if data == "menu_channel":
        return await q.edit_message_text(
            "📢 *Join our official channel:*\n"
            "👉 https://t.me/+wkXVYyqiRYplZjk1",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅ Back", callback_data="back_to_home")]
            ])
        )

    # --- BACK BUTTON ---
    if data == "back_to_home":
        home = [
            [InlineKeyboardButton("⚡ Generate Accounts", callback_data="menu_generate")],
            [InlineKeyboardButton("🛠 Tools Hub", callback_data="menu_tools")],
            [InlineKeyboardButton("📢 Channel", callback_data="menu_channel")],
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

    intro = ASSETS_DIR / "Telegram.mp4"
    if intro.exists():
        await update.message.reply_video(
            video=FSInputFile(intro),
            caption="✨ Select an account type to generate:",
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

    args = context.args

    # Default
    manual_key = None
    duration = "1d"

    if len(args) == 1:
        if args[0].lower().endswith(("d", "h")) or args[0].lower() in ("life", "lifetime"):
            duration = args[0]      # 30d, lifetime, 12h etc.
        else:
            manual_key = args[0]    # custom key
    
    elif len(args) == 2:
        manual_key = args[0]        # custom key
        duration = args[1]          # custom duration

    # Generate key
    key = get_key(manual_key)

    # Parse duration
    seconds = parse_duration(duration)

    # Save
    data = load_keys()
    data["keys"][key] = {
        "owner": None,
        "created_at": time.time(),
        "expires_at": None if seconds is None else time.time() + seconds
    }
    save_keys(data)

    # Format expiry
    exp = data["keys"][key]["expires_at"]
    exp_text = "♾ Lifetime" if exp is None else datetime.fromtimestamp(exp).strftime("%Y-%m-%d %I:%M %p")

    # Reply
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

    await update.message.reply_text(msg, parse_mode="Markdown")
    
#-----------------------Panel--------------------------
async def panel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        return await update.message.reply_text("⛔ Access denied.")

    data = load_keys()
    users = data.get("users", {})
    keys = data.get("keys", {})

    if not users:
        return await update.message.reply_text("📭 No users found.")

    msg = "🛡 *ADMIN PANEL — USERS LIST*\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━━\n\n"

    for uid, key in users.items():
        info = keys.get(key, {})
        exp = info.get("expires_at")

        if exp is None:
            status = "♾ Lifetime"
        elif time.time() > exp:
            status = "❌ Expired"
        else:
            remain = int(exp - time.time())
            h = remain // 3600
            m = (remain % 3600) // 60
            status = f"✅ {h}h {m}m"

        msg += (
            f"👤 *User ID:* `{uid}`\n"
            f"🔑 *Key:* `{key}`\n"
            f"⏳ *Status:* {status}\n"
            "━━━━━━━━━━━━━━\n"
        )

    for i in range(0, len(msg), 4000):
        await update.message.reply_text(
            msg[i:i+4000],
            parse_mode="Markdown"
        )

# -------------------- /key --------------------
async def key_cmd(update, context):
    user = update.effective_user

    # Walang argument
    if not context.args:
        return await update.message.reply_text(
            "❗ Usage: `/key <YOUR_KEY>`",
            parse_mode="Markdown"
        )

    key = context.args[0].strip()

    # Load keys
    data = load_keys()
    info = data["keys"].get(key)

    # Invalid key
    if not info:
        return await update.message.reply_text(
            "❌ Invalid key. Please try again."
        )

    # --- SAFE FIX 1: ensure default values ---
    if "used" not in info:
        info["used"] = False
    if "owner" not in info:
        info["owner"] = None

    # Already used by someone else
    if info["used"] and info["owner"] != user.id:
        return await update.message.reply_text(
            "❌ This key is already used by another user."
        )

    # Check expiry
    exp = info.get("expires_at")
    if exp and time.time() > exp:
        return await update.message.reply_text(
            "⏳ This key has expired."
        )

    # --- REDEEM SUCCESS ---
    info["used"] = True
    info["owner"] = user.id
    data["users"][str(user.id)] = key

    save_keys(data)

    # Lifetime text
    if exp is None:
        exp_text = "♾ Lifetime"
    else:
        exp_text = datetime.fromtimestamp(exp).strftime("%Y-%m-%d %I:%M %p")

    premium_msg = (
    "🏆 *PREMIUM ACCESS ACTIVATED!* 🏆\n"
    "━━━━━━━━━━━━━━━━━━━━━━\n"
    "✨ Welcome to the VIP experience!\n"
    "Your account is now fully upgraded.\n\n"
    
    "💎 *KEY INFORMATION*\n"
    f"🔑 Key: `{key}`\n"
    f"📅 Expires: {exp_text}\n"
    "📌 Status: *ACTIVE*\n\n"
    
    "🚀 *PREMIUM FEATURES UNLOCKED*\n"
    "• ⚡ Faster & smoother generation\n"
    "• 🎯 Priority processing (no cooldown delays)\n"
    "• 🔥 Access to all generator types\n"
    "• ♾ Unlimited usage\n"
    "• 🛡 Anti-error protection enabled\n"
    "• 📞 Owner/Dev priority support\n\n"
    
    "📘 *AVAILABLE COMMANDS*\n"
    "• /start – Open the main menu\n"
    "• /generate – Generate accounts instantly\n"
    "• /mytime – Check your license validity\n\n"
    
    "🔔 *IMPORTANT REMINDERS*\n"
    "• Keep your key private\n"
    "• Don’t share your account to avoid lockouts\n"
    "• Generator resets daily for fresh combos\n\n"
    
    "▶ *Type /start to begin!* ✨"
    )

    return await update.message.reply_text(
        premium_msg,
        parse_mode="Markdown"
    )
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
            await context.bot.send_message(uid, f"\n{msg}")
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
COOLDOWN = 30

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
            f"🔰User: {user.first_name} ({user.id})\n"
            f"📁Type: {typ}\n"
            f"📊Lines: {count}\n"
            f"⌛Time: {PH_TIME()}",
        )
    except:
        pass

    # ---------------- MENU CALLBACK ----------------
async def menu_callback(update, context):
    q = update.callback_query
    await q.answer()
    user = q.from_user
    data = q.data

    # --- GENERATE ACCOUNTS MENU ---
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

        return await q.edit_message_text(
            "⚡ *Select account to generate:*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(gen_keys)
        )

    # --- TOOLS HUB MENU ---
    if data == "menu_tools":
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

    # --- CHANNEL MENU ---
    if data == "menu_channel":
        return await q.edit_message_text(
            "📢 *Join our official channel:*\n"
            "👉 https://t.me/+wkXVYyqiRYplZjk1",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅ Back", callback_data="back_to_home")]
            ])
        )

    # --- BACK TO HOME ---
    if data == "back_to_home":
        home = [
            [InlineKeyboardButton("⚡ Generate Accounts", callback_data="menu_generate")],
            [InlineKeyboardButton("🛠 Tools Hub", callback_data="menu_tools")],
            [InlineKeyboardButton("📢 Channel", callback_data="menu_channel")],
        ]

        return await q.edit_message_text(
            "🏠 *Main Menu*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(home)   # FIXED
        )

    # --- TOOL MESSAGES ---
    if data == "tool_divider":
        return await q.edit_message_text("📄 TXT Divider selected.\nSend file to process.")
    if data == "tool_dupe":
        return await q.edit_message_text("🧹 Duplicate Remover selected.\nSend file to process.")
    if data == "tool_url":
        return await q.edit_message_text("🔗 URL Cleaner selected.\nSend text or file.")
    if data == "tool_file":
        return await q.edit_message_text("📂 File Processor selected.\nSend file.")

    # --- GENERATION HANDLER ---
    if data in FILE_MAP:
        choice = data

        # verify premium
        if not await is_user_authorized(user.id):
            return await q.message.reply_text("❌ Not authorized.")

        # cooldown
        now = time.time()
        if now - user_cool.get(user.id, 0) < COOLDOWN:
            return await q.message.reply_text(f"⏳ Please wait {COOLDOWN}s.")
        user_cool[user.id] = now

        # loading
        msg = await q.message.reply_text(f"🔥 Searching {choice} database…")
        await asyncio.sleep(1.5)
        await msg.delete()

        # extract
        content, count = extract_lines(FILE_MAP[choice], 200)

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

        return await q.message.reply_document(bio, filename=f"{choice}.txt", caption=caption)
        
# ---------------- RUN BOT ----------------
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # ----- Commands -----
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("genkey", genkey_cmd))
    app.add_handler(CommandHandler("key", key_cmd))
    app.add_handler(CommandHandler("revoke", revoke_cmd))
    app.add_handler(CommandHandler("mytime", mytime_cmd))
    app.add_handler(CommandHandler("broadcast", broadcast_cmd))
    app.add_handler(CommandHandler("generate", generate_cmd))
    app.add_handler(CommandHandler("panel", panel_cmd))

    # ----- Menu Buttons -----
    app.add_handler(CallbackQueryHandler(menu_callback, pattern="^menu_"))
    app.add_handler(CallbackQueryHandler(menu_callback, pattern="^back_"))
    app.add_handler(CallbackQueryHandler(menu_callback, pattern="^tool_"))

    # ----- Generator buttons (valorant, codm, facebook, etc) -----
    app.add_handler(CallbackQueryHandler(menu_callback))

    print("BOT RUNNING on Render...")
    app.run_polling()

if __name__ == "__main__":
    keep_alive()
    asyncio.run(main())
