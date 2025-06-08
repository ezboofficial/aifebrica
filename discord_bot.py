import os
import logging
import discord
from discord.ext import commands
import asyncio
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

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

class DiscordBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='!', intents=intents)

    async def on_ready(self):
        logger.info(f'Logged in as {self.user} (ID: {self.user.id})')
        logger.info('------')

    async def process_image_attachment(self, attachment):
        """Process image attachment and return temporary file path"""
        try:
            # Try both URL and proxy_url
            for url in [attachment.url, attachment.proxy_url]:
                try:
                    response = requests.get(url, stream=True)
                    if response.status_code == 200:
                        # Create temp file
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
                            for chunk in response.iter_content(1024):
                                tmp.write(chunk)
                            return tmp.name
                except Exception as e:
                    logger.warning(f"Failed to download image from {url}: {str(e)}")
                    continue
        except Exception as e:
            logger.error(f"Error processing image attachment: {str(e)}")
        return None

    async def on_message(self, message):
        if message.author == self.user:
            return

        if message.content.startswith('!'):
            await self.process_commands(message)
            return

        try:
            user_id = str(message.author.id)
            message_text = message.content
            image_processed = False
            image_path = None

            # Handle image attachments
            if message.attachments:
                for attachment in message.attachments:
                    if 'image' in attachment.content_type:
                        image_path = await self.process_image_attachment(attachment)
                        if image_path:
                            message_text = f"image_url: file://{image_path}"
                            update_user_memory(user_id, "[User sent an image]")
                            image_processed = True
                            break

            if not image_processed:
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
                    
                    async with message.channel.typing():
                        image_response = requests.get(image_url)
                        if image_response.status_code == 200:
                            await message.channel.send(
                                product_text,
                                file=discord.File(BytesIO(image_response.content), 'product.jpg')
                        else:
                            await message.channel.send(response)
                except Exception as e:
                    logger.error(f"Error sending product image: {str(e)}")
                    await message.channel.send(response)
            else:
                await message.channel.send(response)

        except Exception as e:
            logger.error(f"Error in message processing: {str(e)}")
            await message.channel.send("Sorry, I encountered an error processing your message.")

def update_user_memory(user_id, message):
    if user_id not in user_memory:
        user_memory[user_id] = deque(maxlen=20)
    user_memory[user_id].append(message)

def get_conversation_history(user_id):
    return "\n".join(user_memory.get(user_id, []))

def run_discord_bot():
    if not DISCORD_TOKEN:
        logger.error("DISCORD_TOKEN environment variable not set")
        return
    
    bot = DiscordBot()
    try:
        bot.run(DISCORD_TOKEN)
    except discord.LoginFailure:
        logger.error("Discord bot failed to log in. Check your token.")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")

if __name__ == '__main__':
    user_memory = {}
    run_discord_bot()
