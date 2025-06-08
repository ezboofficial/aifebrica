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
    help_text = """
I can help you with:
- Product inquiries
- Order processing
- Product recommendations

Just send me a message or photo of what you're looking for!
"""
    await update.message.reply_text(help_text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages and images."""
    try:
        user_id = update.message.from_user.id
        message_text = update.message.text if update.message.text else ""
        
        # Handle image attachments
        if update.message.photo:
            # Get the highest quality photo
            photo_file = await update.message.photo[-1].get_file()
            image_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{photo_file.file_path}"
            message_text = f"image_url: {image_url}"
            update_user_memory(user_id, "[User sent an image]")
        elif update.message.document and update.message.document.mime_type.startswith('image/'):
            # Handle document-style image uploads
            file = await update.message.document.get_file()
            image_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file.file_path}"
            message_text = f"image_url: {image_url}"
            update_user_memory(user_id, "[User sent an image]")
        elif message_text:
            update_user_memory(user_id, message_text)
        
        # Get conversation history
        conversation_history = get_conversation_history(user_id)
        full_message = f"Conversation so far:\n{conversation_history}\n\nUser: {message_text}"
        
        # Process the message through handler
        response, matched_product = handle_text_message(full_message, message_text)
        
        # Only update memory for non-image responses to avoid duplication
        if matched_product is None:
            update_user_memory(user_id, response)
        
        # Check if response contains an image URL in standard format
        if " - http" in response and any(ext in response.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif']):
            try:
                # Split response into product text and image URL
                parts = response.split(" - ")
                product_text = " - ".join(parts[:-1]).strip()
                image_url = parts[-1].strip()
                
                # Download and send image with caption
                image_response = requests.get(image_url)
                if image_response.status_code == 200:
                    await update.message.reply_photo(
                        photo=BytesIO(image_response.content),
                        caption=product_text
                    )
                else:
                    await update.message.reply_text(response)
            except Exception as e:
                logger.error(f"Error processing image URL: {str(e)}")
                await update.message.reply_text(response)
        else:
            # Send regular text response
            await update.message.reply_text(response)
            
    except Exception as e:
        logger.error(f"Error in handle_message: {str(e)}")
        error_msg = "⚠️ Sorry, I encountered an error processing your message. Please try again."
        await update.message.reply_text(error_msg)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors and notify admin."""
    logger.error(f'Update {update} caused error {context.error}')
    
    # Notify admin if ID is set
    if TELEGRAM_ADMIN_ID:
        try:
            await context.bot.send_message(
                chat_id=TELEGRAM_ADMIN_ID,
                text=f"⚠️ Bot Error:\n{context.error}"
            )
        except Exception as e:
            logger.error(f"Failed to notify admin: {str(e)}")

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
    
    # Handle both text and image messages
    application.add_handler(MessageHandler(
        filters.TEXT | filters.PHOTO | filters.Document.IMAGE, 
        handle_message
    ))
    
    application.add_error_handler(error_handler)

    # Start the Bot
    logger.info("Starting Telegram bot...")
    application.run_polling()

if __name__ == '__main__':
    main()
