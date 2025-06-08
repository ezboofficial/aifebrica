import os
import logging
import discord
from discord.ext import commands
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

# User memory for conversation history (same as in app.py and telegram_bot.py)
user_memory = {}

def update_user_memory(user_id, message):
    if user_id not in user_memory:
        user_memory[user_id] = deque(maxlen=20)
    user_memory[user_id].append(message)

def get_conversation_history(user_id):
    return "\n".join(user_memory.get(user_id, []))

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user.name} (ID: {bot.user.id})')
    logger.info('------')

@bot.command(name='start')
async def start(ctx):
    """Send a message when the command !start is issued."""
    await ctx.send('Hi! I am your shop assistant. How can I help you today?')

@bot.command(name='help')
async def help_command(ctx):
    """Send a message when the command !help is issued."""
    await ctx.send('I can help you with product inquiries and orders. Just send me a message!')

@bot.event
async def on_message(message):
    # Don't respond to ourselves
    if message.author == bot.user:
        return

    # Process commands first
    await bot.process_commands(message)

    # Then handle regular messages
    try:
        user_id = message.author.id
        message_text = message.content
        
        # Check for attachments (images)
        if message.attachments:
            for attachment in message.attachments:
                if attachment.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                    image_url = attachment.url
                    message_text = f"image_url: {image_url}"
                    update_user_memory(user_id, "[User sent an image]")
                    break
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
                    with BytesIO(image_response.content) as image_binary:
                        await message.channel.send(
                            content=product_text,
                            file=discord.File(image_binary, filename='product.jpg')
                        )
                else:
                    await message.channel.send(response)
            except Exception as e:
                logger.error(f"Error processing image URL: {str(e)}")
                await message.channel.send(response)
        else:
            await message.channel.send(response)
            
    except Exception as e:
        logger.error(f"Error in on_message: {str(e)}")
        await message.channel.send("Sorry, I encountered an error processing your message.")

def main():
    """Start the bot."""
    if not DISCORD_TOKEN:
        logger.error("DISCORD_TOKEN environment variable not set")
        return
    
    bot.run(DISCORD_TOKEN)

if __name__ == '__main__':
    main()
