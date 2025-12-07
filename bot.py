import os
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("8539319746:AAHEdZ-d2P6dQFeS4jhwrJglV7Yp3doR1Jw")
GITHUB_TOKEN = os.getenv("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")
GITHUB_REPO = os.getenv("kuzehayakun-debug/KazeBot")  # format: user/repo

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

FILES_DIR = "files"


# 🔘 Create dynamic buttons from files/
def generate_buttons():
    keyboard = []
    for filename in os.listdir(FILES_DIR):
        if filename.endswith(".txt"):
            btn = InlineKeyboardButton(
                text=filename.replace(".txt", ""),
                callback_data=filename
            )
            keyboard.append([btn])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# 📤 Send 100 lines
def get_first_100_lines(path):
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    return lines[:100], lines[100:]


# 📤 Upload updated file to GitHub
def update_github_file(filename, new_content):
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/files/{filename}"

    # Get SHA of existing file
    get_req = requests.get(url)
    sha = get_req.json()["sha"]

    encoded = new_content.encode("utf-8")

    data = {
        "message": f"Auto update {filename}",
        "content": encoded.decode("latin1").encode("base64"),
        "sha": sha
    }


@dp.message(Command("start"))
async def start_cmd(msg: types.Message):
    await msg.answer(
        "Welcome! Select a file below:",
        reply_markup=generate_buttons()
    )


@dp.callback_query()
async def process_file(callback: types.CallbackQuery):
    file_name = callback.data
    file_path = os.path.join(FILES_DIR, file_name)

    # Read 100 lines
    first100, remaining = get_first_100_lines(file_path)

    if len(first100) == 0:
        await callback.message.answer("❌ File empty!")
        return

    # Send result
    formatted = "".join(first100)
    await callback.message.answer(f"Here are your 100 lines:\n\n{formatted}")

    # Rewrite local file
    with open(file_path, "w", encoding="utf-8") as f:
        f.writelines(remaining)

    await callback.answer("Sent 100 lines + updated file!")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())