# Fixed BotTelegramSrc.py - server-friendly version for Render (or similar)
# Key changes:
# - Uses server-writable path: /tmp/accounts (ephemeral) for storing text files & keys.json
# - Reads BOT_TOKEN and OWNER_ID from environment variables (required)
# - Safe handling for missing env vars with clear error messages
# - Ensures folders are created with exist_ok=True (no permission error on /storage)
#
# IMPORTANT: On Render set environment variables:
#   BOT_TOKEN -> your bot token (string)
#   OWNER_ID -> your numeric Telegram user id (integer)
#
# If you want persistent storage across deploys, upload files to a database or use external storage
# (S3, Cloud Storage). /tmp is ephemeral and will be cleared between deploys.

import os
import sys
from pathlib import Path
import json

# --- Environment / secrets ---
BOT_TOKEN = os.getenv('BOT_TOKEN')
OWNER_ID_ENV = os.getenv('OWNER_ID')

if not BOT_TOKEN:
    print('ERROR: BOT_TOKEN environment variable not set. Set it in Render environment variables.', file=sys.stderr)
    raise SystemExit(1)

if not OWNER_ID_ENV:
    print('ERROR: OWNER_ID environment variable not set. Set it in Render environment variables.', file=sys.stderr)
    raise SystemExit(1)

try:
    OWNER_ID = int(OWNER_ID_ENV)
except ValueError:
    print('ERROR: OWNER_ID must be an integer (your numeric Telegram id).', file=sys.stderr)
    raise SystemExit(1)

# --- Paths (server-friendly) ---
# Use /tmp/accounts for ephemeral storage on Render. Change to another writable path if needed.
BASE_FOLDER = Path('/tmp/accounts')
BASE_FOLDER.mkdir(parents=True, exist_ok=True)

KEYS_FILE = BASE_FOLDER / 'keys.json'

# Example file map - adapt names to your bot logic
FILE_MAP = {
    "valorant": BASE_FOLDER / "Valorant.txt",
    "roblox": BASE_FOLDER / "Roblox.txt",
    "random": BASE_FOLDER / "Random.txt",
    "mtacc": BASE_FOLDER / "Mtacc.txt",
    "gmail": BASE_FOLDER / "Gmail.txt",
    "gaslite": BASE_FOLDER / "Gaslite.txt",
    "facebook": BASE_FOLDER / "Facebook.txt",
    "crossfire": BASE_FOLDER / "Crossfire.txt",
    "codm": BASE_FOLDER / "CODM.txt",
    "bloodstrike": BASE_FOLDER / "Bloodstrike.txt",
    "100082": BASE_FOLDER / "100082.txt",
}

# Ensure files exist (create empty files if missing)
for p in FILE_MAP.values():
    if not p.parent.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        p.write_text('', encoding='utf-8')

# Ensure keys.json exists
if not KEYS_FILE.exists():
    KEYS_FILE.write_text(json.dumps({}, indent=2), encoding='utf-8')

# --- Minimal bot skeleton ---
# This is a placeholder skeleton so the file runs without permission errors.
# Reintegrate your full bot logic below, using FILE_MAP and KEYS_FILE paths.
def load_keys():
    try:
        with KEYS_FILE.open('r', encoding='utf-8') as fh:
            return json.load(fh)
    except Exception:
        return {}

def save_keys(data):
    with KEYS_FILE.open('w', encoding='utf-8') as fh:
        json.dump(data, fh, indent=2)

def main():
    # Print paths to logs so you can verify in Render logs
    print('BOT_TOKEN length:', len(BOT_TOKEN))
    print('OWNER_ID:', OWNER_ID)
    print('BASE_FOLDER:', str(BASE_FOLDER))
    print('KEYS_FILE:', str(KEYS_FILE))
    print('Existing account files:')
    for k,v in FILE_MAP.items():
        print(' -', k, '->', v)
    print('Keys content:', load_keys())

    # Here you should initialize your telegram bot as usual, for example with python-telegram-bot v20+
    # Example (uncomment and adapt if you use python-telegram-bot):
    #
    # from telegram import Update
    # from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
    #
    # async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    #     await update.message.reply_text('Bot is running on Render!')
    #
    # app = ApplicationBuilder().token(BOT_TOKEN).build()
    # app.add_handler(CommandHandler('start', start))
    # app.run_polling()  # Or use app.run_webhook(...) for webhooks
    #
    # NOTE: Render runs web services; long-running polling may be okay on a background worker.
    # Consider using webhooks if you host as a web service.
    #
    print('\nREADY (placeholder). Replace with your bot setup.')

if __name__ == '__main__':
    main()
