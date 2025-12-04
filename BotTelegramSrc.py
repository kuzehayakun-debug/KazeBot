# BotTelegramSrc.py
# Fixed + safe for PyDroid usage.
# IMPORTANT: replace BOT_TOKEN and OWNER_ID below before running.

import sys, types, os, asyncio, json, time, secrets
from pathlib import Path
from datetime import datetime, timedelta
import typing
import time

# --- Cooldown storage ---
user_cooldown = {}  # dictionary para sa user cooldown timestamps
COOLDOWN_SECONDS = 30  # ilang seconds ang cooldown per generate

# ---------------- Safe patches for PyDroid (imghdr, urllib3, six, pytz) ----------------
if "imghdr" not in sys.modules:
    imghdr = types.ModuleType("imghdr")
    def what(file, h=None):
        header = b""
        try:
            if isinstance(file, str):
                with open(file, "rb") as f:
                    header = f.read(32)
            else:
                header = (file or b"")[:32]
        except Exception:
            return None
        if header.startswith(b"\xff\xd8"): return "jpeg"
        if header.startswith(b"\x89PNG\r\n\x1a\n"): return "png"
        if header[:6] in (b"GIF87a", b"GIF89a"): return "gif"
        if header.startswith(b"BM"): return "bmp"
        return None
    imghdr.what = what
    sys.modules["imghdr"] = imghdr

if "urllib3.contrib.appengine" not in sys.modules:
    appengine_mod = types.ModuleType("urllib3.contrib.appengine")
    def monkeypatch(type_): return None
    appengine_mod.monkeypatch = monkeypatch
    sys.modules["urllib3.contrib.appengine"] = appengine_mod

if "six" not in sys.modules:
    six_mod = types.ModuleType("six")
    def iteritems(d, **kw):
        return iter(d.items())
    def with_metaclass(meta, *bases):
        class TempMeta(meta): pass
        return TempMeta("TemporaryClass", bases, {})
    class _Moves(types.SimpleNamespace):
        def __getattr__(self, name):
            try:
                return __import__(name)
            except Exception:
                m = types.ModuleType(name)
                sys.modules[name] = m
                return m
    six_mod.PY2 = False
    six_mod.PY3 = True
    six_mod.moves = _Moves()
    six_mod.with_metaclass = with_metaclass
    six_mod.iteritems = iteritems
    six_mod.string_types = (str,)
    sys.modules["six"] = six_mod

if "pytz" not in sys.modules:
    import datetime as _dt
    pytz = types.ModuleType("pytz")
    class _FakeTimezone(_dt.tzinfo):
        def utcoffset(self, dt): return _dt.timedelta(hours=8)
        def dst(self, dt): return _dt.timedelta(0)
        def tzname(self, dt): return "Asia/Manila"
    def timezone(name): return _FakeTimezone()
    pytz.timezone = timezone
    pytz.UTC = _FakeTimezone()
    pytz.utc = pytz.UTC  # sometimes libs expect 'utc' attribute
    sys.modules["pytz"] = pytz

# -----------------------------------------------------------------------------------

# Telegram imports (should be installed)
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# ---------------- CONFIG - REPLACE YOUR TOKEN & OWNER ID BELOW ----------------
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))

# file locations (as you said)
BASE_FOLDER = Path("/storage/emulated/0/Test python-telegram-bot")
FILE_MAP = {
    "valorant": BASE_FOLDER / "Valorant.txt",
    "roblox": BASE_FOLDER / "Roblox.txt",
    "random": BASE_FOLDER / "Random.txt",
    "mtacc": BASE_FOLDER / "Mtacc.txt",
    "gmail": BASE_FOLDER / "Gmail.txt",
    "gaslite": BASE_FOLDER / "gaslite.txt",
    "facebook": BASE_FOLDER / "Facebook.txt",
    "crossfire": BASE_FOLDER / "Crossfire.txt",
    "codm": BASE_FOLDER / "CODM.txt",
    "bloodstrike": BASE_FOLDER / "Bloodstrike.txt",
    "100082": BASE_FOLDER / "100082.txt"
}
# keys json file
KEYS_FILE = Path("/storage/emulated/0/TelegramBot/keys.json")
PH_TZ = __import__("pytz").timezone("Asia/Manila")

