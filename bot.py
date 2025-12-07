# bot.py
import os
import random
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

load_dotenv()  # optional .env file for local dev
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise SystemExit("Set BOT_TOKEN environment variable")

BASE_DIR = Path(__file__).parent
FILES_DIR = BASE_DIR / "files"

# Mapping button text -> filename
MENU_FILES = {
    "🎮 Valorant": "valorant.txt",
    "🤖 Roblox": "roblox.txt",
    "✨ CODM": "codm.txt",
    "⚔️ Crossfire": "crossfire.txt",
    "📘 Facebook": "facebook.txt",
    "📧 Gmail": "gmail.txt",
    "🙈 Mtacc": "mtacc.txt",
    "🔥 Gaslite": "gaslite.txt",
    "♨️ Bloodstrike": "bloodstrike.txt",
    "🎲 Random": None,  # special: choose random file
}

# Create bot & dispatcher
bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher()

def read_lines_from_file(filename: Path):
    if not filename.exists():
        return []
    with open(filename, "r", encoding="utf-8", errors="ignore") as f:
        lines = [line.strip() for line in f if line.strip()]
    return lines

def get_random_from_file(filename: Path, count: int = 1):
    lines = read_lines_from_file(filename)
    if not lines:
        return []
    if count <= 0:
        count = 1
    if count == 1:
        return [random.choice(lines)]
    # if count > available, sample with replacement
    return random.choices(lines, k=count)

def choose_random_file():
    files = [f for f in FILES_DIR.iterdir() if f.is_file() and f.suffix == ".txt"]
    return random.choice(files) if files else None

def build_menu():
    kb = InlineKeyboardBuilder()
    row = []
    for text in MENU_FILES.keys():
        row.append(InlineKeyboardButton(text=text, callback_data=f"pick|{text}"))
        # put two per row
        if len(row) == 2:
            kb.row(*row)
            row = []
    if row:
        kb.row(*row)
    # bottom: send 5, send 10 quick buttons
    kb.row(
        InlineKeyboardButton(text="📤 Send 1", callback_data="count|1"),
        InlineKeyboardButton(text="📤 Send 5", callback_data="count|5"),
        InlineKeyboardButton(text="📤 Send 10", callback_data="count|10"),
    )
    # status / credit
    kb.row(InlineKeyboardButton(text="⚡ 100082", callback_data="noop|whatever"))
    return kb.as_markup()

@dp.message(commands=["start", "help"])
async def cmd_start(msg: types.Message):
    text = "✨ Select an account type to generate:\n\n(Press a button to get entries from your .txt files)"
    await msg.reply_photo(
        photo="https://i.imgur.com/3pXo6gM.png",  # optional thumbnail url
        caption=text,
        reply_markup=build_menu()
    )

# Hold selected file in chat data? Simpler: callback contains selection logic
@dp.callback_query()
async def handle_cb(cb: types.CallbackQuery):
    data = cb.data or ""
    # two types: pick|<button text>  OR count|<n>  OR noop|...
    if data.startswith("pick|"):
        _, button_text = data.split("|", 1)
        filename = MENU_FILES.get(button_text)
        if filename is None:
            # random file
            file_path = choose_random_file()
            if not file_path:
                await cb.answer("No files available.", show_alert=True)
                return
        else:
            file_path = FILES_DIR / filename
            if not file_path.exists():
                await cb.answer(f"File for {button_text} not found.", show_alert=True)
                return

        # store last selection in message's reply markup? For simplicity, reply with one item
        entry = get_random_from_file(file_path, count=1)
        if not entry:
            await cb.answer("File is empty or missing.", show_alert=True)
            return
        await cb.message.answer(f"<b>{button_text}</b>\n\n<pre>{entry[0]}</pre>")
        await cb.answer()  # remove loading
        return

    if data.startswith("count|"):
        _, n = data.split("|", 1)
        try:
            n = int(n)
        except:
            n = 1
        # We'll try to detect last-pressed file by recent reply? Simpler: pick random file
        file_path = choose_random_file()
        if not file_path:
            await cb.answer("No files available.", show_alert=True)
            return
        entries = get_random_from_file(file_path, count=n)
        if not entries:
            await cb.answer("File is empty.", show_alert=True)
            return
        text = "\n".join(entries)
        # If long, send as a text file instead
        if len(text) > 3500:
            # create temp file and send document
            tmp = BASE_DIR / "tmp_out.txt"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(text)
            await cb.message.answer_document(tmp.open("rb"), caption=f"Random from {file_path.name}")
            tmp.unlink(missing_ok=True)
        else:
            await cb.message.answer(f"<b>Random from {file_path.name}</b>\n\n<pre>{text}</pre>")
        await cb.answer()
        return

    # noop
    await cb.answer()

async def main():
    print("Bot started")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Bot stopped")