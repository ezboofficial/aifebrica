import os
import logging
import requests
from collections import deque
from messageHandler import handle_text_message
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import threading

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

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
    """Send a message to an Instagram user"""
    url = f"https://graph.facebook.com/v18.0/{INSTAGRAM_BUSINESS_ACCOUNT_ID}/messages"
    params = {
        "access_token": INSTAGRAM_ACCESS_TOKEN
    }
    headers = {
        "Content-Type": "application/json"
    }
    data = {
        "recipient": {"id": recipient_id},
        "messaging_type": "RESPONSE",
        "message": {"text": message}
    }
    
    try:
        response = requests.post(url, params=params, headers=headers, json=data)
        response.raise_for_status()
        logger.info(f"Message sent to Instagram user {recipient_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to send Instagram message: {str(e)}")
        return False

def send_image(recipient_id, image_url):
    """Send an image to an Instagram user"""
    url = f"https://graph.facebook.com/v18.0/{INSTAGRAM_BUSINESS_ACCOUNT_ID}/messages"
    params = {
        "access_token": INSTAGRAM_ACCESS_TOKEN
    }
    headers = {
        "Content-Type": "application/json"
    }
    data = {
        "recipient": {"id": recipient_id},
        "messaging_type": "RESPONSE",
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
        response = requests.post(url, params=params, headers=headers, json=data)
        response.raise_for_status()
        logger.info(f"Image sent to Instagram user {recipient_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to send Instagram image: {str(e)}")
        return False

def handle_instagram_message(sender_id, message_text, attachments=None):
    """Process incoming Instagram messages"""
    try:
        # Handle image attachments
        if attachments and 'image' in attachments.get('type', ''):
            image_url = attachments.get('payload', {}).get('url', '')
            if image_url:
                update_user_memory(sender_id, "[User sent an image]")
                response, matched_product = handle_text_message(f"image_url: {image_url}", "[Image attachment]")
                
                if matched_product:
                    update_user_memory(sender_id, response)
                
                # Check if response contains an image URL
                if " - http" in response and any(ext in response.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif']):
                    try:
                        image_url = response.split(" - ")[-1].strip()
                        product_text = response.split(" - ")[0]
                        send_image(sender_id, image_url)
                        send_message(sender_id, product_text)
                    except Exception as e:
                        logger.error(f"Error processing image URL: {str(e)}")
                        send_message(sender_id, response)
                else:
                    send_message(sender_id, response)
                return
        
        # Update memory with the new message
        update_user_memory(sender_id, message_text)
        
        # Get conversation history
        conversation_history = get_conversation_history(sender_id)
        full_message = f"Conversation so far:\n{conversation_history}\n\nUser: {message_text}"
        
        # Process the message
        response, matched_product = handle_text_message(full_message, message_text)
        
        # Check if response contains an image URL
        if " - http" in response and any(ext in response.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif']):
            try:
                image_url = response.split(" - ")[-1].strip()
                product_text = response.split(" - ")[0]
                send_image(sender_id, image_url)
                send_message(sender_id, product_text)
            except Exception as e:
                logger.error(f"Error processing image URL: {str(e)}")
                send_message(sender_id, response)
        else:
            send_message(sender_id, response)
            
    except Exception as e:
        logger.error(f"Error handling Instagram message: {str(e)}")
        send_message(sender_id, "Sorry, I encountered an error processing your message.")

def create_instagram_app():
    """Create Flask app for Instagram webhooks"""
    app = Flask(__name__)
    
    @app.route('/instagram/webhook', methods=['GET'])
    def verify_webhook():
        # Instagram webhook verification
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        
        if mode == 'subscribe' and token == os.getenv("INSTAGRAM_VERIFY_TOKEN"):
            logger.info("Instagram webhook verified successfully")
            return challenge, 200
        return "Verification failed", 403
    
    @app.route('/instagram/webhook', methods=['POST'])
    def webhook():
        data = request.get_json()
        logger.info(f"Received Instagram webhook data: {data}")
        
        if data.get('object') == 'instagram':
            for entry in data.get('entry', []):
                for messaging in entry.get('messaging', []):
                    sender_id = messaging.get('sender', {}).get('id')
                    message = messaging.get('message')
                    
                    if message:
                        message_text = message.get('text')
                        attachments = message.get('attachments', [{}])[0] if message.get('attachments') else None
                        
                        # Skip echo messages (messages sent by your own bot)
                        if message.get('is_echo'):
                            logger.info("Skipping echo message")
                            continue
                            
                        if message_text or attachments:
                            handle_instagram_message(sender_id, message_text or '', attachments)
        
        return "EVENT_RECEIVED", 200
    
    return app

def run_instagram_bot():
    """Run the Instagram bot"""
    if not all([INSTAGRAM_ACCESS_TOKEN, INSTAGRAM_BUSINESS_ACCOUNT_ID]):
        logger.error("Instagram configuration missing")
        return
    
    app = create_instagram_app()
    app.run(port=5001)  # Run on a different port than your main Flask app

if __name__ == '__main__':
    run_instagram_bot()