# ensure base paths exist
BASE_FOLDER.mkdir(parents=True, exist_ok=True)
if not KEYS_FILE.parent.exists():
    KEYS_FILE.parent.mkdir(parents=True, exist_ok=True)

# init keys file
if not KEYS_FILE.exists():
    KEYS_FILE.write_text(json.dumps({"keys": {}, "users": {}}, indent=2))

# ---------- Helper functions for keys ----------
def load_keys() -> dict:
    try:
        data = json.loads(KEYS_FILE.read_text())
        # Ensure structure
        if "keys" not in data: data["keys"] = {}
        if "users" not in data: data["users"] = {}
        # Normalize each key record to contain fields
        for k, info in list(data["keys"].items()):
            if not isinstance(info, dict):
                data["keys"][k] = {"used": False, "owner": None, "created_by": None, "created_at": None, "expires_at": None}
            else:
                # ensure keys exist
                info.setdefault("used", False)
                info.setdefault("owner", None)
                info.setdefault("created_by", None)
                info.setdefault("created_at", None)
                info.setdefault("expires_at", None)
        return data
    except Exception:
        # if corrupted, reset
        KEYS_FILE.write_text(json.dumps({"keys": {}, "users": {}}, indent=2))
        return {"keys": {}, "users": {}}

def save_keys(data: dict):
    KEYS_FILE.write_text(json.dumps(data, indent=2))

def make_key(length: int = 8) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))

def parse_duration(text: str):
    text = (text or "").lower().strip()
    if text in ("life", "lifetime", "permanent"):
        return None
    if text.endswith("d"):
        try:
            return int(text[:-1]) * 86400
        except:
            return 86400
    if text.endswith("h"):
        try:
            return int(text[:-1]) * 3600
        except:
            return 3600
    # default 1 day
    return 86400

# ---------- Authorization helpers ----------
def is_key_valid(info: dict) -> bool:
    # info is normalized with expires_at present
    exp = info.get("expires_at")
    if exp is None:
        return True
    try:
        return time.time() <= float(exp)
    except:
        return False

async def is_user_authorized(user_id: int) -> bool:
    data = load_keys()
    key = data["users"].get(str(user_id))
    if not key: return False
    info = data["keys"].get(key)
    if not info: return False
    return is_key_valid(info)

# ----------- Commands -------------
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    fullname = user.full_name

    # Check kung authorized ba
    if not await is_user_authorized(user_id):
        await update.message.reply_text(
            f"👋 WELCOME {fullname}!\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🔐 ʙᴇғᴏʀᴇ ʏᴏᴜ ᴄᴀɴ ᴜsᴇ ᴛʜᴇ ɢᴇɴᴇʀᴀᴛᴏʀ, ʏᴏᴜ ɴᴇᴇᴅ ᴀ ᴠᴀʟɪᴅ ᴋᴇʏ.\n"
            "ᴜsᴇ ᴛʜᴇ ᴋᴇʏ ғᴏʀ ᴏɴᴇ-ᴛɪᴍᴇ ᴀᴄᴛɪᴠᴀᴛɪᴏɴ.\n\n"
            "💎 ᴇɴᴊᴏʏ ᴘʀɪᴠᴀᴛᴇ ʟɪɴᴇ ɢᴇɴᴇʀᴀᴛᴏʀ ɪɴ ᴋᴀᴢᴇʜᴀʏᴀ ᴠɪᴘ ʙᴏᴛ!\n"

            "ʙᴜʏ ᴋᴇʏ: @KAZEHAYAMODZ"
        )
        return

    # -------- AUTHORIZED USER MENU ------------
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

    [InlineKeyboardButton("⚡ 100082", callback_data="100082")]
]
    await update.message.reply_video(
    video="Telegram.mp4",
    caption="\n\n✨ Select an account type to generate:",
    reply_markup=InlineKeyboardMarkup(keyboard)
)

