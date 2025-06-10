import os
import logging
from dotenv import load_dotenv
from messageHandler import handle_text_message
from collections import deque
import requests
import json
from threading import Thread

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

INSTAGRAM_BUSINESS_ACCOUNT_ID = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID")
INSTAGRAM_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN")

# User memory for conversation history
user_memory = {}

def update_user_memory(user_id, message):
    if user_id not in user_memory:
        user_memory[user_id] = deque(maxlen=20)
    user_memory[user_id].append(message)

def get_conversation_history(user_id):
    return "\n".join(user_memory.get(user_id, []))

def send_message(recipient_id, message):
    """Send a message via Instagram Graph API"""
    url = f"https://graph.facebook.com/v18.0/{INSTAGRAM_BUSINESS_ACCOUNT_ID}/messages"
    params = {
        "access_token": INSTAGRAM_ACCESS_TOKEN,
        "recipient": json.dumps({"id": recipient_id}),
        "message": json.dumps({"text": message})
    }
    
    try:
        response = requests.post(url, params=params)
        if response.status_code == 200:
            logger.info(f"Message sent to Instagram user {recipient_id}")
        else:
            logger.error(f"Failed to send Instagram message: {response.text}")
    except Exception as e:
        logger.error(f"Error sending Instagram message: {str(e)}")

def send_image(recipient_id, image_url):
    """Send an image via Instagram Graph API"""
    url = f"https://graph.facebook.com/v18.0/{INSTAGRAM_BUSINESS_ACCOUNT_ID}/messages"
    params = {
        "access_token": INSTAGRAM_ACCESS_TOKEN,
        "recipient": json.dumps({"id": recipient_id}),
        "message": json.dumps({
            "attachment": {
                "type": "image",
                "payload": {
                    "url": image_url,
                    "is_reusable": True
                }
            }
        })
    }
    
    try:
        response = requests.post(url, params=params)
        if response.status_code == 200:
            logger.info(f"Image sent to Instagram user {recipient_id}")
        else:
            logger.error(f"Failed to send Instagram image: {response.text}")
    except Exception as e:
        logger.error(f"Error sending Instagram image: {str(e)}")

def handle_instagram_message(user_id, message_text, message_attachments=None):
    """Process incoming Instagram messages"""
    try:
        # Handle image attachments
        if message_attachments:
            for attachment in message_attachments:
                if attachment.get("type") == "image":
                    image_url = attachment["payload"].get("url")
                    if image_url:
                        update_user_memory(user_id, "[User sent an image]")
                        response, matched_product = handle_text_message(
                            f"image_url: {image_url}", 
                            "[Image attachment]"
                        )
                        if matched_product:
                            update_user_memory(user_id, response)
                        
                        if " - http" in response and any(ext in response.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif']):
                            try:
                                product_text = response.split(" - ")[0]
                                image_url = response.split(" - ")[-1].strip()
                                send_message(user_id, product_text)
                                send_image(user_id, image_url)
                            except Exception as e:
                                logger.error(f"Error processing image URL for Instagram: {str(e)}")
                                send_message(user_id, response)
                        else:
                            send_message(user_id, response)
                        return
        
        # Handle text messages
        if message_text:
            update_user_memory(user_id, message_text)
            conversation_history = get_conversation_history(user_id)
            full_message = f"Conversation so far:\n{conversation_history}\n\nUser: {message_text}"
            response, _ = handle_text_message(full_message, message_text)
            
            if " - http" in response and any(ext in response.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif']):
                try:
                    product_text = response.split(" - ")[0]
                    image_url = response.split(" - ")[-1].strip()
                    send_message(user_id, product_text)
                    send_image(user_id, image_url)
                except Exception as e:
                    logger.error(f"Error processing image URL for Instagram: {str(e)}")
                    send_message(user_id, response)
            else:
                send_message(user_id, response)
                
    except Exception as e:
        logger.error(f"Error handling Instagram message: {str(e)}")
        send_message(user_id, "Sorry, I encountered an error processing your message.")

def setup_instagram_webhook():
    """Set up Instagram webhook for receiving messages"""
    # This would be called during app initialization
    # You'll need to implement the webhook verification and handling
    pass

def run_instagram_bot():
    """Main function to run Instagram bot"""
    if not INSTAGRAM_BUSINESS_ACCOUNT_ID or not INSTAGRAM_ACCESS_TOKEN:
        logger.error("Instagram credentials not configured")
        return
    
    # In a real implementation, you would set up a webhook here
    # For this example, we'll just log that the bot is ready
    logger.info("Instagram bot is ready to receive messages via webhook")

if __name__ == '__main__':
    run_instagram_bot()
