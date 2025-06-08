To suppress the specific error log about the Telegram bot conflict and generally reduce error logging, you can modify the logging configuration in your `telegram_bot.py` file. Here's how to do it:

1. First, modify the logging configuration at the top of `telegram_bot.py` to filter out this specific error:

```python
import logging
from logging import Filter

class TelegramConflictFilter(Filter):
    def filter(self, record):
        # Filter out the "Conflict: terminated by other getUpdates request" message
        return not (record.levelno == logging.ERROR and 
                  "Conflict: terminated by other getUpdates request" in record.getMessage())

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Add filter to the telegram.ext logger to suppress the conflict error
telegram_logger = logging.getLogger('telegram.ext.Updater')
telegram_logger.addFilter(TelegramConflictFilter())
```

2. If you want to completely disable all error logs from the Telegram bot (not recommended, but if you really want to), you can set the logging level to CRITICAL:

```python
# Configure logging - minimal version
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.CRITICAL  # Only show critical errors
)
```

3. Alternatively, if you want to keep your current logging level but suppress all error logs from the Telegram library, you can do:

```python
# Configure logging - suppress telegram errors
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Disable all error logs from telegram.ext
logging.getLogger('telegram.ext').setLevel(logging.CRITICAL)
```

Choose the approach that best fits your needs. The first solution (with the custom filter) is the most targeted approach as it only suppresses that specific conflict error while keeping other error logs visible.

The conflict error itself occurs when multiple instances of your bot are running simultaneously trying to poll for updates. While suppressing the error will make your logs cleaner, you should also ensure you only have one instance of your bot running to avoid any potential issues.

Here's the complete modified `telegram_bot.py` with the first approach (custom filter):

```python
import os
import logging
from logging import Filter
from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from messageHandler import handle_text_message
from dotenv import load_dotenv
import requests
from io import BytesIO
from collections import deque

class TelegramConflictFilter(Filter):
    def filter(self, record):
        # Filter out the "Conflict: terminated by other getUpdates request" message
        return not (record.levelno == logging.ERROR and 
                  "Conflict: terminated by other getUpdates request" in record.getMessage())

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Add filter to suppress the conflict error
telegram_logger = logging.getLogger('telegram.ext.Updater')
telegram_logger.addFilter(TelegramConflictFilter())

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_ADMIN_ID = os.getenv("TELEGRAM_ADMIN_ID")

# User memory for conversation history (same as in app.py)
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
        user_id = update.message.from_user.id
        message_text = update.message.text
        
        # Check for photo
        if update.message.photo:
            # Get the highest quality photo
            photo_file = await update.message.photo[-1].get_file()
            image_url = photo_file.file_path
            message_text = f"image_url: {image_url}"
            update_user_memory(user_id, "[User sent an image]")
        else:
            update_user_memory(user_id, message_text)
        
        # Get conversation history
        conversation_history = get_conversation_history(user_id)
        full_message = f"Conversation so far:\n{conversation_history}\n\nUser: {message_text}"
        
        # Process the message through your existing handler
        response, _ = handle_text_message(full_message, message_text)
        
        # Update memory with the response if it's not an image
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
```
