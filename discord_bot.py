import os
import discord
from discord.ext import commands
from messageHandler import handle_text_message
from dotenv import load_dotenv
import logging
from collections import deque
import requests
from io import BytesIO

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
    logger.info(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')

@bot.event
async def on_message(message):
    # Don't respond to ourselves
    if message.author == bot.user:
        return

    try:
        user_id = str(message.author.id)
        
        # Check for attachments (images)
        if message.attachments:
            for attachment in message.attachments:
                if attachment.content_type.startswith('image/'):
                    image_url = attachment.url
                    message_text = f"image_url: {image_url}"
                    update_user_memory(user_id, "[User sent an image]")
                    break
        else:
            message_text = message.content
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
                    file = discord.File(BytesIO(image_response.content), filename="product.jpg")
                    await message.channel.send(content=product_text, file=file)
                else:
                    await message.channel.send(response)
            except Exception as e:
                logger.error(f"Error processing image URL: {str(e)}")
                await message.channel.send(response)
        else:
            await message.channel.send(response)
            
    except Exception as e:
        logger.error(f"Error in message handling: {str(e)}")
        await message.channel.send("Sorry, I encountered an error processing your message.")

def run_discord_bot():
    if not DISCORD_TOKEN:
        logger.error("DISCORD_TOKEN environment variable not set")
        return
    
    # Configure intents
    intents = discord.Intents.default()
    intents.message_content = True
    
    # Create bot instance with proper settings
    bot = commands.Bot(
        command_prefix='!',
        intents=intents,
        help_command=None  # Disable default help command
    )
    
    # Add event handlers
    bot.event(on_ready)
    bot.event(on_message)
    
    try:
        bot.run(DISCORD_TOKEN)
    except Exception as e:
        logger.error(f"Discord bot error: {str(e)}")
        raise

if __name__ == '__main__':
    run_discord_bot()