# Owner only: generate key
async def genkey_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != 7201369115:
        await update.message.reply_text("🚫 You are not allowed to generate keys.")
        return
    duration = "1d"
    if context.args:
        duration = context.args[0]
    expires_in = parse_duration(duration)
    data = load_keys()
    new_key = make_key(8)
    exp_time = None
    if expires_in is not None:
        exp_time = time.time() + expires_in
    data["keys"][new_key] = {"used": False, "owner": None, "created_by": user.id, "created_at": time.time(), "expires_at": exp_time}
    save_keys(data)
    exp_display = "Lifetime" if exp_time is None else datetime.fromtimestamp(exp_time, PH_TZ).strftime("%Y-%m-%d %I:%M %p")
    await update.message.reply_text(f"✨ 𝑺𝒖𝒄𝒄𝒆𝒔𝒔𝒇𝒖ℓ 𝒈𝒆𝒏𝒆𝒓𝒂𝒕𝒆𝒅 𝒌𝒆𝒚 ✨\n\n🔑𝙔𝙤𝙪𝙧 𝙠𝙚𝙮: `{new_key}`\n🕒 𝙑𝙖𝙡𝙞𝙙 𝙪𝙣𝙩𝙞𝙡: {exp_display}", parse_mode="Markdown")

# use a key
async def key_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not context.args:
        await update.message.reply_text("Usage: /key <KEY>")
        return
    key = context.args[0].strip()
    data = load_keys()
    info = data["keys"].get(key)
    if not info:
        await update.message.reply_text("❌ Invalid key.")
        return
    if info.get("used") and info.get("owner") != user.id:
        await update.message.reply_text("❌ That key is already used by someone else.")
        return
    if info.get("expires_at") and time.time() > info.get("expires_at"):
        await update.message.reply_text("⏰ This key has expired.")
        return
    info["used"] = True
    info["owner"] = user.id
    data["users"][str(user.id)] = key
    save_keys(data)
    exp_display = "Lifetime" if info.get("expires_at") is None else datetime.fromtimestamp(info.get("expires_at"), PH_TZ).strftime("%Y-%m-%d %I:%M %p")
    await update.message.reply_text(f"✅🏆 PREMIUM ACCESS GRANTED! 🏆\n▶️ Click /start to begin generating private accounts.")

async def mykey_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    data = load_keys()
    kid = data["users"].get(str(user.id))
    if not kid:
        await update.message.reply_text("❌ You don't have a key yet.")
        return
    info = data["keys"].get(kid)
    if not info:
        await update.message.reply_text("⚠️ Your key is invalid or revoked.")
        return
    exp_display = "Lifetime" if info.get("expires_at") is None else datetime.fromtimestamp(info.get("expires_at"), PH_TZ).strftime("%Y-%m-%d %I:%M %p")
    await update.message.reply_text(f"🔑 Key: `{kid}`\n🕒 Valid until: {exp_display}", parse_mode="Markdown")

async def mytime_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    data = load_keys()
    kid = data["users"].get(str(user.id))

    if not kid:
        await update.message.reply_text("❌ You don't have a key yet.")
        return

    info = data["keys"].get(kid)
    if not info:
        await update.message.reply_text("⚠️ Your key is invalid or revoked.")
        return

    # Lifetime key?
    if info.get("expires_at") is None:
        await update.message.reply_text("♾️ Your key is **Lifetime**. No expiration.")
        return

    # Compute remaining time
    now = int(time.time())
    expires = info.get("expires_at")
    remaining = expires - now

    if remaining <= 0:
        await update.message.reply_text("⛔ Your key has **expired**.")
        return

    # Convert seconds → days/hours/minutes
    days = remaining // 86400
    hours = (remaining % 86400) // 3600
    minutes = (remaining % 3600) // 60

    exp_display = datetime.fromtimestamp(expires, PH_TZ).strftime("%Y-%m-%d %I:%M %p")

    msg = (
        f"⏳ **KEY VALIDITY**\n"
        f"🔑 Key: `{kid}`\n"
        f"📅 Expires on: {exp_display}\n\n"
        f"⏱️ **Time remaining:**\n"
        f"➡️ {days} days, {hours} hours, {minutes} minutes"
    )

    await update.message.reply_text(msg, parse_mode="Markdown")

