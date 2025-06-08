import os
import logging
from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from messageHandler import handle_text_message
from dotenv import load_dotenv
import requests
from io import BytesIO
from collections import deque
from PIL import Image
import tempfile

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

user_memory = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Hi! I am your shop assistant. How can I help you today?')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('I can help you with product inquiries and orders. Just send me a message!')

async def process_telegram_photo(photo_file):
    """Process Telegram photo and return temporary file path"""
    try:
        # Download photo content
        photo_bytes = await photo_file.download_as_bytearray()
        
        # Create temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
            tmp.write(photo_bytes)
            return tmp.name
    except Exception as e:
        logger.error(f"Error processing Telegram photo: {str(e)}")
        return None

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = str(update.message.from_user.id)
        message_text = update.message.text or ""
        image_path = None

        # Handle photo
        if update.message.photo:
            photo_file = await update.message.photo[-1].get_file()
            image_path = await process_telegram_photo(photo_file)
            if image_path:
                message_text = f"image_url: file://{image_path}"
                update_user_memory(user_id, "[User sent an image]")
            else:
                await update.message.reply_text("Sorry, I couldn't process that image. Please try again.")
                return

        elif message_text:
            update_user_memory(user_id, message_text)

        # Get conversation history
        conversation_history = get_conversation_history(user_id)
        full_message = f"Conversation so far:\n{conversation_history}\n\nUser: {message_text}"

        # Process message
        response, _ = handle_text_message(full_message, message_text)

        # Clean up temp file if exists
        if image_path and os.path.exists(image_path):
            try:
                os.unlink(image_path)
            except Exception as e:
                logger.warning(f"Failed to delete temp image: {str(e)}")

        # Update memory with response
        if not (" - http" in response and any(ext in response.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif'])):
            update_user_memory(user_id, response)

        # Handle image response
        if " - http" in response and any(ext in response.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif']):
            try:
                image_url = response.split(" - ")[-1].strip()
                product_text = response.split(" - ")[0]
                
                async with context.bot:
                    image_response = requests.get(image_url)
                    if image_response.status_code == 200:
                        await update.message.reply_photo(
                            photo=BytesIO(image_response.content),
                            caption=product_text
                        )
                    else:
                        await update.message.reply_text(response)
            except Exception as e:
                logger.error(f"Error sending product image: {str(e)}")
                await update.message.reply_text(response)
        else:
            await update.message.reply_text(response)

    except Exception as e:
        logger.error(f"Error in message processing: {str(e)}")
        await update.message.reply_text("Sorry, I encountered an error processing your message.")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f'Update {update} caused error {context.error}')

def update_user_memory(user_id, message):
    if user_id not in user_memory:
        user_memory[user_id] = deque(maxlen=20)
    user_memory[user_id].append(message)

def get_conversation_history(user_id):
    return "\n".join(user_memory.get(user_id, []))

def main():
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN environment variable not set")
        return
    
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT | filters.PHOTO, handle_message))
    application.add_error_handler(error_handler)

    application.run_polling()

if __name__ == '__main__':
    main()
