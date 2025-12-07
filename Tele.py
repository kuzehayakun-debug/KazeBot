import asyncio
import os
import threading
from datetime import datetime

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# ────── CONFIG ──────
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = 123456789                  # ← ilisan ni sa imong real ID
TARGET_CHAT = ADMIN_CHAT_ID                # auto-send target (pwede usbon kung lahi)
# ─────────────────────

# Imong mga commands (ibalik nimo imong tinuod nga functions dinhi)
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot is alive!")

# (Ibalik imong genkey_cmd, key_cmd, revoke_cmd, mytime_cmd, broadcast_cmd, etc. dinhi)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # imong logic diri...

# ────── AUTO SEND EVERY 10 MINUTES ──────
async def auto_hello_task(app: Application):
    while True:
        try:
            await app.bot.send_message(
                chat_id=TARGET_CHAT,
                text=f"Hello pogi\nAuto-sent: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            print("Auto message sent!")
        except Exception as e:
            print(f"Auto-send error: {e}")
        
        await asyncio.sleep(600)  # 10 minutes

# ────── KEEP-ALIVE WEB SERVER (para dili matulog sa Render) ──────
def keep_alive():
    port = int(os.environ.get("PORT", 8080))
    from http.server import SimpleHTTPRequestHandler
    import socketserver
    with socketserver.TCPServer(("", port), SimpleHTTPRequestHandler) as httpd:
        print(f"Keep-alive server running on port {port}")
        httpd.serve_forever()

# ────── START TASKS AFTER BOT IS FULLY READY ──────
async def on_startup(app: Application):
    print("Bot fully connected! Starting auto task...")
    app.create_task(auto_hello_task(app))

# ────── MAIN ──────
def main():
    if not BOT_TOKEN:
        print("ERROR: BOT_TOKEN not found!")
        return

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Ibalik tanan nimo nga handlers dinhi
    app.add_handler(CommandHandler("start", start_cmd))
    # ... ug uban pa

    app.add_handler(CallbackQueryHandler(button_callback))

    # Safe na pag-start sa auto task
    app.pre_run_hook(on_startup)

    print("BOT RUNNING on Render... Pogi mode ON!")
    app.run_polling(drop_pending_updates=True)

# ────── ENTRY POINT ──────
if __name__ == "__main__":
    threading.Thread(target=keep_alive, daemon=True).start()
    main()
