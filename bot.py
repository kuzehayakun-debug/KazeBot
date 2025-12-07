# bot.py
import os
import time
import json
import secrets
import base64
import asyncio
from pathlib import Path
from typing import Tuple, Dict, Any, Optional

import requests
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    FSInputFile,
)

load_dotenv()

# ---------------- Config from environment ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")  # format owner/repo
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID")) if os.getenv("ADMIN_CHAT_ID") else None

if not BOT_TOKEN:
    raise SystemExit("BOT_TOKEN not set in environment")
if not GITHUB_REPO:
    raise SystemExit("GITHUB_REPO not set in environment")
# GITHUB_TOKEN optional (but required for auto-updating GitHub files)
# ADMIN_CHAT_ID optional (admin features won't work without it)

# ---------------- Constants & paths ----------------
FILES_DIR = Path("files")
ASSETS_DIR = Path("assets")
KEYS_FILE = Path("keys.json")
USERS_FILE = Path("users.json")
COOLDOWN_SECONDS = 15
LINES_PER_GENERATE = 100
INTRO_MP4 = ASSETS_DIR / "intro.mp4"

FILES_DIR.mkdir(parents=True, exist_ok=True)
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

# ---------------- In-memory state ----------------
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

cooldowns: Dict[int, float] = {}  # user_id -> timestamp when allowed next

def load_json(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default
    return default

keys_store = load_json(KEYS_FILE, {"keys": {}, "revoked": []})
users_store = load_json(USERS_FILE, {"users": [], "user_keys": {}})

# ---------------- GitHub helpers (blocking -> run_in_executor) ----------------
GITHUB_API_BASE = "https://api.github.com"
GITHUB_HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}

