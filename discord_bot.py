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

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# User memory for conversation history
user_memory = {}

def update_user_memory(user_id, message):
    if user_id not in user_memory:
        user_memory[user_id] = deque(maxlen=20)
    user_memory[user_id].append(message)

def get_conversation_history(user_id):
    return "\n".join(user_memory.get(user_id, []))

class DiscordBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True  # Required to read message content
        super().__init__(command_prefix='!', intents=intents)

    async def on_ready(self):
        logger.info(f'Logged in as {self.user} (ID: {self.user.id})')
        logger.info('------')

    async def on_message(self, message):
        if message.author == self.user:  # Don't respond to ourselves
            return

        if message.content.startswith('!'):  # Simple command handling example
            await self.process_commands(message)
            return

        try:
            user_id = str(message.author.id) # Use string for user_id consistency
            message_text = message.content
            
            # Handle attachments (images)
            image_processed = False
            if message.attachments:
                for attachment in message.attachments:
                    if 'image' in attachment.content_type:
                        image_data = BytesIO()
                        await attachment.save(image_data)
                        image_data.seek(0)
                        message_text = "[User sent an image]"
                        update_user_memory(user_id, "[User sent an image]")
                        image_processed = True
                        break # Process only the first image attachment
            
            if not image_processed:
                update_user_memory(user_id, message_text)
            
            # Get conversation history
            conversation_history = get_conversation_history(user_id)
            full_message = f"Conversation so far:\n{conversation_history}\n\nUser: {message_text}"
            
            # Process the message through your existing handler
            response, _ = handle_text_message(full_message, message_text, image_data=image_data if image_processed else None)
            
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
                        await message.channel.send(product_text, file=discord.File(BytesIO(image_response.content), 'image.png'))
                    else:
                        await message.channel.send(response)
                except Exception as e:
                    logger.error(f"Error processing image URL for Discord: {str(e)}")
                    await message.channel.send(response)
            else:
                await message.channel.send(response)
                
        except Exception as e:
            logger.error(f"Error in Discord on_message: {str(e)}")
            await message.channel.send("Sorry, I encountered an error processing your message.")

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
        logger.error(f"An unexpected error occurred with the Discord bot: {e}")

if __name__ == '__main__':
    run_discord_bot()
