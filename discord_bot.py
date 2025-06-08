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
DISCORD_ADMIN_ID = os.getenv("DISCORD_ADMIN_ID")

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
        
        # Notify admin when bot comes online
        if DISCORD_ADMIN_ID:
            try:
                admin = await self.fetch_user(int(DISCORD_ADMIN_ID))
                await admin.send("🟢 Bot is now online and ready!")
            except Exception as e:
                logger.error(f"Failed to notify admin: {str(e)}")

    async def on_message(self, message):
        # Don't respond to ourselves or other bots
        if message.author == self.user or message.author.bot:
            return

        # Simple command handling
        if message.content.startswith('!'):
            await self.process_commands(message)
            return

        try:
            user_id = str(message.author.id)
            message_text = message.content
            
            # Handle image attachments
            image_processed = False
            if message.attachments:
                for attachment in message.attachments:
                    if 'image' in attachment.content_type:
                        # Use URL for reliable access
                        image_url = attachment.url
                        message_text = f"image_url: {image_url}"
                        update_user_memory(user_id, "[User sent an image]")
                        image_processed = True
                        break  # Process only the first image
            
            if not image_processed and message_text:
                update_user_memory(user_id, message_text)
            
            # Get conversation history
            conversation_history = get_conversation_history(user_id)
            full_message = f"Conversation so far:\n{conversation_history}\n\nUser: {message_text}"
            
            # Process the message through handler
            response, matched_product = handle_text_message(full_message, message_text)
            
            # Only update memory for non-image responses
            if matched_product is None:
                update_user_memory(user_id, response)
            
            # Check if response contains an image URL in standard format
            if " - http" in response and any(ext in response.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif']):
                try:
                    # Split response into product text and image URL
                    parts = response.split(" - ")
                    product_text = " - ".join(parts[:-1]).strip()
                    image_url = parts[-1].strip()
                    
                    # Download and send image with caption
                    image_response = requests.get(image_url)
                    if image_response.status_code == 200:
                        await message.channel.send(
                            content=product_text,
                            file=discord.File(
                                BytesIO(image_response.content),
                                filename='product_image.png'
                            )
                        )
                    else:
                        await message.channel.send(response)
                except Exception as e:
                    logger.error(f"Error processing image URL: {str(e)}")
                    await message.channel.send(response)
            else:
                # Send regular text response
                await message.channel.send(response)
                
        except Exception as e:
            logger.error(f"Error in on_message: {str(e)}")
            error_msg = "⚠️ Sorry, I encountered an error processing your message. Please try again."
            await message.channel.send(error_msg)
            
            # Notify admin about the error
            if DISCORD_ADMIN_ID:
                try:
                    admin = await self.fetch_user(int(DISCORD_ADMIN_ID))
                    await admin.send(f"❌ Error in channel {message.channel.id}:\n```{str(e)}```")
                except Exception as admin_error:
                    logger.error(f"Failed to notify admin: {str(admin_error)}")

    async def on_error(self, event_method, *args, **kwargs):
        """Handle errors in event handlers."""
        logger.error(f"Error in {event_method}: {str(sys.exc_info()[1])}")
        
        # Notify admin about the error
        if DISCORD_ADMIN_ID:
            try:
                admin = await self.fetch_user(int(DISCORD_ADMIN_ID))
                await admin.send(f"❌ Error in {event_method}:\n```{str(sys.exc_info()[1])}```")
            except Exception as e:
                logger.error(f"Failed to notify admin: {str(e)}")

def run_discord_bot():
    """Start the Discord bot."""
    if not DISCORD_TOKEN:
        logger.error("DISCORD_TOKEN environment variable not set")
        return
    
    bot = DiscordBot()
    
    # Add commands
    @bot.command(name='help')
    async def help_command(ctx):
        """Show help information"""
        help_text = """
**Shop Bot Commands:**
`!help` - Show this help message

**How to use:**
- Send a message describing what you're looking for
- Send an image of a product for identification
- The bot will help you find products and place orders
"""
        await ctx.send(help_text)

    try:
        logger.info("Starting Discord bot...")
        bot.run(DISCORD_TOKEN)
    except discord.LoginFailure:
        logger.error("Discord bot failed to log in. Check your token.")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")

if __name__ == '__main__':
    run_discord_bot()