def _gh_get_file(path_in_repo: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Return (content_str, sha) or (None, None) if not found
    """
    url = f"{GITHUB_API_BASE}/repos/{GITHUB_REPO}/contents/{path_in_repo}"
    r = requests.get(url, headers={**GITHUB_HEADERS, "Accept": "application/vnd.github.v3+json"}, timeout=30)
    if r.status_code == 200:
        j = r.json()
        content_b64 = j.get("content", "")
        sha = j.get("sha")
        try:
            raw = base64.b64decode(content_b64).decode("utf-8", errors="ignore")
        except Exception:
            raw = ""
        return raw, sha
    return None, None

def _gh_put_file(path_in_repo: str, new_text: str, sha: Optional[str], commit_msg: str) -> Tuple[int, dict]:
    url = f"{GITHUB_API_BASE}/repos/{GITHUB_REPO}/contents/{path_in_repo}"
    payload = {
        "message": commit_msg,
        "content": base64.b64encode(new_text.encode("utf-8")).decode("utf-8"),
        "branch": "main",
    }
    if sha:
        payload["sha"] = sha
    r = requests.put(url, json=payload, headers={**GITHUB_HEADERS, "Accept": "application/vnd.github.v3+json"}, timeout=30)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, {"text": r.text}

async def gh_get_file(path_in_repo: str) -> Tuple[Optional[str], Optional[str]]:
    return await asyncio.get_event_loop().run_in_executor(None, _gh_get_file, path_in_repo)

async def gh_put_file(path_in_repo: str, new_text: str, sha: Optional[str], commit_msg: str) -> Tuple[int, dict]:
    return await asyncio.get_event_loop().run_in_executor(None, _gh_put_file, path_in_repo, new_text, sha, commit_msg)

# ---------------- Local store helpers ----------------
def save_keys_local():
    KEYS_FILE.write_text(json.dumps(keys_store, indent=2), encoding="utf-8")

def save_users_local():
    USERS_FILE.write_text(json.dumps(users_store, indent=2), encoding="utf-8")

def push_local_file_to_github(local_path: Path, repo_path: str, commit_msg: str):
    """
    Best-effort push of local file to GitHub (blocking). Use only in background tasks.
    """
    try:
        content = local_path.read_text(encoding="utf-8")
        sha = None
        # try get sha
        _, sha = _gh_get_file(repo_path)
        code, resp = _gh_put_file(repo_path, content, sha, commit_msg)
        return code, resp
    except Exception as e:
        return None, {"error": str(e)}

# ---------------- Key & user management ----------------
def generate_key() -> str:
    return "K-" + secrets.token_hex(8).upper()

def is_key_valid(key: str) -> bool:
    if not key:
        return False
    if key in keys_store.get("revoked", []):
        return False
    return key in keys_store.get("keys", {})

def store_key(key: str, meta: dict):
    keys_store.setdefault("keys", {})[key] = meta
    save_keys_local()
    # best-effort push
    if GITHUB_TOKEN and GITHUB_REPO:
        asyncio.create_task(asyncio.get_event_loop().run_in_executor(None, push_local_file_to_github, KEYS_FILE, "keys.json", f"Add key {key}"))

def revoke_key(key: str):
    if key in keys_store.get("keys", {}):
        keys_store["keys"].pop(key, None)
    keys_store.setdefault("revoked", []).append(key)
    save_keys_local()
    if GITHUB_TOKEN and GITHUB_REPO:
        asyncio.create_task(asyncio.get_event_loop().run_in_executor(None, push_local_file_to_github, KEYS_FILE, "keys.json", f"Revoke key {key}"))

def record_user(user_id: int):
    if user_id not in users_store.get("users", []):
        users_store.setdefault("users", []).append(user_id)
        save_users_local()
        if GITHUB_TOKEN and GITHUB_REPO:
            asyncio.create_task(asyncio.get_event_loop().run_in_executor(None, push_local_file_to_github, USERS_FILE, "users.json", f"Add user {user_id}"))

def set_user_key(user_id: int, key: str):
    users_store.setdefault("user_keys", {})[str(user_id)] = key
    save_users_local()
    if GITHUB_TOKEN and GITHUB_REPO:
        asyncio.create_task(asyncio.get_event_loop().run_in_executor(None, push_local_file_to_github, USERS_FILE, "users.json", f"User {user_id} set key"))

def get_user_key(user_id: int) -> Optional[str]:
    return users_store.get("user_keys", {}).get(str(user_id))

# ---------------- Cooldown ----------------
def check_cooldown(user_id: int) -> int:
    until = cooldowns.get(user_id, 0)
    left = int(until - time.time())
    return left if left > 0 else 0

def set_cooldown(user_id: int):
    cooldowns[user_id] = time.time() + COOLDOWN_SECONDS

# ---------------- UI helpers ----------------
def build_files_keyboard() -> InlineKeyboardMarkup:
    kb = []
    for fn in sorted(FILES_DIR.iterdir()):
        if fn.is_file() and fn.name.lower().endswith(".txt"):
            name = fn.stem
            kb.append([InlineKeyboardButton(text=f"📄 {name}", callback_data=f"file:{fn.name}")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def pretty(s: str) -> str:
    # small "upgraded font" mapping (simple)
    return f"✨ {s} ✨"

# ---------------- File read/update logic ----------------
def get_first_n_and_remainder_local(path: Path, n: int) -> Tuple[str, str]:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    lines = text.splitlines(keepends=True)
    first = lines[:n]
    rest = lines[n:]
    return "".join(first), "".join(rest)

# ---------------- Admin check ----------------
def is_admin(user_id: int) -> bool:
    return ADMIN_CHAT_ID is not None and user_id == ADMIN_CHAT_ID

# ---------------- Alerts ----------------
async def send_admin_alert(text: str):
    if ADMIN_CHAT_ID:
        try:
            await bot.send_message(chat_id=ADMIN_CHAT_ID, text=text)
        except Exception:
            pass

# ---------------- Handlers ----------------
@dp.message(Command("start"))
async def cmd_start(message: Message):
    record_user(message.from_user.id)
    # send mp4 if exists
    if INTRO_MP4.exists():
        try:
            await message.answer_video(video=FSInputFile(str(INTRO_MP4)), caption=pretty("Welcome! Select a file below:"))
        except Exception:
            await message.answer(pretty("Welcome! Select a file below:"))
    else:
        await message.answer(pretty("Welcome! Select a file below:"))
    kb = build_files_keyboard()
    if kb.inline_keyboard:
        await message.answer("Choose file to generate (100 lines) — you MUST use a valid key first using /usekey <KEY>", reply_markup=kb)
    else:
        await message.answer("No files found in /files. Upload .txt files to your repo.")

@dp.message(Command("usekey"))
async def cmd_usekey(message: Message):
    # user registers a key: /usekey K-....
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("Usage: /usekey <KEY>")
        return
    key = parts[1].strip()
    if not is_key_valid(key):
        await message.reply("❌ Key invalid or revoked.")
        return
    set_user_key(message.from_user.id, key)
    await message.reply("✅ Key registered. You may now generate files (observe cooldown).")

@dp.callback_query()
async def callback_router(query: CallbackQuery):
    if not query.data:
        await query.answer()
        return
    if query.data.startswith("file:"):
        filename = query.data.split("file:", 1)[1]
        await handle_file_select(query, filename)
    else:
        await query.answer()

async def handle_file_select(query: CallbackQuery, filename: str):
    user_id = query.from_user.id

    # check cooldown
    left = check_cooldown(user_id)
    if left > 0:
        await query.message.answer(f"⏳ You must wait {left}s before generating again.")
        await query.answer()
        return

    # enforce key for EVERYONE (including admin)
    user_key = get_user_key(user_id)
    if not user_key:
        await query.message.answer("🔐 You must register a valid key first. Use /usekey <KEY>")
        await query.answer()
        return
    if not is_key_valid(user_key):
        await query.message.answer("❌ Your registered key is invalid or revoked. Request a new key from admin.")
        await query.answer()
        return

    # find local file
    path = FILES_DIR / filename
    if not path.exists():
        await query.message.answer("File not found.")
        await query.answer()
        return

    # read first 100 lines and remainder
    first100, remainder = await asyncio.get_event_loop().run_in_executor(None, get_first_n_and_remainder_local, path, LINES_PER_GENERATE)

    if not first100:
        await query.message.answer("File is empty.")
        await query.answer()
        return

    # write temp file
    tmp = Path(f"tmp_{int(time.time())}_{filename}")
    tmp.write_text(first100, encoding="utf-8")

    # send as real file
    try:
        await bot.send_document(chat_id=user_id, document=FSInputFile(str(tmp)), caption=f"{filename} — {LINES_PER_GENERATE} lines")
    except Exception:
        # fallback: send truncated text
        await bot.send_message(chat_id=user_id, text=first100[:3500])

    # update local file (overwrite with remainder)
    path.write_text(remainder, encoding="utf-8")

    # attempt push to GitHub (contents API)
    if GITHUB_TOKEN:
        repo_path = f"files/{filename}"
        # get current sha and push
        sha_content = await gh_get_file(repo_path)
        sha = sha_content[1] if sha_content else None
        code, resp = await gh_put_file(repo_path, remainder, sha, f"Auto-deduct {LINES_PER_GENERATE} lines from {filename} by user {user_id}")
        if code is None or (isinstance(code, int) and code >= 400):
            await send_admin_alert(f"⚠️ Failed to push updated {filename}. Resp: {resp}")

    # cleanup tmp file
    try:
        tmp.unlink(missing_ok=True)
    except Exception:
        pass

    # set cooldown and remove inline keyboard (clean UI)
    set_cooldown(user_id)
    try:
        await query.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    # notify admin
    await send_admin_alert(f"🔥 NEW GENERATION\nUser: {query.from_user.id}\nFile: {filename}\nKey: {user_key}\nTime: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    await query.answer("Generated ✅", show_alert=False)

# ---------------- Admin Commands (still admin-only) ----------------
@dp.message(Command("genkey"))
async def cmd_genkey(message: Message):
    if not is_admin(message.from_user.id):
        await message.reply("❌ Not authorized.")
        return
    k = generate_key()
    meta = {"created_by": message.from_user.id, "time": int(time.time())}
    store_key(k, meta)
    await message.reply(f"✅ New key created:\n`{k}`", parse_mode="Markdown")
    await send_admin_alert(f"🆕 Key generated: {k} by {message.from_user.id}")

@dp.message(Command("revokekey"))
async def cmd_revokey(message: Message):
    if not is_admin(message.from_user.id):
        await message.reply("❌ Not authorized.")
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("Usage: /revokekey <KEY>")
        return
    k = parts[1].strip()
    revoke_key(k)
    await message.reply(f"✅ Key revoked: `{k}`", parse_mode="Markdown")
    await send_admin_alert(f"🛑 Key revoked: {k} by {message.from_user.id}")

@dp.message(Command("broadcast"))
async def cmd_broadcast(message: Message):
    if not is_admin(message.from_user.id):
        await message.reply("❌ Not authorized.")
        return
    payload = message.text.partition(" ")[2].strip()
    if not payload:
        await message.reply("Usage: /broadcast your message")
        return
    sent = 0
    for uid in list(users_store.get("users", [])):
        try:
            await bot.send_message(chat_id=uid, text=f"📢 Broadcast:\n\n{payload}")
            sent += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass
    await message.reply(f"Broadcast sent to {sent} users.")

# ---------------- Utility commands ----------------
@dp.message(Command("mytime"))
async def cmd_mytime(message: Message):
    left = check_cooldown(message.from_user.id)
    if left == 0:
        await message.reply("✅ You can generate now.")
    else:
        await message.reply(f"⏳ Cooldown: {left} seconds left.")

@dp.message(Command("help"))
async def cmd_help(message: Message):
    txt = (
        "✨ KazeBot Help\n\n"
        "• /start - show menu\n"
        "• /usekey <KEY> - register your key (required to generate)\n"
        "• /mytime - check cooldown\n\n"
        "Admin only:\n"
        "• /genkey\n"
        "• /revokekey <KEY>\n"
        "• /broadcast <msg>\n"
    )
    await message.reply(txt)

# ---------------- Startup sync ----------------
async def on_startup():
    # try push local stores to GitHub at start (best-effort)
    if GITHUB_TOKEN:
        if KEYS_FILE.exists():
            asyncio.create_task(asyncio.get_event_loop().run_in_executor(None, push_local_file_to_github, KEYS_FILE, "keys.json", "Sync keys on startup"))
        if USERS_FILE.exists():
            asyncio.create_task(asyncio.get_event_loop().run_in_executor(None, push_local_file_to_github, USERS_FILE, "users.json", "Sync users on startup"))

# ---------------- Run ----------------
if __name__ == "__main__":
    print("Starting KazeBot...")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(on_startup())
    try:
        dp.run_polling(bot)
    finally:
        loop.close()