import asyncio
import json
import http.client
import urllib.parse
from datetime import datetime, timedelta
from bson import ObjectId
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    ConversationHandler,
    CallbackQueryHandler,
    filters,
)
from pymongo import MongoClient
from urllib.parse import quote_plus
from groq import Groq
from dotenv import load_dotenv
import os
import logging

# Set up logging for debugging scheduler and job execution
logging.basicConfig(level=logging.INFO)

load_dotenv()

telegram_token = os.environ.get('TELEGRAM_TOKEN')
groq_api = os.environ.get('GROQ_API')
rapid_key = os.environ.get('RAPID_KEY')

# --- MongoDB Setup ---
password = quote_plus("Vasani@12345")
MONGO_URI = f"mongodb+srv://ankurcourses:{password}@stock.jnaw2.mongodb.net/"
client = MongoClient(MONGO_URI)
db = client["stockerbot_db"]
portfolio_collection = db["portfolio"]
# New collection for user settings
user_settings_collection = db["user_settings"]
# --- End MongoDB Setup ---

# Define conversation states for the add stock flow
STOCK_SUGGESTIONS, STOCK_CODE_INPUT, STOCK_BUY_PRICE, STOCK_QUANTITY = range(4)
# Define conversation states for the remove stock flow
REMOVAL_SELECTION, REMOVAL_SELL_PRICE, REMOVAL_QUANTITY = range(3)
# Define conversation state for the news flow
NEWS_INPUT = 0
# Define conversation state for the schedule flow
SCHEDULE_SETTING = 0

# ----------------------------
# Helper Functions
# ----------------------------
def get_current_price(stock_name: str) -> float:
    conn = http.client.HTTPSConnection("indian-stock-exchange-api2.p.rapidapi.com")
    headers = {
        'x-rapidapi-key': rapid_key,
        'x-rapidapi-host': "indian-stock-exchange-api2.p.rapidapi.com"
    }
    encoded_name = urllib.parse.quote(stock_name)
    endpoint = f"/stock?name={encoded_name}"
    conn.request("GET", endpoint, headers=headers)
    res = conn.getresponse()
    data = res.read()
    json_data = json.loads(data.decode("utf-8"))
    current_price_str = json_data.get("currentPrice", {}).get("NSE")
    current_price = 0.0
    if current_price_str is not None:
        try:
            current_price = float(current_price_str)
        except (ValueError, TypeError):
            current_price = 0.0
    if current_price == 0.0:
        current_price_str = json_data.get("currentPrice", {}).get("BSE")
        if current_price_str is not None:
            try:
                current_price = float(current_price_str)
            except (ValueError, TypeError):
                current_price = 0.0
    return current_price

def get_stock_news(stock_name: str) -> str:
    conn = http.client.HTTPSConnection("indian-stock-exchange-api2.p.rapidapi.com")
    headers = {
        'x-rapidapi-key': rapid_key,
        'x-rapidapi-host': "indian-stock-exchange-api2.p.rapidapi.com"
    }
    encoded_name = urllib.parse.quote(stock_name)
    endpoint = f"/stock?name={encoded_name}"
    conn.request("GET", endpoint, headers=headers)
    res = conn.getresponse()
    data = res.read()
    json_data = json.loads(data.decode("utf-8"))
    recent_news = json_data.get("recentNews", [])
    if not recent_news:
        return f"😕 No recent news found for stock '{stock_name}'."
    messages = []
    for news_item in recent_news[:3]:
        headline = news_item.get("headline", "No headline")
        date = news_item.get("date", "Unknown date")
        messages.append(f"📰 {headline} ({date})")
    return "\n".join(messages)

def get_stock_details(stock_name: str) -> dict:
    conn = http.client.HTTPSConnection("indian-stock-exchange-api2.p.rapidapi.com")
    headers = {
        'x-rapidapi-key': rapid_key,
        'x-rapidapi-host': "indian-stock-exchange-api2.p.rapidapi.com"
    }
    encoded_name = urllib.parse.quote(stock_name)
    endpoint = f"/stock?name={encoded_name}"
    conn.request("GET", endpoint, headers=headers)
    res = conn.getresponse()
    data = res.read()
    json_data = json.loads(data.decode("utf-8"))
    details = {
        "companyName": json_data.get("companyName", ""),
        "industry": json_data.get("industry", ""),
        "stockTechnicalData": json_data.get("stockTechnicalData", []),
        "riskMeter": json_data.get("riskMeter", {}),
        "recentNews": get_stock_news(stock_name)
    }
    return details