async def revoke_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != 7201369115:
        await update.message.reply_text("🚫 Not allowed.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /revoke <KEY>")
        return
    key = context.args[0].strip()
    data = load_keys()
    if key in data["keys"]:
        info = data["keys"].pop(key)
        if info.get("owner"):
            uid = str(info["owner"])
            if uid in data["users"]:
                data["users"].pop(uid)
        save_keys(data)
        await update.message.reply_text(f"✅ Revoked key {key}")
    else:
        await update.message.reply_text("❌ Key not found.")

# Load all authorized users (based sa data file)
def get_all_authorized_users():
    data = load_keys()
    return list(data["users"].keys())

# 🔥 ADD BROADCAST FUNCTION HERE (AFTER revoke_cmd)
async def broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Only owner can broadcast
    if update.effective_user.id != 7201369115:
        await update.message.reply_text("🚫 This command is for the owner only.")
        return

    # No message provided
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /broadcast <message>")
        return

    announcement = " ".join(context.args)

    # Send announcement to all active users
    sent = 0
    for user_id in get_all_authorized_users():
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"📢 *Announcement from Owner*\n{announcement}",
                parse_mode="Markdown"
            )
            sent += 1
        except:
            pass

    await update.message.reply_text(f"📨 Broadcast sent to {sent} users.")

# ---------- file extraction & send (take first N lines and remove them) ----------
def extract_lines_from_file(path: Path, n: int = 100) -> typing.Tuple[str, int]:
    """
    Read the first n lines from path and remove them from the source file.
    Returns (content_string, count_lines_sent).
    """
    if not path.exists():
        return ("", 0)
    # Read all lines
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        # fallback binary read
        text = path.read_text(errors="ignore")
    lines = text.splitlines()
    if not lines:
        return ("", 0)
    to_take = min(len(lines), n)
    taken = lines[:to_take]
    remaining = lines[to_take:]
    # Write remaining back
    try:
        path.write_text("\n".join(remaining), encoding="utf-8", errors="ignore")
    except Exception:
        try:
            path.write_text("\n".join(remaining))
        except Exception:
            pass
    return ("\n".join(taken) + ("\n" if taken and not taken[-1].endswith("\n") else ""), to_take)

# Notify owner privately when someone generates
async def notify_owner(bot, user, choice_key, count):
    owner_id = 7201369115
    try:
        msg = (
            f"📢 *New Generation Alert!*\n"
            f"👤 User: `{user.id}` ({user.first_name})\n"
            f"🔥 Type: {choice_key.capitalize()}\n"
            f"📦 Lines: {count}\n"
            f"⏰ Time: {datetime.now(PH_TZ).strftime('%Y-%m-%d %I:%M %p')}"
        )
        await bot.send_message(chat_id=owner_id, text=msg, parse_mode="Markdown")
    except Exception as e:
        print("Failed to notify owner:", e)

