import os
import logging
from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from messageHandler import handle_text_message
from dotenv import load_dotenv
import requests
from io import BytesIO
from collections import deque

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_ADMIN_ID = os.getenv("TELEGRAM_ADMIN_ID")

# User memory for conversation history
user_memory = {}

def update_user_memory(user_id, message):
    if user_id not in user_memory:
        user_memory[user_id] = deque(maxlen=20)
    user_memory[user_id].append(message)

def get_conversation_history(user_id):
    return "\n".join(user_memory.get(user_id, []))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    await update.message.reply_text('Hi! I am your shop assistant. How can I help you today?')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /help is issued."""
    await update.message.reply_text('I can help you with product inquiries and orders. Just send me a message!')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages."""
    try:
        user_id = str(update.message.from_user.id)
        message_text = update.message.text if update.message.text else ""
        
        # Handle photo attachments
        if update.message.photo:
            # Get the highest quality photo
            photo_file = await update.message.photo[-1].get_file()
            image_url = photo_file.file_path  # This is the path to the image on Telegram's servers
            
            # Create the proper image URL format that messageHandler expects
            message_text = f"image_url: https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{image_url}"
            update_user_memory(user_id, "[User sent an image]")
        
        # Get conversation history
        conversation_history = get_conversation_history(user_id)
        full_message = f"Conversation so far:\n{conversation_history}\n\nUser: {message_text}"
        
        # Process the message through your existing handler
        response, matched_product = handle_text_message(full_message, message_text)
        
        # Update memory with the response if it's not an image
        if not (" - http" in response and any(ext in response.lower() for ext in [".jpg", ".jpeg", ".png", ".gif"])):
            update_user_memory(user_id, response)

        if matched_product:
            # Format the response similar to the Facebook page
            response_text = (
                f"I found a similar product in our catalog ({(matched_product[1]*100):.1f}% match):\n"
                f"{matched_product[0]["type"]} ({matched_product[0]["category"]})\n"
                f"Sizes: {", ".join(matched_product[0]["size"])}\n"
                f"Colors: {", ".join(matched_product[0]["color"])}\n"
                f"Price: {matched_product[0]["price"]}{messageHandler.settings["currency"]}\n"
            )
            image_url = matched_product[0]["image"]

            try:
                image_response = requests.get(image_url)
                if image_response.status_code == 200:
                    await update.message.reply_photo(
                        photo=BytesIO(image_response.content),
                        caption=response_text
                    )
                else:
                    await update.message.reply_text(response_text + f"\nImage URL: {image_url}")
            except Exception as e:
                logger.error(f"Error sending image: {str(e)}")
                await update.message.reply_text(response_text + f"\nImage URL: {image_url}")
        else:
            await update.message.reply_text(response)            
    except Exception as e:
        logger.error(f"Error in handle_message: {str(e)}")
        await update.message.reply_text("Sorry, I encountered an error processing your message.")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors."""
    logger.error(f'Update {update} caused error {context.error}')

def main():
    """Start the bot."""
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN environment variable not set")
        return
    
    # Create the Application
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT | filters.PHOTO, handle_message))
    application.add_error_handler(error_handler)

    # Start the Bot
    application.run_polling()

if __name__ == '__main__':
    main()
