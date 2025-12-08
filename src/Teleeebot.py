import asyncio
import os
import threading
from datetime import datetime
from http.server import SimpleHTTPRequestHandler
import socketserver

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# ==================== CONFIG ====================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = 7201369115                  # ← ILISAN NI SA IMONG CHAT ID
TARGET_CHAT = ADMIN_CHAT_ID                 # auto-send target
# ================================================

# ---------- Ibalik imong tinuod nga commands dinhi ----------
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not await is_user_authorized(user.id):
        await update.message.reply_text(
            f"✨ 𝙒𝙀𝙇𝘾𝙊𝙈𝙀 𝙃𝙄 {user.full_name}! ✨\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🔐 𝙆𝙀𝙔 𝙑𝙀𝙍𝙄𝙁𝙄𝘾𝘼𝙏𝙄𝙊𝙉 𝙍𝙀𝙌𝙐𝙄𝙍𝙀𝘿\n"
            "• Before you can access the generator,\n"
            "• You must enter a valid activation key.\n\n"
            "💠 𝙊𝙉𝙀 𝙆𝙀𝙔 = 𝙇𝙄𝙁𝙀𝙏𝙄𝙈𝙀 𝘼𝘾𝘾𝙀𝙎𝙎\n"
            "✨ Fast activation\n"
            "✨ Secure verification\n\n"
            "🛒 Buy key here: @KAZEHAYAMODZ\n"
            "━━━━━━━━━━━━━━━━━━━━━━"
        )
        return
        
# Ibalik imong ubang functions (genkey, key, revoke, mytime, broadcast, etc.)
# Example placeholders lang ni para dili mag-error:
async def genkey_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Genkey command")

async def key_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Key command")

async def revoke_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Revoke command")

async def mytime_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Mytime command")

async def broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Broadcast command")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Button clicked!")
# ------------------------------------------------------------

# =============== AUTO SEND EVERY 10 MINUTES ===============
async def auto_hello_task(app):
    while True:
        try:
            await app.bot.send_message(
                chat_id=TARGET_CHAT,
                text=f"Hello pogi 😍\nAuto-sent: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            print("Auto message sent!")
        except Exception as e:
            print(f"Auto-send error: {e}")
        
        await asyncio.sleep(300)  # 10 minutes
# ===========================================================

# =============== KEEP-ALIVE WEB SERVER (Render Free) ===============
def keep_alive():
    port = int(os.environ.get("PORT", 10000))
    with socketserver.TCPServer(("", port), SimpleHTTPRequestHandler) as httpd:
        print(f"Keep-alive server running on port {port}")
        httpd.serve_forever()
# ====================================================================

# ========================= MAIN BOT =========================
async def run_bot():
    if not BOT_TOKEN:
        print("ERROR: BOT_TOKEN not found in environment variables!")
        return

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Add all your handlers
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("genkey", genkey_cmd))
    app.add_handler(CommandHandler("key", key_cmd))
    app.add_handler(CommandHandler("revoke", revoke_cmd))
    app.add_handler(CommandHandler("mytime", mytime_cmd))
    app.add_handler(CommandHandler("broadcast", broadcast_cmd))
    app.add_handler(CallbackQueryHandler(button_callback))

    # Start the bot properly
    await app.initialize()
    await app.start()
    print("BOT IS FULLY CONNECTED! Starting auto task...")

    # Safe na i-start ang auto task diri
    app.create_task(auto_hello_task(app))

    # Keep the bot running forever
    await asyncio.Event().wait()

# ========================= ENTRY POINT =========================
if __name__ == "__main__":
    # Start keep-alive web server in background
    threading.Thread(target=keep_alive, daemon=True).start()
    
    # Run the Telegram bot
    asyncio.run(run_bot())
