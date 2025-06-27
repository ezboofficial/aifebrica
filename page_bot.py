# page_bot.py
import os
import logging
import requests
from collections import deque
from dotenv import load_dotenv
from messageHandler import handle_text_message

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")

# User memory for conversation history and last message tracking
user_memory = {}
last_user_message = {}  # {user_id: last_message_text}

def update_user_memory(user_id, message):
    if user_id not in user_memory:
        user_memory[user_id] = deque(maxlen=20)
    user_memory[user_id].append(message)

def get_conversation_history(user_id):
    return "\n".join(user_memory.get(user_id, []))

def send_message(recipient_id, message=None):
    params = {"access_token": PAGE_ACCESS_TOKEN}
    headers = {"Content-Type": "application/json"}
    
    if not isinstance(message, str):
        message = str(message) if message else "An error occurred while processing your request."
    
    data = {
        "recipient": {"id": recipient_id},
        "message": {"text": message},
    }

    try:
        response = requests.post(
            "https://graph.facebook.com/v21.0/me/messages",
            params=params,
            headers=headers,
            json=data
        )
        if response.status_code == 200:
            logger.info(f"Message sent to {recipient_id}")
        else:
            error_data = response.json()
            if not (response.status_code == 400 and 
                   error_data.get("error", {}).get("code") == 100 and 
                   error_data.get("error", {}).get("error_subcode") == 2018001):
                logger.error(f"Failed to send message: {response.text}")
    except Exception as e:
        logger.error(f"Error sending message: {str(e)}")

def send_image(recipient_id, image_url):
    params = {"access_token": PAGE_ACCESS_TOKEN}
    headers = {"Content-Type": "application/json"}
    
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
        response = requests.post(
            "https://graph.facebook.com/v21.0/me/messages",
            params=params,
            headers=headers,
            json=data
        )
        if response.status_code == 200:
            logger.info(f"Image sent to {recipient_id}")
        else:
            error_data = response.json()
            if not (response.status_code == 400 and 
                   error_data.get("error", {}).get("code") == 100 and 
                   error_data.get("error", {}).get("error_subcode") == 2018001):
                logger.error(f"Failed to send image: {response.text}")
    except Exception as e:
        logger.error(f"Error sending image: {str(e)}")

def handle_facebook_message(data):
    logger.info("Received data: %s", data)

    if data.get("object") == "page":
        for entry in data["entry"]:
            for event in entry.get("messaging", []):
                if "message" in event:
                    sender_id = event["sender"]["id"]
                    message_text = event["message"].get("text")
                    message_attachments = event["message"].get("attachments")
                    
                    # Skip if this is the same message as last time from this user
                    if sender_id in last_user_message and message_text == last_user_message[sender_id]:
                        logger.info(f"Skipping duplicate message from user {sender_id}")
                        continue
                    
                    # Update last message
                    if message_text:
                        last_user_message[sender_id] = message_text
                    
                    is_thumbs_up = False
                    if message_attachments:
                        for attachment in message_attachments:
                            if attachment.get("type") == "image":
                                payload = attachment.get("payload", {})
                                sticker_id = payload.get("sticker_id")
                                image_url = payload.get("url", "")
                                
                                if (sticker_id == "369239263222822" or 
                                    "39178562_1505197616293642_5411344281094848512_n.png" in image_url):
                                    is_thumbs_up = True
                                    send_message(sender_id, "👍")
                                    continue

                    if is_thumbs_up:
                        continue

                    image_processed = False
                    if message_attachments:
                        for attachment in message_attachments:
                            if attachment.get("type") == "image" and not is_thumbs_up:
                                image_url = attachment["payload"].get("url")
                                if image_url:
                                    update_user_memory(sender_id, "[User sent an image]")
                                    response, matched_product = handle_text_message(
                                        f"image_url: {image_url}", 
                                        "[Image attachment]"
                                    )
                                    send_message(sender_id, response)
                                    if matched_product:
                                        update_user_memory(sender_id, response)
                                    image_processed = True
                    
                    if message_text and not image_processed:
                        update_user_memory(sender_id, message_text)
                        conversation_history = get_conversation_history(sender_id)
                        full_message = f"Conversation so far:\n{conversation_history}\n\nUser: {message_text}"
                        response, _ = handle_text_message(full_message, message_text)
                        
                        if " - http" in response and any(ext in response.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif']):
                            try:
                                image_url = response.split(" - ")[-1].strip()
                                if image_url.startswith(('http://', 'https://')):
                                    send_image(sender_id, image_url)
                                    product_text = response.split(" - ")[0]
                                    if product_text:
                                        send_message(sender_id, product_text)
                                        update_user_memory(sender_id, product_text)
                            except Exception as e:
                                logger.error(f"Error processing image URL: {str(e)}")
                                send_message(sender_id, response)
                                update_user_memory(sender_id, response)
                        else:
                            send_message(sender_id, response)
                            update_user_memory(sender_id, response)
                    elif not image_processed:
                        send_message(sender_id, "👍")

def verify_webhook(token_sent):
    if token_sent == VERIFY_TOKEN:
        logger.info("Webhook verification successful.")
        return True
    logger.error("Webhook verification failed: invalid verify token.")
    return False

def run_page_bot():
    if not PAGE_ACCESS_TOKEN or not VERIFY_TOKEN:
        logger.error("Missing required environment variables (PAGE_ACCESS_TOKEN or VERIFY_TOKEN)")
        return
    
    logger.info("Facebook Page bot is ready to process messages")

if __name__ == '__main__':
    run_page_bot()
