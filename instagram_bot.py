import os
import logging
import requests
from messageHandler import handle_text_message
from dotenv import load_dotenv
from collections import deque

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Instagram API credentials
INSTAGRAM_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN")
INSTAGRAM_VERIFY_TOKEN = os.getenv("INSTAGRAM_VERIFY_TOKEN")

# User memory for conversation history
user_memory = {}

def update_user_memory(user_id, message):
    """Update user conversation memory."""
    if user_id not in user_memory:
        user_memory[user_id] = deque(maxlen=20)
    user_memory[user_id].append(message)

def get_conversation_history(user_id):
    """Get conversation history for a user."""
    return "\n".join(user_memory.get(user_id, []))

def verify_webhook(verify_token, challenge):
    """Verify webhook for Instagram."""
    if verify_token == INSTAGRAM_VERIFY_TOKEN:
        logger.info("Instagram webhook verification successful.")
        return challenge
    logger.error("Instagram webhook verification failed: invalid verify token.")
    return None

def send_message(recipient_id, message_text):
    """Send a text message to an Instagram user."""
    if not INSTAGRAM_ACCESS_TOKEN:
        logger.error("Instagram access token not configured")
        return False
    
    url = f"https://graph.facebook.com/v21.0/me/messages"
    headers = {
        "Content-Type": "application/json"
    }
    params = {
        "access_token": INSTAGRAM_ACCESS_TOKEN
    }
    data = {
        "recipient": {"id": recipient_id},
        "message": {"text": message_text}
    }
    
    try:
        response = requests.post(url, headers=headers, params=params, json=data)
        if response.status_code == 200:
            logger.info(f"Instagram message sent to {recipient_id}")
            return True
        else:
            logger.error(f"Failed to send Instagram message: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error sending Instagram message: {str(e)}")
        return False

def send_image(recipient_id, image_url):
    """Send an image to an Instagram user."""
    if not INSTAGRAM_ACCESS_TOKEN:
        logger.error("Instagram access token not configured")
        return False
    
    url = f"https://graph.facebook.com/v21.0/me/messages"
    headers = {
        "Content-Type": "application/json"
    }
    params = {
        "access_token": INSTAGRAM_ACCESS_TOKEN
    }
    data = {
        "recipient": {"id": recipient_id},
        "message": {
            "attachment": {
                "type": "image",
                "payload": {
                    "url": image_url,
                    "is_reusable": True
                }
            }
        }
    }
    
    try:
        response = requests.post(url, headers=headers, params=params, json=data)
        if response.status_code == 200:
            logger.info(f"Instagram image sent to {recipient_id}")
            return True
        else:
            logger.error(f"Failed to send Instagram image: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error sending Instagram image: {str(e)}")
        return False

def handle_instagram_message(sender_id, message_text=None, attachments=None):
    """Handle incoming Instagram message."""
    try:
        # Handle image attachments
        if attachments:
            for attachment in attachments:
                if attachment.get("type") == "image":
                    image_url = attachment.get("payload", {}).get("url")
                    if image_url:
                        update_user_memory(sender_id, "[User sent an image]")
                        response, matched_product = handle_text_message(
                            f"image_url: {image_url}", 
                            "[Image attachment]"
                        )
                        
                        if matched_product:
                            update_user_memory(sender_id, response)
                        
                        # Send response
                        if " - http" in response and any(ext in response.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif']):
                            try:
                                product_text = response.split(" - ")[0]
                                image_url = response.split(" - ")[-1].strip()
                                
                                if image_url.startswith(('http://', 'https://')):
                                    send_image(sender_id, image_url)
                                    if product_text:
                                        send_message(sender_id, product_text)
                                        update_user_memory(sender_id, product_text)
                                else:
                                    send_message(sender_id, response)
                                    update_user_memory(sender_id, response)
                            except Exception as e:
                                logger.error(f"Error processing image URL: {str(e)}")
                                send_message(sender_id, response)
                                update_user_memory(sender_id, response)
                        else:
                            send_message(sender_id, response)
                            update_user_memory(sender_id, response)
                        return
        
        # Handle text messages
        if message_text:
            update_user_memory(sender_id, message_text)
            conversation_history = get_conversation_history(sender_id)
            full_message = f"Conversation so far:\n{conversation_history}\n\nUser: {message_text}"
            
            response, matched_product = handle_text_message(full_message, message_text)
            
            # Send response
            if " - http" in response and any(ext in response.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif']):
                try:
                    product_text = response.split(" - ")[0]
                    image_url = response.split(" - ")[-1].strip()
                    
                    if image_url.startswith(('http://', 'https://')):
                        send_image(sender_id, image_url)
                        if product_text:
                            send_message(sender_id, product_text)
                            update_user_memory(sender_id, product_text)
                    else:
                        send_message(sender_id, response)
                        update_user_memory(sender_id, response)
                except Exception as e:
                    logger.error(f"Error processing image URL: {str(e)}")
                    send_message(sender_id, response)
                    update_user_memory(sender_id, response)
            else:
                send_message(sender_id, response)
                update_user_memory(sender_id, response)
        
    except Exception as e:
        logger.error(f"Error handling Instagram message: {str(e)}")
        send_message(sender_id, "Sorry, I encountered an error processing your message.")

def process_instagram_webhook(data):
    """Process Instagram webhook data."""
    try:
        if data.get("object") == "instagram":
            for entry in data.get("entry", []):
                for messaging_event in entry.get("messaging", []):
                    if "message" in messaging_event:
                        sender_id = messaging_event["sender"]["id"]
                        message = messaging_event["message"]
                        
                        message_text = message.get("text")
                        attachments = message.get("attachments")
                        
                        handle_instagram_message(sender_id, message_text, attachments)
                        
    except Exception as e:
        logger.error(f"Error processing Instagram webhook: {str(e)}")

if __name__ == '__main__':
    logger.info("Instagram bot module loaded")
