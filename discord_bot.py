import os
import logging
import discord
from discord.ext import commands
import asyncio
from messageHandler import handle_text_message
from dotenv import load_dotenv
import requests
from io import BytesIO
from memory_manager import update_user_memory, get_conversation_history

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

    async def on_message(self, message):
        # Only respond to DMs, ignore messages in servers
        if not isinstance(message.channel, discord.DMChannel):
            return

        if message.author == self.user:
            return

        if message.content.startswith('!'):
            await self.process_commands(message)
            return

        try:
            user_id = str(message.author.id)
            message_text = message.content
            
            # Handle attachments (images)
            if message.attachments:
                for attachment in message.attachments:
                    if 'image' in attachment.content_type:
                        image_url = attachment.url
                        message_text = f"image_url: {image_url}"
                        update_user_memory("discord", user_id, "[User sent an image]")
                        
                        # Process the image directly through messageHandler
                        response, matched_product = handle_text_message(message_text, "[Image attachment]")
                        
                        if matched_product:
                            update_user_memory("discord", user_id, response)
                        
                        # Send the response
                        if " - http" in response and any(ext in response.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif']):
                            try:
                                parts = response.split(" - ")
                                product_text = parts[0]
                                image_url = parts[-1].strip()
                                
                                # Download image
                                image_response = requests.get(image_url)
                                if image_response.status_code == 200:
                                    # Send image with proper file handling
                                    await message.channel.send(
                                        content=product_text,
                                        file=discord.File(BytesIO(image_response.content), filename='product.png')
                                    )
                                else:
                                    await message.channel.send(response)
                            except Exception as e:
                                logger.error(f"Error processing image URL for Discord: {str(e)}")
                                await message.channel.send(response)
                        else:
                            await message.channel.send(response)
                        return
            
            if message_text:
                update_user_memory("discord", user_id, message_text)
            
            # Get conversation history
            conversation_history = get_conversation_history("discord", user_id)
            full_message = f"Conversation so far:\n{conversation_history}\n\nUser: {message_text}"
            
            # Process the message through your existing handler
            response, matched_product = handle_text_message(full_message, message_text)
            
            # Update memory with the response if it's not an image
            if not (" - http" in response and any(ext in response.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif'])):
                update_user_memory("discord", user_id, response)
            
            # Check if response contains an image URL
            if " - http" in response and any(ext in response.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif']):
                try:
                    parts = response.split(" - ")
                    product_text = parts[0]
                    image_url = parts[-1].strip()
                    
                    # Download image
                    image_response = requests.get(image_url)
                    if image_response.status_code == 200:
                        # Send image with proper file handling
                        await message.channel.send(
                            content=product_text,
                            file=discord.File(BytesIO(image_response.content), filename='product.png')
                        )
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