def get_prediction_for_stock(data: dict) -> str:
    client = Groq(api_key=groq_api)
    messages = [
        {"role": "system", "content": "You are a stock trading assistant. Provide a recommendation (Buy or Sell) based on the following json data."},
        {"role": "user", "content": json.dumps(data)}
    ]
    completion = client.chat.completions.create(
        model="gemma2-9b-it",
        messages=messages,
        temperature=1,
        max_completion_tokens=1024,
        top_p=1,
        stream=False,
        response_format={"type": "json_object"},
        stop=None,
    )
    return completion.choices[0].message.content or "No prediction"

# ----------------------------
# Cancel & Error Handlers (Define early!)
# ----------------------------
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Operation cancelled.")
    return ConversationHandler.END

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    print(f"Exception while handling an update: {context.error}")

# ----------------------------
# Command Handlers
# ----------------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "<b>Welcome to StockerBot! 🚀</b>\n"
        "I'm here to help you manage your stock portfolio using advanced predictive analytics and AI.\n\n"
        "Available commands:\n"
        "/add - Add Stock to Portfolio 📈\n"
        "/view - View Portfolio 👀\n"
        "/remove - Remove Stock from Portfolio ❌\n"
        "/news - Get Latest News 📰\n"
        "/schedule - Schedule Notification ⏰\n"
        "/cancel - Cancel the current operation ❌\n\n"
        "Please use the bot's command menu to navigate and choose your desired option.",
        parse_mode='HTML'
    )

async def add_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Reliance 🤝", callback_data="STOCK_RELIANCE"),
         InlineKeyboardButton("TCS 💻", callback_data="STOCK_TCS")],
        [InlineKeyboardButton("HDFC Bank 🏦", callback_data="STOCK_HDFC"),
         InlineKeyboardButton("ICICI Bank 💳", callback_data="STOCK_ICICI")],
        [InlineKeyboardButton("Other ✍️", callback_data="STOCK_OTHER")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Please select a BSE stock or choose 'Other' to enter manually: 🔍",
        reply_markup=reply_markup
    )
    return STOCK_SUGGESTIONS

async def stock_suggestions_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data.startswith("STOCK_"):
        if data == "STOCK_OTHER":
            await query.edit_message_text("✍️ Please type the stock name or code:")
            return STOCK_CODE_INPUT
        else:
            stock_code = data.split("_")[1]
            context.user_data['stock_code'] = stock_code
            await query.edit_message_text(
                f"Please enter the buying price for <b>{stock_code}</b>: 💵",
                parse_mode='HTML'
            )
            return STOCK_BUY_PRICE
    else:
        await query.edit_message_text("Unknown selection. 🤷‍♀️")
        return ConversationHandler.END

async def stock_code_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stock_code = update.message.text.strip()
    context.user_data['stock_code'] = stock_code
    await update.message.reply_text(
        f"Please enter the buying price for <b>{stock_code}</b>: 💵",
        parse_mode='HTML'
    )
    return STOCK_BUY_PRICE

