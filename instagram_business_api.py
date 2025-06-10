import requests
import logging
from dotenv import load_dotenv
import os

load_dotenv()

class InstagramBusinessApi:
    def __init__(self, access_token=None):
        self.access_token = access_token or os.getenv("INSTAGRAM_ACCESS_TOKEN")
        self.base_url = "https://graph.facebook.com/v21.0"
        self.logger = logging.getLogger(__name__)
        
    def send_message(self, recipient_id, message):
        """Send a text message to an Instagram user"""
        url = f"{self.base_url}/me/messages"
        params = {
            "access_token": self.access_token
        }
        payload = {
            "recipient": {"id": recipient_id},
            "message": {"text": message}
        }
        
        try:
            response = requests.post(url, params=params, json=payload)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error sending Instagram message: {str(e)}")
            return None
            
    def send_image(self, recipient_id, image_url):
        """Send an image to an Instagram user"""
        url = f"{self.base_url}/me/messages"
        params = {
            "access_token": self.access_token
        }
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
            }
        }
        
        try:
            response = requests.post(url, params=params, json=payload)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error sending Instagram image: {str(e)}")
            return None
