import os
import logging
from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from messageHandler import handle_text_message
from dotenv import load_dotenv
import requests
from io import BytesIO
from collections import deque
import warnings

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Filter out specific warnings and logs
class TelegramConflictFilter(logging.Filter):
    def filter(self, record):
        msg = record.getMessage()
        # Skip conflict errors and related HTTP logs
        if ("Conflict: terminated by other getUpdates request" in msg or 
            "HTTP/1.1 409 Conflict" in msg or
            "telegram.ext.Updater - ERROR - Error while getting Updates" in msg):
            return False
        return True

# Apply filter to all loggers
for handler in logging.root.handlers:
    handler.addFilter(TelegramConflictFilter())

# Also suppress warnings
warnings.filterwarnings("ignore", category=RuntimeWarning)

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
    await update.message.reply_text('Hi! I am your shop assistant. How can I help you today?')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('I can help you with product inquiries and orders. Just send me a message!')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.message.from_user.id
        message_text = update.message.text
        
        if update.message.photo:
            photo_file = await update.message.photo[-1].get_file()
            image_url = photo_file.file_path
            message_text = f"image_url: {image_url}"
            update_user_memory(user_id, "[User sent an image]")
        else:
            update_user_memory(user_id, message_text)
        
        conversation_history = get_conversation_history(user_id)
        full_message = f"Conversation so far:\n{conversation_history}\n\nUser: {message_text}"
        
        response, _ = handle_text_message(full_message, message_text)
        
        if not (" - http" in response and any(ext in response.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif'])):
            update_user_memory(user_id, response)
        
        if " - http" in response and any(ext in response.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif']):
            try:
                image_url = response.split(" - ")[-1].strip()
                product_text = response.split(" - ")[0]
                
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
            await update.message.reply_text(response)
            
    except Exception as e:
        logger.error(f"Error in handle_message: {str(e)}")
        await update.message.reply_text("Sorry, I encountered an error processing your message.")

class SilentErrorHandler:
    async def __call__(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        error = context.error
        # Completely suppress the conflict error
        if not (isinstance(error, Exception) and 
               "Conflict: terminated by other getUpdates request" in str(error)):
            logger.error('Exception while handling an update:', exc_info=error)

def main():
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN environment variable not set")
        return
    
    # Create application with customized settings
    application = Application.builder() \
        .token(TELEGRAM_TOKEN) \
        .connection_pool_size(1) \  # Minimize connection issues
        .pool_timeout(30) \
        .get_updates_connection_pool_size(1) \
        .build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT | filters.PHOTO, handle_message))
    
    # Add silent error handler
    application.add_error_handler(SilentErrorHandler())

    # Configure polling with longer timeout
    application.run_polling(
        poll_interval=1.0,
        timeout=30,
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES
    )

if __name__ == '__main__':
    main()
