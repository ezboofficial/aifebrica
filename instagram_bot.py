import os
import logging
import requests
from dotenv import load_dotenv
from messageHandler import handle_text_message
from collections import deque

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Instagram API credentials
INSTAGRAM_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN")
INSTAGRAM_BUSINESS_ACCOUNT_ID = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID")
INSTAGRAM_APP_ID = os.getenv("INSTAGRAM_APP_ID")
INSTAGRAM_APP_SECRET = os.getenv("INSTAGRAM_APP_SECRET")

# User memory for conversation history
user_memory = {}

def update_user_memory(user_id, message):
    if user_id not in user_memory:
        user_memory[user_id] = deque(maxlen=20)
    user_memory[user_id].append(message)

def get_conversation_history(user_id):
    return "\n".join(user_memory.get(user_id, []))

def send_message(recipient_id, message):
    """Send a text message to an Instagram user"""
    url = f"https://graph.facebook.com/v18.0/{INSTAGRAM_BUSINESS_ACCOUNT_ID}/messages"
    
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": message},
        "messaging_type": "RESPONSE",
        "access_token": INSTAGRAM_ACCESS_TOKEN
    }
    
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            logger.info(f"Message sent to Instagram user {recipient_id}")
        else:
            logger.error(f"Failed to send Instagram message: {response.text}")
    except Exception as e:
        logger.error(f"Error sending Instagram message: {str(e)}")

def send_image(recipient_id, image_url):
    """Send an image to an Instagram user"""
    url = f"https://graph.facebook.com/v18.0/{INSTAGRAM_BUSINESS_ACCOUNT_ID}/messages"
    
    payload = {
        "recipient": {"id": recipient_id},
        "message": {
            "attachment": {
                "type": "image",
                "payload": {
                    "url": image_url,
                    "is_reusable": True
                }
            }
        },
        "messaging_type": "RESPONSE",
        "access_token": INSTAGRAM_ACCESS_TOKEN
    }
    
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            logger.info(f"Image sent to Instagram user {recipient_id}")
        else:
            logger.error(f"Failed to send Instagram image: {response.text}")
    except Exception as e:
        logger.error(f"Error sending Instagram image: {str(e)}")

def handle_instagram_message(data):
    """Process incoming Instagram messages"""
    for entry in data.get('entry', []):
        for messaging_event in entry.get('messaging', []):
            sender_id = messaging_event['sender']['id']
            
            if 'message' in messaging_event:
                message = messaging_event['message']
                
                # Handle text messages
                if 'text' in message:
                    message_text = message['text']
                    update_user_memory(sender_id, message_text)
                    
                    # Get conversation history
                    conversation_history = get_conversation_history(sender_id)
                    full_message = f"Conversation so far:\n{conversation_history}\n\nUser: {message_text}"
                    
                    # Process the message through your existing handler
                    response, matched_product = handle_text_message(full_message, message_text)
                    
                    # Update memory with the response if it's not an image
                    if not (" - http" in response and any(ext in response.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif'])):
                        update_user_memory(sender_id, response)
                    
                    # Check if response contains an image URL
                    if " - http" in response and any(ext in response.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif']):
                        try:
                            image_url = response.split(" - ")[-1].strip()
                            product_text = response.split(" - ")[0]
                            
                            # Send the image
                            send_image(sender_id, image_url)
                            
                            # Send the product text if available
                            if product_text:
                                send_message(sender_id, product_text)
                        except Exception as e:
                            logger.error(f"Error processing image URL for Instagram: {str(e)}")
                            send_message(sender_id, response)
                    else:
                        send_message(sender_id, response)
                
                # Handle image attachments
                elif 'attachments' in message:
                    for attachment in message['attachments']:
                        if attachment['type'] == 'image':
                            image_url = attachment['payload']['url']
                            update_user_memory(sender_id, "[User sent an image]")
                            
                            # Process the image
                            response, matched_product = handle_text_message(
                                f"image_url: {image_url}", 
                                "[Image attachment]"
                            )
                            
                            if matched_product:
                                update_user_memory(sender_id, response)
                            
                            # Send the response
                            if " - http" in response and any(ext in response.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif']):
                                try:
                                    image_url = response.split(" - ")[-1].strip()
                                    product_text = response.split(" - ")[0]
                                    
                                    # Send the image
                                    send_image(sender_id, image_url)
                                    
                                    # Send the product text if available
                                    if product_text:
                                        send_message(sender_id, product_text)
                                except Exception as e:
                                    logger.error(f"Error processing image URL for Instagram: {str(e)}")
                                    send_message(sender_id, response)
                            else:
                                send_message(sender_id, response)

def verify_instagram_webhook(request):
    """Verify Instagram webhook subscription"""
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    
    if mode and token:
        if mode == 'subscribe' and token == os.getenv("VERIFY_TOKEN"):
            logger.info("Instagram webhook verified successfully")
            return challenge, 200
    
    logger.error("Instagram webhook verification failed")
    return "Verification failed", 403
