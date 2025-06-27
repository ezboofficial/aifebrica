# page_bot.py
import os
import logging
import requests
from dotenv import load_dotenv
from messageHandler import handle_text_message
from memory_manager import update_user_memory, get_conversation_history

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
            return True
        else:
            # Skip logging for "No matching user found" error
            error_data = response.json()
            if not (response.status_code == 400 and 
                   error_data.get("error", {}).get("code") == 100 and 
                   error_data.get("error", {}).get("error_subcode") == 2018001):
                logger.error(f"Failed to send message: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error sending message: {str(e)}")
        return False

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
            return True
        else:
            # Skip logging for "No matching user found" error
            error_data = response.json()
            if not (response.status_code == 400 and 
                   error_data.get("error", {}).get("code") == 100 and 
                   error_data.get("error", {}).get("error_subcode") == 2018001):
                logger.error(f"Failed to send image: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error sending image: {str(e)}")
        return False

def handle_facebook_message(data):
    logger.info("Received data: %s", data)

    if data.get("object") == "page":
        for entry in data["entry"]:
            for event in entry.get("messaging", []):
                if "message" in event:
                    sender_id = event["sender"]["id"]
                    message_text = event["message"].get("text")
                    message_attachments = event["message"].get("attachments")
                    
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
                                    if send_message(sender_id, "👍"):
                                        update_user_memory(sender_id, "facebook", "👍", sender="ai")
                                    continue

                    if is_thumbs_up:
                        continue

                    image_processed = False
                    if message_attachments:
                        for attachment in message_attachments:
                            if attachment.get("type") == "image" and not is_thumbs_up:
                                image_url = attachment["payload"].get("url")
                                if image_url:
                                    update_user_memory(sender_id, "facebook", "[User sent an image]", sender="user")
                                    response, matched_product = handle_text_message(
                                        f"image_url: {image_url}", 
                                        "[Image attachment]"
                                    )
                                    if send_message(sender_id, response):
                                        update_user_memory(sender_id, "facebook", response, sender="ai")
                                    if matched_product:
                                        update_user_memory(sender_id, "facebook", response, sender="ai")
                                    image_processed = True
                    
                    if message_text and not image_processed:
                        update_user_memory(sender_id, "facebook", message_text, sender="user")
                        conversation_history = get_conversation_history(sender_id, "facebook")
                        full_message = f"Conversation so far:\n{conversation_history}\n\nUser: {message_text}"
                        response, _ = handle_text_message(full_message, message_text)
                        
                        if " - http" in response and any(ext in response.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif']):
                            try:
                                image_url = response.split(" - ")[-1].strip()
                                if image_url.startswith(('http://', 'https://')):
                                    if send_image(sender_id, image_url):
                                        product_text = response.split(" - ")[0]
                                        if product_text:
                                            if send_message(sender_id, product_text):
                                                update_user_memory(sender_id, "facebook", product_text, sender="ai")
                            except Exception as e:
                                logger.error(f"Error processing image URL: {str(e)}")
                                if send_message(sender_id, response):
                                    update_user_memory(sender_id, "facebook", response, sender="ai")
                        else:
                            if send_message(sender_id, response):
                                update_user_memory(sender_id, "facebook", response, sender="ai")
                    elif not image_processed:
                        if send_message(sender_id, "👍"):
                            update_user_memory(sender_id, "facebook", "👍", sender="ai")

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
