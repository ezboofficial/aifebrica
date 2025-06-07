import os
import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from messageHandler import handle_text_message
from dotenv import load_dotenv
import requests
from io import BytesIO
from collections import deque
import time
import asyncio

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_ADMIN_ID = os.getenv("TELEGRAM_ADMIN_ID")

# Global variable to track bot instance
_bot_instance = None

class TelegramBot:
    def __init__(self):
        self.user_memory = {}
        self.application = None
        self.running = False
        self.lock = asyncio.Lock()

    def update_user_memory(self, user_id, message):
        if user_id not in self.user_memory:
            self.user_memory[user_id] = deque(maxlen=20)
        self.user_memory[user_id].append(message)

    def get_conversation_history(self, user_id):
        return "\n".join(self.user_memory.get(user_id, []))

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send welcome message when /start is issued."""
        await update.message.reply_text(
            "Hi! I am your shop assistant. How can I help you today?"
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send help message when /help is issued."""
        await update.message.reply_text(
            "I can help you with product inquiries and orders. Just send me a message!"
        )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle all incoming messages and photos."""
        try:
            user_id = update.message.from_user.id
            message_text = update.message.text or ""

            # Handle photo messages
            if update.message.photo:
                photo_file = await update.message.photo[-1].get_file()
                image_url = photo_file.file_path
                message_text = f"image_url: {image_url}"
                self.update_user_memory(user_id, "[User sent an image]")
            else:
                self.update_user_memory(user_id, message_text)

            # Get conversation history
            conversation_history = self.get_conversation_history(user_id)
            full_message = (
                f"Conversation so far:\n{conversation_history}\n\nUser: {message_text}"
            )

            # Process message through handler
            response, _ = handle_text_message(full_message, message_text)

            # Update memory if not an image response
            if not (
                " - http" in response
                and any(ext in response.lower() for ext in [".jpg", ".jpeg", ".png", ".gif"])
            ):
                self.update_user_memory(user_id, response)

            # Handle image responses
            if " - http" in response and any(
                ext in response.lower() for ext in [".jpg", ".jpeg", ".png", ".gif"]
            ):
                try:
                    image_url = response.split(" - ")[-1].strip()
                    product_text = response.split(" - ")[0]

                    # Download and send image
                    image_response = requests.get(image_url)
                    if image_response.status_code == 200:
                        await update.message.reply_photo(
                            photo=BytesIO(image_response.content),
                            caption=product_text,
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
            await update.message.reply_text(
                "Sorry, I encountered an error processing your message."
            )

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Silently handle specific errors and log others."""
        error = str(context.error)
        if "Conflict" not in error and "terminated by other getUpdates" not in error:
            logger.error(f"Update {update} caused error {context.error}")

    async def shutdown(self):
        """Gracefully shutdown the bot."""
        async with self.lock:
            if self.running:
                self.running = False
                if self.application:
                    await self.application.stop()
                    await self.application.shutdown()

    async def run(self):
        """Run the bot with connection management."""
        if not TELEGRAM_TOKEN:
            logger.error("TELEGRAM_TOKEN environment variable not set")
            return

        async with self.lock:
            if self.running:
                return

            self.running = True
            self.application = Application.builder().token(TELEGRAM_TOKEN).build()

            # Add handlers
            self.application.add_handler(CommandHandler("start", self.start))
            self.application.add_handler(CommandHandler("help", self.help_command))
            self.application.add_handler(
                MessageHandler(filters.TEXT | filters.PHOTO, self.handle_message)
            )
            self.application.add_error_handler(self.error_handler)

        while self.running:
            try:
                await self.application.initialize()
                await self.application.start()
                await self.application.updater.start_polling(
                    drop_pending_updates=True,
                    allowed_updates=Update.ALL_TYPES,
                )
                
                # Run until stopped
                while self.running:
                    await asyncio.sleep(1)

            except Exception as e:
                if self.running and "Conflict" not in str(e):
                    logger.error(f"Bot connection error: {str(e)}")
                await asyncio.sleep(10)
            finally:
                if self.running:
                    try:
                        await self.application.updater.stop()
                        await self.application.stop()
                        await self.application.shutdown()
                    except Exception:
                        pass

def get_bot_instance():
    """Singleton pattern to ensure only one bot instance exists."""
    global _bot_instance
    if _bot_instance is None:
        _bot_instance = TelegramBot()
    return _bot_instance

async def main():
    """Entry point for the bot."""
    bot = get_bot_instance()
    await bot.run()

if __name__ == "__main__":
    asyncio.run(main())
