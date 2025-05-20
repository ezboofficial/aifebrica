import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler,
    ContextTypes
)
import messageHandler
from collections import deque
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Telegram Bot Token from environment
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# User memory for conversation history (similar to Facebook implementation)
user_memory = {}

def update_user_memory(user_id, message):
    if user_id not in user_memory:
        user_memory[user_id] = deque(maxlen=20)
    user_memory[user_id].append(message)

def get_conversation_history(user_id):
    return "\n".join(user_memory.get(user_id, []))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    welcome_message = (
        f"👋 Hello {user.first_name}! I'm {messageHandler.get_settings()['ai_name']} from "
        f"{messageHandler.get_settings()['shop_name']}. How can I help you today?"
    )
    await update.message.reply_text(welcome_message)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming messages."""
    if not messageHandler.get_settings():
        await update.message.reply_text("😔 Sorry, I'm currently unavailable. Please try again later.")
        return

    user_id = update.message.from_user.id
    message_text = update.message.text
    message_photo = update.message.photo

    if message_photo:
        # Handle photo messages
        photo_file = await message_photo[-1].get_file()
        image_url = photo_file.file_path
        update_user_memory(user_id, f"[User sent an image: {image_url}]")
        
        response, matched_product = messageHandler.handle_text_message(
            f"image_url: {image_url}", 
            "[Image attachment]"
        )
        
        if matched_product:
            update_user_memory(user_id, response)
        
        # Send the response back to the user
        if " - http" in response and any(ext in response.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif']):
            try:
                # Split product text and image URL
                parts = response.split(" - ")
                product_text = " - ".join(parts[:-1])
                image_url = parts[-1].strip()
                
                await update.message.reply_photo(image_url, caption=product_text)
            except Exception as e:
                logger.error(f"Error sending image: {str(e)}")
                await update.message.reply_text(response)
        else:
            await update.message.reply_text(response)
    elif message_text:
        # Handle text messages
        update_user_memory(user_id, message_text)
        conversation_history = get_conversation_history(user_id)
        full_message = f"Conversation so far:\n{conversation_history}\n\nUser: {message_text}"
        
        response, _ = messageHandler.handle_text_message(full_message, message_text)
        
        # Check if response contains an image URL
        if " - http" in response and any(ext in response.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif']):
            try:
                # Split product text and image URL
                parts = response.split(" - ")
                product_text = " - ".join(parts[:-1])
                image_url = parts[-1].strip()
                
                await update.message.reply_photo(image_url, caption=product_text)
            except Exception as e:
                logger.error(f"Error sending image: {str(e)}")
                await update.message.reply_text(response)
        else:
            await update.message.reply_text(response)
            update_user_memory(user_id, response)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors and send a generic message to the user."""
    logger.error(f"Update {update} caused error {context.error}")
    await update.message.reply_text("😔 Sorry, I encountered an error processing your message. Please try again later.")

def main() -> None:
    """Start the bot."""
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.PHOTO, handle_message))
    application.add_handler(CallbackQueryHandler(button))
    
    # Register error handler
    application.add_error_handler(error_handler)

    # Run the bot until the user presses Ctrl-C
    application.run_polling()

if __name__ == "__main__":
    main()
