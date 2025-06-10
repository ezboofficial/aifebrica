import os
import logging
from instagrapi import Client
from instagrapi.exceptions import LoginRequired
from dotenv import load_dotenv
from collections import deque
from messageHandler import handle_text_message
import requests
from io import BytesIO
import time

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD")

# User memory for conversation history
user_memory = {}

def update_user_memory(user_id, message):
    if user_id not in user_memory:
        user_memory[user_id] = deque(maxlen=20)
    user_memory[user_id].append(message)

def get_conversation_history(user_id):
    return "\n".join(user_memory.get(user_id, []))

def handle_instagram_message(cl, message):
    try:
        user_id = str(message.user_id)
        sender = message.user_id
        message_text = message.text if message.text else ""
        
        # Handle media attachments
        if message.media:
            try:
                # Get the media URL
                media_info = cl.media_info(message.media_id)
                if media_info.media_type == 1:  # Photo
                    image_url = media_info.image_versions2['candidates'][0]['url']
                    logger.info(f"Received image with URL: {image_url}")
                    
                    # Format the image URL for processing
                    formatted_image_url = f"image_url: {image_url}"
                    update_user_memory(user_id, "[User sent an image]")
                    
                    # Process the image
                    response, matched_product = handle_text_message(formatted_image_url, "[Image attachment]")
                    logger.info(f"Image processing response: {response}")
                    
                    if matched_product:
                        update_user_memory(user_id, response)
                    
                    # Send the response
                    if " - http" in response and any(ext in response.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif']):
                        try:
                            product_text = response.split(" - ")[0]
                            image_url = response.split(" - ")[-1].strip()
                            
                            # Download image
                            image_response = requests.get(image_url)
                            if image_response.status_code == 200:
                                # Send image
                                cl.direct_send_photo(
                                    file=BytesIO(image_response.content),
                                    user_ids=[sender],
                                    caption=product_text
                                )
                            else:
                                cl.direct_send(response, user_ids=[sender])
                        except Exception as e:
                            logger.error(f"Error processing image URL: {str(e)}")
                            cl.direct_send(response, user_ids=[sender])
                    else:
                        cl.direct_send(response, user_ids=[sender])
                    return
            except Exception as e:
                logger.error(f"Error processing media: {str(e)}")
                cl.direct_send("Sorry, I couldn't process that media.", user_ids=[sender])
                return
                
        # Get conversation history
        conversation_history = get_conversation_history(user_id)
        full_message = f"Conversation so far:\n{conversation_history}\n\nUser: {message_text}"
        
        # Process the message
        response, matched_product = handle_text_message(full_message, message_text)
        
        # Update memory with the response if it's not an image
        if not (" - http" in response and any(ext in response.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif'])):
            update_user_memory(user_id, response)
        
        # Check if response contains an image URL
        if " - http" in response and any(ext in response.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif']):
            try:
                product_text = response.split(" - ")[0]
                image_url = response.split(" - ")[-1].strip()
                
                # Download image
                image_response = requests.get(image_url)
                if image_response.status_code == 200:
                    # Send image
                    cl.direct_send_photo(
                        file=BytesIO(image_response.content),
                        user_ids=[sender],
                        caption=product_text
                    )
                else:
                    cl.direct_send(response, user_ids=[sender])
            except Exception as e:
                logger.error(f"Error processing image URL: {str(e)}")
                cl.direct_send(response, user_ids=[sender])
        else:
            cl.direct_send(response, user_ids=[sender])
            
    except Exception as e:
        logger.error(f"Error in handle_instagram_message: {str(e)}")
        cl.direct_send("Sorry, I encountered an error processing your message.", user_ids=[sender])

def run_instagram_bot():
    if not INSTAGRAM_USERNAME or not INSTAGRAM_PASSWORD:
        logger.error("Instagram credentials not set in environment variables")
        return
    
    cl = Client()
    try:
        # Login
        cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
        logger.info("Successfully logged in to Instagram")
        
        # Main loop
        while True:
            try:
                # Check for new messages
                threads = cl.direct_threads()
                for thread in threads:
                    if thread.messages:
                        last_message = thread.messages[0]
                        if last_message.user_id != cl.user_id:  # Only respond to user messages
                            handle_instagram_message(cl, last_message)
                
                # Sleep to avoid rate limiting
                time.sleep(10)
                
            except LoginRequired:
                logger.warning("Session expired, relogging in...")
                cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
            except Exception as e:
                logger.error(f"Error in Instagram bot main loop: {str(e)}")
                time.sleep(60)  # Wait before retrying
                
    except Exception as e:
        logger.error(f"Failed to start Instagram bot: {str(e)}")

if __name__ == '__main__':
    run_instagram_bot()
