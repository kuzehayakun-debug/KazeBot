# bot.py
import os
import asyncio
import base64
import tempfile
from pathlib import Path
from typing import Tuple, List, Optional

import requests
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InputFile
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram import Router

load_dotenv()

# ===== ENV / CONFIG =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")  # example: "username/KazeBot"
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main")

if not BOT_TOKEN:
    raise SystemExit("Set BOT_TOKEN environment variable")
if not GITHUB_TOKEN:
    raise SystemExit("Set GITHUB_TOKEN environment variable")
if not GITHUB_REPO:
    raise SystemExit("Set GITHUB_REPO environment variable (owner/repo)")

# files mapping (display name -> filename inside `files/` folder)
MENU_FILES = {
    "🎮 Valorant": "Valorant.txt",
    "🤖 Roblox": "Roblox.txt",
    "✨ CODM": "CODM.txt",
    "⚔️ Crossfire": "Crossfire.txt",
    "📘 Facebook": "Facebook.txt",
    "📧 Gmail": "Gmail.txt",
    "🙈 Mtacc": "Mtacc.txt",
    "🔥 Gaslite": "gaslite.txt",
    "♨️ Bloodstrike": "Bloodstrike.txt",
    # "🎲 Random": None  # optional
}

# how many lines to extract per request
LINES_PER_GENERATE = 100

# aiogram setup (v3)
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
router = Router()
dp.include_router(router)

# concurrency locks per filename to avoid race-conditions
file_locks = {name: asyncio.Lock() for name in MENU_FILES.values()}

# GitHub API helpers
GITHUB_API_BASE = "https://api.github.com"

def github_get_file(path: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Returns tuple (text_content, sha) or (None, None) if not found.
    Path is relative to repo root, e.g. "files/CODM.txt"
    """
    url = f"{GITHUB_API_BASE}/repos/{GITHUB_REPO}/contents/{path}"
    params = {"ref": GITHUB_BRANCH}
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    r = requests.get(url, params=params, headers=headers, timeout=30)
    if r.status_code == 200:
        j = r.json()
        content_b64 = j.get("content", "")
        sha = j.get("sha")
        # content may contain newlines; decode
        try:
            raw = base64.b64decode(content_b64).decode("utf-8", errors="ignore")
        except Exception:
            raw = ""
        return raw, sha
    # file not found or other error
    return None, None

def github_update_file(path: str, new_text: str, sha: str, commit_message: str) -> bool:
    """
    Overwrite file with new_text. Returns True on success.
    """
    url = f"{GITHUB_API_BASE}/repos/{GITHUB_REPO}/contents/{path}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    content_b64 = base64.b64encode(new_text.encode("utf-8")).decode("utf-8")
    payload = {
        "message": commit_message,
        "content": content_b64,
        "sha": sha,
        "branch": GITHUB_BRANCH
    }
    r = requests.put(url, json=payload, headers=headers, timeout=30)
    return r.status_code in (200, 201)

# Utility: build inline keyboard markup
def build_menu_markup():
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    kb = InlineKeyboardMarkup(row_width=2)
    buttons = []
    for label in MENU_FILES.keys():
        buttons.append(InlineKeyboardButton(text=label, callback_data=f"pick|{label}"))
    kb.add(*buttons)
    # add a quick 100-lines button maybe?
    return kb

# Handlers
@router.message(F.text == "/start")
async def cmd_start(message: Message):
    text = "✨ Select an account type to generate (100 lines will be extracted and deducted):"
    await message.answer_photo(
        photo="https://i.imgur.com/3pXo6gM.png",
        caption=text,
        reply_markup=build_menu_markup()
    )

@router.callback_query(F.data.startswith("pick|"))
async def on_pick(cb: CallbackQuery):
    data = cb.data  # e.g. "pick|✨ CODM"
    try:
        _, label = data.split("|", 1)
    except Exception:
        await cb.answer("Invalid selection.", show_alert=True)
        return

    filename = MENU_FILES.get(label)
    if not filename:
        await cb.answer("File mapping not found.", show_alert=True)
        return

    repo_path = f"files/{filename}"

    # Acquire lock per file
    lock = file_locks.get(filename)
    if lock is None:
        # create lock if missing
        lock = asyncio.Lock()
        file_locks[filename] = lock

    await cb.answer("Processing... please wait.", show_alert=False)

    async with lock:
        # fetch file from GitHub
        raw, sha = await asyncio.get_event_loop().run_in_executor(None, github_get_file, repo_path)
        if raw is None:
            await cb.message.answer(f"Error: file `{repo_path}` not found in repo.")
            return

        # split into lines, keep non-empty lines
        lines = [line for line in raw.splitlines() if line.strip()]
        total = len(lines)
        if total < LINES_PER_GENERATE:
            await cb.message.answer(f"Not enough lines in `{filename}` (found {total}, need {LINES_PER_GENERATE}).")
            return

        # take first N lines (FIFO). If you want random sample, replace logic.
        take = lines[:LINES_PER_GENERATE]
        remaining = lines[LINES_PER_GENERATE:]

        # prepare temp file to send
        with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".txt") as tmp:
            tmp_name = tmp.name
            tmp.write("\n".join(take))
            tmp.flush()

        # Send file to user as document
        try:
            await cb.message.answer_document(InputFile(tmp_name), caption=f"{filename} — {LINES_PER_GENERATE} lines")
        except Exception as e:
            await cb.message.answer(f"Failed to send file: {e}")
            # cleanup temp
            try:
                Path(tmp_name).unlink(missing_ok=True)
            except Exception:
                pass
            return

        # Now update file on GitHub (overwrite with remaining)
        new_text = "\n".join(remaining) + ("\n" if remaining else "")
        commit_msg = f"Bot removed {LINES_PER_GENERATE} lines from {filename}"
        success = await asyncio.get_event_loop().run_in_executor(
            None, github_update_file, repo_path, new_text, sha, commit_msg
        )

        # cleanup tmp file after send
        try:
            Path(tmp_name).unlink(missing_ok=True)
        except Exception:
            pass

        if success:
            await cb.message.answer(f"✅ Sent {LINES_PER_GENERATE} lines and updated `{filename}` (remaining: {len(remaining)} lines).")
        else:
            await cb.message.answer("⚠️ Sent file but failed to update GitHub file. You should check repository and restore if needed.")

# fallback message handler
@router.message()
async def fallback(message: Message):
    await message.reply("Use /start to open the menu.")

# Run
async def main():
    print("Bot started")
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Bot stopped")