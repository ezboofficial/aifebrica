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

# Track processed message IDs to prevent duplicates
processed_messages = set()

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

def send_image(recipient_id, image_url, caption=None):
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
            if caption:
                send_message(recipient_id, caption)
        else:
            error_data = response.json()
            if not (response.status_code == 400 and 
                   error_data.get("error", {}).get("code") == 100 and 
                   error_data.get("error", {}).get("error_subcode") == 2018001):
                logger.error(f"Failed to send image: {response.text}")
    except Exception as e:
        logger.error(f"Error sending image: {str(e)}")

def handle_facebook_message(data):
    if data.get("object") != "page":
        return

    for entry in data["entry"]:
        for event in entry.get("messaging", []):
            if "message" not in event:
                continue

            message = event["message"]
            message_id = message.get("mid")
            sender_id = event["sender"]["id"]

            # Skip if we've already processed this message
            if message_id in processed_messages:
                logger.info(f"Skipping already processed message: {message_id}")
                continue

            # Add to processed messages
            processed_messages.add(message_id)
            logger.info(f"Processing new message: {message_id}")

            # Handle thumbs up reaction
            if message.get("sticker_id") == "369239263222822":
                send_message(sender_id, "👍")
                continue

            # Handle image attachments
            attachments = message.get("attachments", [])
            if attachments and attachments[0].get("type") == "image":
                image_url = attachments[0]["payload"].get("url")
                if image_url:
                    response, _ = handle_text_message(f"image_url: {image_url}", "[Image attachment]")
                    if " - http" in response:
                        parts = response.split(" - ")
                        if len(parts) > 1:
                            product_text = parts[0]
                            image_url = parts[-1].strip()
                            send_image(sender_id, image_url, product_text)
                    else:
                        send_message(sender_id, response)
                    continue

            # Handle text messages
            text = message.get("text", "").strip()
            if text:
                response, _ = handle_text_message(text, None)
                if " - http" in response:
                    parts = response.split(" - ")
                    if len(parts) > 1:
                        product_text = parts[0]
                        image_url = parts[-1].strip()
                        send_image(sender_id, image_url, product_text)
                else:
                    send_message(sender_id, response)

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
