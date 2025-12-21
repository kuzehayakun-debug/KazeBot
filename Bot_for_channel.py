import os
import asyncio
from threading import Thread
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

app_web = Flask(__name__)

@app_web.route("/")
def home():
    return "Bot is online!"

def keep_alive():
    port = int(os.environ.get("PORT", 10000))
    Thread(target=lambda: app_web.run(host="0.0.0.0", port=port)).start()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hi! Bot is running.")

async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    for m in update.message.new_chat_members:
        full = (m.full_name or m.first_name).strip()
        name_upper = full.upper()
        msgs = [
            f"HELLO {name_upper}, WELCOME TO PALARO! 🎮🔥",
            "THANK YOU FOR JOINING US THIS SEASON!",
            "KINDLY REVIEW THE PINNED RULES BEFORE PROCEEDING.",
            "PLEASE INTRODUCE YOURSELF: AGE, CURRENT RANK, AND TIMEZONE.",
            "IF YOU HAVEN'T JOINED OUR MAIN CHANNEL YET, PLEASE JOIN HERE: https://t.me/+wkXVYyqiRYplZjk1",
            "WE RUN WEEKLY TOURNAMENTS WITH EXCITING PRIZES!",
            "STAY ACTIVE AND FOLLOW ANNOUNCEMENTS FOR UPDATES.",
        ]
        
def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN env var in Render.")
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))
    app.run_polling()

if __name__ == "__main__":
    keep_alive()
    main()
