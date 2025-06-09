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
                        update_user_memory(user_id, "[User sent an image]")
                        
                        # Process the image through your existing handler
                        response, matched_product = handle_text_message(message_text, "[Image attachment]")
                        
                        if matched_product:
                            # Format the response exactly like Facebook
                            response = (
                                f"I found a similar product in our catalog ({(matched_product[1]*100):.1f}% match):\n"
                                f"{matched_product[0]['type']} ({matched_product[0]['category']})\n"
                                f"Sizes: {', '.join(matched_product[0]['size'])}\n"
                                f"Colors: {', '.join(matched_product[0]['color'])}\n"
                                f"Price: {matched_product[0]['price']}{settings['currency']}\n"
                                f"Image: {matched_product[0]['image']}"
                            )
                            update_user_memory(user_id, response)
                            
                            # Check if response contains an image URL
                            if matched_product[0]['image']:
                                try:
                                    image_response = requests.get(matched_product[0]['image'])
                                    if image_response.status_code == 200:
                                        # Send image with product details
                                        await message.channel.send(
                                            content=(
                                                f"I found a similar product in our catalog ({(matched_product[1]*100):.1f}% match):\n"
                                                f"{matched_product[0]['type']} ({matched_product[0]['category']})\n"
                                                f"Sizes: {', '.join(matched_product[0]['size'])}\n"
                                                f"Colors: {', '.join(matched_product[0]['color'])}\n"
                                                f"Price: {matched_product[0]['price']}{settings['currency']}"
                                            ),
                                            file=discord.File(BytesIO(image_response.content), 'product.png')
                                        )
                                        return
                                except Exception as e:
                                    logger.error(f"Error processing product image: {str(e)}")
                            
                            await message.channel.send(response)
                            return
                        else:
                            response = "No Match Found!!\n\n- I couldn't find anything matching in our catalog.\n- To help me assist you, please follow these steps:\n\n 1. Visit our Facebook page.\n 2. Download an image of the product you need.\n 3. Send it to me directly.\n\n- You can also describe what you're looking for, I can then show you your needed product with an image."
                            await message.channel.send(response)
                            return
            
            # For text messages
            if message_text:
                update_user_memory(user_id, message_text)
                
                # Get conversation history
                conversation_history = get_conversation_history(user_id)
                full_message = f"Conversation so far:\n{conversation_history}\n\nUser: {message_text}"
                
                # Process the message through your existing handler
                response, matched_product = handle_text_message(full_message, message_text)
                
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
                            await message.channel.send(
                                product_text, 
                                file=discord.File(BytesIO(image_response.content), 'product.png')
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