async def stock_buy_price_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        buy_price = float(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ Invalid price. Please enter a numeric value for the buying price:")
        return STOCK_BUY_PRICE
    context.user_data['buy_price'] = buy_price
    stock_code = context.user_data.get('stock_code', "Unknown")
    await update.message.reply_text(
        f"Please enter the quantity for <b>{stock_code}</b>: 📊",
        parse_mode='HTML'
    )
    return STOCK_QUANTITY

async def stock_quantity_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        quantity = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ Invalid quantity. Please enter a numeric value for the quantity:")
        return STOCK_QUANTITY
    stock_code = context.user_data.get('stock_code', "Unknown")
    buy_price = context.user_data.get('buy_price', 0.0)
    stock_document = {
        "stock_code": stock_code,
        "buy_price": buy_price,
        "quantity": quantity,
        "user_id": update.effective_user.id,
        "username": update.effective_user.username,
        "buy_timestamp": datetime.utcnow()
    }
    portfolio_collection.insert_one(stock_document)
    await update.message.reply_text(
        f"✅ Stock '<b>{stock_code}</b>' purchased at ₹{buy_price} for {quantity} shares added to your portfolio!",
        parse_mode='HTML'
    )
    return ConversationHandler.END

async def view_portfolio_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    stocks = list(portfolio_collection.find({"user_id": user_id}))
    if not stocks:
        await update.message.reply_text("😕 Your portfolio is empty.")
        return
    messages = []
    for stock in stocks:
        stock_code = stock.get("stock_code", "Unknown")
        buy_price = stock.get("buy_price", 0.0)
        quantity = stock.get("quantity", 0)
        current_price = await asyncio.to_thread(get_current_price, stock_code)
        diff = current_price - buy_price
        if diff > 0:
            emoji = "🔺"
            diff_text = f"up by ₹{diff:.2f}"
        elif diff < 0:
            emoji = "🔻"
            diff_text = f"down by ₹{abs(diff):.2f}"
        else:
            emoji = "➖"
            diff_text = "no change"
        messages.append(
            f"✅ {stock_code}: Current ₹{current_price:.2f} ({emoji} {diff_text})\nQuantity: {quantity} shares"
        )
    text = "👤 <b>Your Portfolio:</b>\n" + "\n".join(messages)
    await update.message.reply_text(text, parse_mode='HTML')

async def remove_stock_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    stocks = list(portfolio_collection.find({"user_id": user_id}))
    if not stocks:
        await update.message.reply_text("😕 Your portfolio is empty. Nothing to remove!")
        return ConversationHandler.END
    keyboard = []
    for stock in stocks:
        button = InlineKeyboardButton(
            f"{stock.get('stock_code', 'Unknown')} (Qty: {stock.get('quantity', 'N/A')})",
            callback_data=f"REMOVE_STOCK_{str(stock['_id'])}"
        )
        keyboard.append([button])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Please select a stock to remove: 🗑️", reply_markup=reply_markup)
    return REMOVAL_SELECTION

async def remove_stock_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data.startswith("REMOVE_STOCK_"):
        doc_id = data.split("_")[-1]
        stock_doc = portfolio_collection.find_one({"_id": ObjectId(doc_id)})
        if not stock_doc:
            await query.edit_message_text("❌ Stock not found.")
            return ConversationHandler.END
        context.user_data['removal_doc_id'] = doc_id
        context.user_data['removal_stock_code'] = stock_doc.get('stock_code', 'Unknown')
        await query.edit_message_text(
            f"Please enter the selling price for <b>{stock_doc.get('stock_code', 'Unknown')}</b>: 💰",
            parse_mode='HTML'
        )
        return REMOVAL_SELL_PRICE
    else:
        await query.edit_message_text("Unknown selection. 🤷‍♀️")
        return ConversationHandler.END

async def remove_stock_sell_price_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        sell_price = float(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ Invalid price. Please enter a numeric value for the selling price:")
        return REMOVAL_SELL_PRICE
    context.user_data['sell_price'] = sell_price
    stock_code = context.user_data.get('removal_stock_code', "Unknown")
    await update.message.reply_text(
        f"Please enter the quantity to sell for <b>{stock_code}</b>: 📊",
        parse_mode='HTML'
    )
    return REMOVAL_QUANTITY

async def remove_stock_quantity_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        sell_quantity = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ Invalid quantity. Please enter a numeric value for the quantity:")
        return REMOVAL_QUANTITY
    doc_id = context.user_data.get('removal_doc_id')
    stock_code = context.user_data.get('removal_stock_code', "Unknown")
    sell_price = context.user_data.get('sell_price', 0.0)
    portfolio_collection.update_one(
        {"_id": ObjectId(doc_id)},
        {"$set": {"sell_price": sell_price, "sell_quantity": sell_quantity, "sell_timestamp": datetime.utcnow()}}
    )
    portfolio_collection.delete_one({"_id": ObjectId(doc_id)})
    await update.message.reply_text(
        f"✅ Stock '<b>{stock_code}</b>' sold at ₹{sell_price} for {sell_quantity} shares and removed from your portfolio!",
        parse_mode='HTML'
    )
    return ConversationHandler.END

async def news_stock_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📰 Please enter the stock name for which you want the latest news:")
    return NEWS_INPUT

async def news_stock_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stock_name = update.message.text.strip()
    news_text = await asyncio.to_thread(get_stock_news, stock_name)
    await update.message.reply_text(news_text, parse_mode='HTML')
    return ConversationHandler.END

news_conv_handler = ConversationHandler(
    entry_points=[CommandHandler("news", news_stock_start)],
    states={
        NEWS_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, news_stock_handler)]
    },
    fallbacks=[CommandHandler("cancel", cancel)]
)

async def schedule_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("ON 🔔", callback_data="SCHEDULE_ON"),
         InlineKeyboardButton("OFF 🔕", callback_data="SCHEDULE_OFF")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Do you want to turn notifications ON or OFF? Please select:", reply_markup=reply_markup)
    return SCHEDULE_SETTING

