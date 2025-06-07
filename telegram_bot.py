import os
import logging
from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from messageHandler import handle_text_message
from dotenv import load_dotenv
import requests
from io import BytesIO
from app import update_user_memory, get_conversation_history

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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    user_id = str(update.message.from_user.id)
    update_user_memory(user_id, "[User started conversation]")
    await update.message.reply_text('Hi! I am your shop assistant. How can I help you today?')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /help is issued."""
    user_id = str(update.message.from_user.id)
    update_user_memory(user_id, "[User requested help]")
    await update.message.reply_text('I can help you with product inquiries and orders. Just send me a message!')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages."""
    try:
        user_id = str(update.message.from_user.id)
        message_text = update.message.text
        
        # Check for photo
        if update.message.photo:
            # Get the highest quality photo
            photo_file = await update.message.photo[-1].get_file()
            image_url = photo_file.file_path
            message_text = f"image_url: {image_url}"
            update_user_memory(user_id, "[User sent an image]")
        elif message_text:
            update_user_memory(user_id, message_text)
        
        # Get conversation history
        conversation_history = get_conversation_history(user_id)
        full_message = f"Conversation so far:\n{conversation_history}\n\nUser: {message_text}"
        
        # Process the message through your existing handler
        response, _ = handle_text_message(full_message, message_text)
        
        # Update memory with response if not an image
        if not (" - http" in response and any(ext in response.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif'])):
            update_user_memory(user_id, response)
        
        # Check if response contains an image URL
        if " - http" in response and any(ext in response.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif']):
            try:
                image_url = response.split(" - ")[-1].strip()
                product_text = response.split(" - ")[0]
                
                # Download image
                image_response = requests.get(image_url)
                if image_response.status_code == 200:
                    # Send image
                    await update.message.reply_photo(
                        photo=BytesIO(image_response.content),
                        caption=product_text
                    )
                    update_user_memory(user_id, product_text)
                else:
                    await update.message.reply_text(response)
            except Exception as e:
                logger.error(f"Error processing image URL: {str(e)}")
                await update.message.reply_text(response)
        else:
            await update.message.reply_text(response)
            
    except Exception as e:
        logger.error(f"Error in handle_message: {str(e)}")
        await update.message.reply_text("Sorry, I encountered an error processing your message.")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors."""
    logger.error(f'Update {update} caused error {context.error}')
    if update.message:
        user_id = str(update.message.from_user.id)
        update_user_memory(user_id, "[System encountered an error]")

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
    logger.info("Starting Telegram bot...")
    application.run_polling()

if __name__ == '__main__':
    main()