async def secure_send_file(query, choice_key: str):
    user_id = query.from_user.id

    # --- Cooldown check ---
    now = time.time()
    last = user_cooldown.get(user_id, 0)

    if now - last < COOLDOWN_SECONDS:
        remaining = int(COOLDOWN_SECONDS - (now - last))
        await query.message.reply_text(f"⏳ Please wait {remaining}s before generating again.")
        return False

    # Update cooldown timestamp
    user_cooldown[user_id] = now

    # check access
    if not await is_user_authorized(user_id):
        await query.message.reply_text("🚫 Access denied. Please use /key <KEY> to activate access.")
        return False

    file_path = FILE_MAP.get(choice_key)
    if not file_path or not file_path.exists():
        await query.message.reply_text("❌ File not found on server.")
        return False

    # extract 100 lines
    content, count = extract_lines_from_file(file_path, n=100)
    if count == 0:
        await query.message.reply_text("⚠️ The file is empty or has no more lines to send.")
        return False

    # prepare document
    import io
    bio = io.BytesIO(content.encode("utf-8", errors="ignore"))
    bio.name = f"{choice_key.capitalize()}_results.txt"
    bio.seek(0)

    # typing animation
    await query.message.chat.send_action("typing")
    await asyncio.sleep(1.2)

    # SUCCESS MESSAGE FIRST
    await query.message.reply_text(
            "✨ 𝙂𝙚𝙣𝙚𝙧𝙖𝙩𝙞𝙤𝙣 𝘾𝙤𝙢𝙥𝙡𝙚𝙩𝙚! ✨\n"
        "╔══════════════════════╗\n"
        f"🗂️ 𝙇𝙞𝙣𝙚𝙨: {count}\n"
        f"🔍 𝙏𝙮𝙥𝙚: {choice_key.capitalize()} Private\n"
        "👨‍💻 𝙂𝙚𝙣𝙚𝙧𝙖𝙩𝙚𝙙 𝙗𝙮: @KAZEHAYAMODZ\n"
        "╚══════════════════════╝\n\n"
                   "📄 𝙁𝙞𝙡𝙚 𝙂𝙚𝙣𝙚𝙧𝙖𝙩𝙚𝙙 ",
        parse_mode="Markdown"
    )

    # SEND FILE SECOND (immediately)
    try:
        await query.message.reply_document(document=bio)
    except:
        await query.message.reply_text("⚠️ Error sending file.")

    # notify owner
    await notify_owner(query._bot, query.from_user, choice_key, count)

    return True

# Callback button handler
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    choice = (query.data or "").lower()

    # Validate kung nasa FILE_MAP
    if choice not in FILE_MAP:
        await query.message.reply_text("⚠️ Invalid option.")
        return

    # Searching message (store so we can delete later)
    search_msg = await query.message.reply_text(
        f"🔥 Searching in database for {choice.capitalize()}..."
    )

    await asyncio.sleep(8)

    # DELETE the loading message BEFORE sending results
    await search_msg.delete()

    # NOW send file + the "Generation Complete" message
    await secure_send_file(query, choice)

# ---------- run ----------
def main():
    # Try to apply nest_asyncio to avoid "event loop already running" in PyDroid
    try:
        import nest_asyncio
        nest_asyncio.apply()
    except Exception:
        pass

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("genkey", genkey_cmd))
    app.add_handler(CommandHandler("key", key_cmd))
    app.add_handler(CommandHandler("mykey", mykey_cmd))
    app.add_handler(CommandHandler("revoke", revoke_cmd))
    app.add_handler(CommandHandler("broadcast", broadcast_cmd))
    app.add_handler(CommandHandler("mytime", mytime_cmd))

    # Callback buttons
    app.add_handler(CallbackQueryHandler(button_callback))

    print("🤖 Bot started... Press Ctrl+C to stop.")
    print(f"👑 Owner ID: {OWNER_ID}")
    # Run (this will block)
    try:
        app.run_polling()
    except RuntimeError as e:
        print("RuntimeError when starting the bot:", e)
        print("If you're on PyDroid and see 'event loop already running', try to install 'nest_asyncio' or run in a clean python process.")
    except Exception as e:
        print("Exception:", e)

if __name__ == "__main__":
    main()

import traceback

async def send_crash_report(bot):
    try:
        error_text = traceback.format_exc()
        msg = f"⚠️ *Bot Crash Detected!*\n```\n{error_text}\n```"

        await bot.send_message(
            chat_id=7201369115,
            text=msg,
            parse_mode="Markdown"
        )
    except:
        pass  # avoid recursive crash


async def main_loop():
    while True:
        try:
            print("🚀 Bot running...")
            await application.initialize()
            await application.start()
            await application.updater.start_polling()
            await application.updater.idle()

        except Exception:
            print("❌ Bot crashed! Restarting...")
            await send_crash_report(application.bot)
            await asyncio.sleep(3)  # short delay before restart
            continue  # restart loop

        except KeyboardInterrupt:
            print("🛑 Bot stopped manually.")
            break