async def schedule_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "SCHEDULE_ON":
        value = 1
        message = "✅ Notifications turned ON."
    elif data == "SCHEDULE_OFF":
        value = 0
        message = "✅ Notifications turned OFF."
    else:
        message = "Unknown selection."
        return ConversationHandler.END
    user_id = query.from_user.id
    user_settings_collection.update_one(
        {"user_id": user_id},
        {"$set": {"notifications": value, "updated_at": datetime.utcnow()}},
        upsert=True
    )
    portfolio_collection.update_many(
        {"user_id": user_id},
        {"$set": {"notification": value}}
    )
    await query.edit_message_text(message)
    return ConversationHandler.END

schedule_conv_handler = ConversationHandler(
    entry_points=[CommandHandler("schedule", schedule_start)],
    states={
        SCHEDULE_SETTING: [CallbackQueryHandler(schedule_handler)]
    },
    fallbacks=[CommandHandler("cancel", cancel)]
)

add_conv_handler = ConversationHandler(
    entry_points=[CommandHandler("add", add_stock)],
    states={
        STOCK_SUGGESTIONS: [CallbackQueryHandler(stock_suggestions_handler)],
        STOCK_CODE_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, stock_code_input_handler)],
        STOCK_BUY_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, stock_buy_price_handler)],
        STOCK_QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, stock_quantity_handler)]
    },
    fallbacks=[CommandHandler("cancel", cancel)]
)

remove_conv_handler = ConversationHandler(
    entry_points=[CommandHandler("remove", remove_stock_start)],
    states={
        REMOVAL_SELECTION: [CallbackQueryHandler(remove_stock_handler)],
        REMOVAL_SELL_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_stock_sell_price_handler)],
        REMOVAL_QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_stock_quantity_handler)]
    },
    fallbacks=[CommandHandler("cancel", cancel)]
)

async def schedule_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏰ Schedule Notification feature is not implemented yet.")

# Daily prediction function using Groq LLM API
async def send_daily_predictions(app: Application):
    # Get all users with notifications turned on
    users = user_settings_collection.find({"notifications": 1})
    for user in users:
        user_id = user["user_id"]
        stocks = list(portfolio_collection.find({"user_id": user_id}))
        if not stocks:
            continue
        predictions = []
        for stock in stocks:
            stock_code = stock.get("stock_code", "Unknown")
            buy_price = stock.get("buy_price", 0.0)
            quantity = stock.get("quantity", 0)
            current_price = await asyncio.to_thread(get_current_price, stock_code)
            diff = current_price - buy_price
            details = get_stock_details(stock_code)
            data_to_send = {
                "companyName": details.get("companyName"),
                "industry": details.get("industry"),
                "current_price": current_price,
                "stockTechnicalData": details.get("stockTechnicalData"),
                "riskMeter": details.get("riskMeter"),
                "recentNews": details.get("recentNews"),
                "buy_price": buy_price,
                "quantity": quantity,
                "difference": diff
            }
            prediction = await asyncio.to_thread(get_prediction_for_stock, data_to_send)
            predictions.append(f"{stock_code}: {prediction}")
        if predictions:
            logging.info("Sending daily predictions to user_id %s", user_id)
            message = "📊 <b>Daily Prediction for your Stocks:</b>\n" + "\n".join(predictions)
            await app.bot.send_message(chat_id=user_id, text=message, parse_mode="HTML")

async def main():
    app = Application.builder().token(telegram_token).build()
    # Register command and conversation handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(add_conv_handler)
    app.add_handler(remove_conv_handler)
    app.add_handler(CommandHandler("view", view_portfolio_command))
    app.add_handler(news_conv_handler)
    app.add_handler(schedule_conv_handler)
    app.add_handler(CommandHandler("cancel", cancel))
    
    await app.bot.set_my_commands([
        BotCommand("start", "Start the bot 🚀"),
        BotCommand("add", "Add Stock to Portfolio 📈"),
        BotCommand("view", "View Portfolio 👀"),
        BotCommand("remove", "Remove Stock from Portfolio ❌"),
        BotCommand("news", "Get Latest News 📰"),
        BotCommand("schedule", "Schedule Notification ⏰"),
        BotCommand("cancel", "Cancel the current operation ❌")
    ])
    
    # Set up APScheduler to run the daily prediction job every day at 09:00 local time.
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_daily_predictions, 'cron', hour=3, minute=10, args=[app])
    scheduler.start()
    
    # Register the error handler
    app.add_error_handler(error_handler)
    
    await app.run_polling()

if __name__ == '__main__':
    try:
        import nest_asyncio
        nest_asyncio.apply()
    except ImportError:
        pass
    asyncio.run(main())
