from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        """Welcome to StockerBot! 🚀
StockerBot harnesses advanced predictive analytics and cutting-edge generative AI 🤖 to deliver actionable buy/sell signals 📈.
Whether you're a novice or a seasoned trader, StockerBot empowers you to navigate market fluctuations with confidence 🌊 and seize every opportunity 💡."""
    )

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Sorry, I didn't understand that command.")

async def unknown_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Sorry, I didn't understand that message.")

app = Application.builder().token("7755922511:AAHFXCVVmXlXzz_MdC9o-tKS49mNGlXu7Pg").build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.COMMAND, unknown))
app.add_handler(MessageHandler(filters.TEXT, unknown_text))

app.run_polling()
