import os
import logging
import discord
from discord.ext import commands
from messageHandler import handle_text_message
from collections import deque
from dotenv import load_dotenv
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

# User memory for conversation history
user_memory = {}

def update_user_memory(user_id, message):
    if user_id not in user_memory:
        user_memory[user_id] = deque(maxlen=20)
    user_memory[user_id].append(message)

def get_conversation_history(user_id):
    return "\n".join(user_memory.get(user_id, []))

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True  # Required to read message content
        super().__init__(command_prefix=commands.when_mentioned_or('!'), intents=intents)

    async def on_ready(self):
        logger.info(f'Logged in as {self.user} (ID: {self.user.id})')
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print('------')

    async def on_message(self, message):
        if message.author.bot:  # Ignore messages from bots
            return

        user_id = str(message.author.id)
        message_content = message.content

        # Handle image attachments
        image_processed = False
        if message.attachments:
            for attachment in message.attachments:
                if attachment.content_type.startswith('image/'):
                    image_url = attachment.url
                    update_user_memory(user_id, "[User sent an image]")
                    response, matched_product = handle_text_message(
                        f"image_url: {image_url}", 
                        "[Image attachment]"
                    )
                    await message.channel.send(response)
                    if matched_product:
                        update_user_memory(user_id, response)
                    image_processed = True
                    break # Process only the first image attachment

        if message_content and not image_processed:
            update_user_memory(user_id, message_content)
            conversation_history = get_conversation_history(user_id)
            full_message = f"Conversation so far:\n{conversation_history}\n\nUser: {message_content}"
            response, _ = handle_text_message(full_message, message_content)

            if " - http" in response and any(ext in response.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif']):
                try:
                    image_url = response.split(" - ")[-1].strip()
                    product_text = response.split(" - ")[0]

                    image_response = requests.get(image_url)
                    if image_response.status_code == 200:
                        file = discord.File(BytesIO(image_response.content), filename="image.png")
                        await message.channel.send(content=product_text, file=file)
                    else:
                        await message.channel.send(response)
                except Exception as e:
                    logger.error(f"Error processing image URL: {str(e)}")
                    await message.channel.send(response)
            else:
                await message.channel.send(response)
                update_user_memory(user_id, response)
        elif not image_processed and not message_content:
            await message.channel.send("👍")

        await self.process_commands(message)

def main():
    if not DISCORD_TOKEN:
        logger.error("DISCORD_TOKEN environment variable not set")
        return
    
    bot = MyBot()
    bot.run(DISCORD_TOKEN)

if __name__ == '__main__':
    main()
