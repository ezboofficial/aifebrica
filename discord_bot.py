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
                        update_user_memory(user_id, "discord", "[User sent an image]", sender="user")
                        
                        # Process the image directly through messageHandler
                        response, matched_product = handle_text_message(message_text, "[Image attachment]")
                        
                        if matched_product:
                            update_user_memory(user_id, "discord", response, sender="ai")
                        
                        # Send the response
                        if " - http" in response and any(ext in response.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif']):
                            try:
                                image_url = response.split(" - ")[-1].strip()
                                product_text = response.split(" - ")[0]
                                
                                # Download image
                                image_response = requests.get(image_url)
                                if image_response.status_code == 200:
                                    # Send image
                                    await message.channel.send(
                                        content=product_text,
                                        file=discord.File(BytesIO(image_response.content), filename='image.png')
                                    )
                                    update_user_memory(user_id, "discord", product_text, sender="ai")
                                else:
                                    await message.channel.send(response)
                                    update_user_memory(user_id, "discord", response, sender="ai")
                            except Exception as e:
                                logger.error(f"Error processing image URL for Discord: {str(e)}")
                                await message.channel.send(response)
                                update_user_memory(user_id, "discord", response, sender="ai")
                        else:
                            await message.channel.send(response)
                            update_user_memory(user_id, "discord", response, sender="ai")
                        return
            
            if message_text:
                update_user_memory(user_id, "discord", message_text, sender="user")
            
            # Get conversation history
            conversation_history = get_conversation_history(user_id, "discord")
            full_message = f"Conversation so far:\n{conversation_history}\n\nUser: {message_text}"
            
            # Process the message through your existing handler
            response, matched_product = handle_text_message(full_message, message_text)
            
            # Update memory with the response if it's not an image
            if not (" - http" in response and any(ext in response.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif'])):
                update_user_memory(user_id, "discord", response, sender="ai")
            
            # Check if response contains an image URL
            if " - http" in response and any(ext in response.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif']):
                try:
                    product_text = response.split(" - ")[0]
                    image_url = response.split(" - ")[-1].strip()
                    
                    # Download image
                    image_response = requests.get(image_url)
                    if image_response.status_code == 200:
                        # Send image
                        await message.channel.send(
                            content=product_text,
                            file=discord.File(BytesIO(image_response.content), filename='image.png')
                        )
                        update_user_memory(user_id, "discord", product_text, sender="ai")
                    else:
                        await message.channel.send(response)
                        update_user_memory(user_id, "discord", response, sender="ai")
                except Exception as e:
                    logger.error(f"Error processing image URL for Discord: {str(e)}")
                    await message.channel.send(response)
                    update_user_memory(user_id, "discord", response, sender="ai")
            else:
                await message.channel.send(response)
                update_user_memory(user_id, "discord", response, sender="ai")
                
        except Exception as e:
            logger.error(f"Error in Discord on_message: {str(e)}")
            await message.channel.send("Sorry, I encountered an error processing your message.")
            update_user_memory(user_id, "discord", "Sorry, I encountered an error processing your message.", sender="ai")

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
