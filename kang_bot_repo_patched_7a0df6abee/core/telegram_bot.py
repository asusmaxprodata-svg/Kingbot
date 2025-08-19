from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import os

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Define command functions
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Welcome to the bot! Use /help for command list.")

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_message = '''
    /start - Start the bot
    /status - Get current bot status
    /run - Start the trading bot
    /pause - Pause the trading bot
    /setpair <pair> - Set trading pair
    /setmode <mode> - Set trading mode (scalping, swing, etc.)
    /tune - Start tuning for optimal settings
    '''
    await update.message.reply_text(help_message)

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status_message = "Bot is currently running in TESTNET mode."
    await update.message.reply_text(status_message)

# Create the Application instance
application = Application.builder().token(BOT_TOKEN).build()

# Add command handlers
application.add_handler(CommandHandler("start", cmd_start))
application.add_handler(CommandHandler("help", cmd_help))
application.add_handler(CommandHandler("status", cmd_status))

# Run the bot
application.run_polling()
