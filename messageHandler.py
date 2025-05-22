import os
import logging
import requests
from io import BytesIO
import time
import google.generativeai as genai
from dotenv import load_dotenv
import urllib3
from brain import query
import datetime
from github import Github
from collections import deque
import cv2
import numpy as np
from PIL import Image
from skimage.metrics import structural_similarity as ssim

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Load environment variables
load_dotenv()

# Logging setup
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# Default settings
settings = {
    "shop_name": "Febrica",
    "shop_number": "+8801709805177",
    "shop_email": "developerabdurrahman88@gmail.com",
    "currency": "BDT",
    "ai_name": "Ruhi",
    "payment_methods": {
        "cod": True,
        "bkash": True,
        "nagad": False,
        "bkash_number": "01709805177",
        "nagad_number": "",
        "bkash_type": "Personal",
        "nagad_type": "Personal",
        "paypal": False,
        "paypal_email": ""
    },
    "delivery_records": [
    ],
    "service_products": "Selling high-quality Shirts, Pants, and Shoes.",
    "return_policy": "Customers can return products within 7 days if there is a valid issue. Money will be refunded without delivery charges."
}

def update_settings(shop_name=None, shop_number=None, shop_email=None, currency=None, ai_name=None, greeting=None, 
                   payment_methods=None, delivery_records=None, service_products=None, return_policy=None):
    if shop_name:
        settings["shop_name"] = shop_name
    if shop_number:
        settings["shop_number"] = shop_number
    if shop_email:
        settings["shop_email"] = shop_email
    if currency:
        settings["currency"] = currency
    if ai_name:
        settings["ai_name"] = ai_name
    if payment_methods:
        settings["payment_methods"].update(payment_methods)
    if delivery_records:
        settings["delivery_records"] = delivery_records
    if service_products:
        settings["service_products"] = service_products
    if return_policy:
        settings["return_policy"] = return_policy

def get_settings():
    return settings

def format_delivery_records():
    return "\n".join([
        f"{record['country']} ({record['region']}): Delivery charge {record['delivery_charge']}{settings['currency']}, Delivery time {record['delivery_time']}"
        for record in settings['delivery_records']
    ])

# Product List
products = [
    {'category': 'Shirt', 'type': 'Denim Shirt', 'size': ['M', 'L', 'XL'], 'color': ['Blue', 'Gray'], 'image': 'https://ezbo.org/product-image/uploads/img_682c988cbd00b6.10732605.jpg', 'price': 780},
    {'category': 'Shirt', 'type': 'Cotton Shirt', 'size': ['M', 'L', 'XL', 'XXL'], 'color': ['Black', 'Navy'], 'image': 'https://ezbo.org/product-image/uploads/img_682c98c0ee3119.95771931.jpg', 'price': 800},
    {'category': 'Pant', 'type': 'Cargo Pant', 'size': ['M', 'L', 'XL', 'XXL'], 'color': ['Gray', 'White'], 'image': 'https://ezbo.org/product-image/uploads/img_682c990bc73608.08671474.jpg', 'price': 850},
    {'category': 'Pant', 'type': 'Gabardine Pant', 'size': ['M', 'L', 'XL', 'XXL'], 'color': ['Black', 'Blue'], 'image': 'https://ezbo.org/product-image/uploads/img_682c9966ed74c6.48769739.jpg', 'price': 720},
    {'category': 'Shoes', 'type': 'Casual Shoes', 'size': ['36', '37', '38', '39', '40', '41', '42'], 'color': ['Blue', 'Red'], 'image': 'https://ezbo.org/product-image/uploads/img_682c99a0295111.82030960.jpg', 'price': 1100},
    {'category': 'Shoes', 'type': 'Dress Shoes', 'size': ['36', '37', '38', '39', '40'], 'color': ['Black', 'Orange'], 'image': 'https://ezbo.org/product-image/uploads/img_682c99d3d32951.87415347.jpg', 'price': 950}
]

def get_products():
    return products

def add_product(product):
    products.append(product)

def update_product(index, product):
    if 0 <= index < len(products):
        products[index] = product

def remove_product(index):
    if 0 <= index < len(products):
        products.pop(index)

# Orders List
orders = [
    {'name': 'Ahon', 'mobile': '01717670615', 'address': 'SP Park Road, Tangail', 'product': 'Cotton Shirt (L, Black)', 'price': 800, 'payment_method': 'COD', 'total': 800, 'delivery_charge': 0, 'subtotal': 800, 'status': 'Preparing', 'date': '2025-05-21'},
    {'name': 'Tanbhir Ahammed', 'mobile': '01540605804', 'address': 'Pangsha, Rajbari', 'product': 'Casual Shoes (42, Blue)', 'price': 1100, 'payment_method': 'COD', 'total': 1100, 'delivery_charge': 0, 'subtotal': 1100, 'status': 'Preparing', 'date': '2025-05-21'},
    {'name': 'Suleiman', 'mobile': '08088941798', 'address': 'Adebayo ado ekiti', 'product': 'Dress Shoes (40, Red)', 'price': 950, 'payment_method': 'COD', 'total': 950, 'delivery_charge': 0, 'subtotal': 950, 'status': 'Preparing', 'date': '2025-05-21'},
    {'name': 'Adiba', 'mobile': '01797332640', 'address': 'Tangail', 'product': 'Dress Shoes (40, Black)', 'price': 950, 'payment_method': 'COD', 'total': 950, 'delivery_charge': 0, 'subtotal': 950, 'status': 'Preparing', 'date': '2025-05-21'},
    {'name': 'Adib', 'mobile': '01707322640', 'address': 'Tangail', 'product': 'Dress Shoes (40, Orange)', 'price': 950, 'payment_method': 'COD', 'total': 950, 'delivery_charge': 0, 'subtotal': 950, 'status': 'Preparing', 'date': '2025-05-22'}
]

# Sales Logs List
sales_logs = []

def get_orders():
    return orders

def add_order(order):
    orders.append(order)
    update_github_repo_orders(orders)
    logger.info("New order added and GitHub repository updated.")
    
    # Send email notification for new orders
    try:
        from app import send_order_notification
        send_order_notification(order)
    except Exception as e:
        logger.error(f"Failed to send order notification email: {str(e)}")

def update_order_status(index, status):
    if 0 <= index < len(orders):
        orders[index]["status"] = status
        if status in ["Delivered", "Canceled"]:
            orders[index]["date"] = datetime.datetime.now().strftime("%Y-%m-%d")
            sales_logs.append(orders.pop(index))
            save_sales_logs_to_github()

def remove_old_logs():
    global sales_logs
    cutoff_date = datetime.datetime.now() - datetime.timedelta(days=60)
    sales_logs = [log for log in sales_logs if datetime.datetime.strptime(log.get("date", "1970-01-01"), "%Y-%m-%d") >= cutoff_date]
    save_sales_logs_to_github()

def save_sales_logs_to_github():
    try:
        github = Github(os.getenv("GITHUB_ACCESS_TOKEN"))
        repo = github.get_repo(os.getenv("GITHUB_REPO_NAME"))
        
        # Get current content or create file if it doesn't exist
        try:
            content = repo.get_contents("templates/saleslogs.txt")
            logs_str = "\n".join([str(log) for log in sales_logs])
            repo.update_file(
                path="templates/saleslogs.txt",
                message="Update sales logs via chatbot",
                content=logs_str,
                sha=content.sha
            )
        except Exception as e:
            if "404" in str(e):
                repo.create_file(
                    path="templates/saleslogs.txt",
                    message="Initialize sales logs file",
                    content="\n".join([str(log) for log in sales_logs]),
                    branch="main"
                )
        
        logger.info("Sales logs saved to GitHub.")
    except Exception as e:
        logger.error(f"Failed to save sales logs to GitHub: {str(e)}")

def load_sales_logs_from_github():
    try:
        github = Github(os.getenv("GITHUB_ACCESS_TOKEN"))
        repo = github.get_repo(os.getenv("GITHUB_REPO_NAME"))
        
        # First try to get the file contents
        try:
            content = repo.get_contents("templates/saleslogs.txt")
            logs_str = content.decoded_content.decode("utf-8").strip()
            
            # If file is empty, initialize with empty list
            if not logs_str:
                sales_logs.clear()
                logger.info("Initialized empty sales logs from blank file.")
                return
                
            # Try to parse the logs
            logs = logs_str.splitlines()
            sales_logs.clear()
            for log in logs:
                if log.strip():  # Skip empty lines
                    sales_logs.append(eval(log.strip()))
            logger.info("Sales logs loaded from GitHub.")
            
        except Exception as e:
            # If file doesn't exist, create it
            if "404" in str(e):
                repo.create_file(
                    path="templates/saleslogs.txt",
                    message="Initialize sales logs file",
                    content="",
                    branch="main"
                )
                sales_logs.clear()
                logger.info("Created new sales logs file.")
            else:
                raise
                
    except Exception as e:
        logger.error(f"Failed to load sales logs from GitHub: {str(e)}")
        # Initialize empty sales logs if loading fails
        sales_logs.clear()

load_sales_logs_from_github()

def update_github_repo_orders(orders):
    try:
        from github import Github
        github = Github(os.getenv("GITHUB_ACCESS_TOKEN"))
        repo = github.get_repo(os.getenv("GITHUB_REPO_NAME"))
        content = repo.get_contents("messageHandler.py")
        current_content = content.decoded_content.decode("utf-8")
        start_marker = "# Orders List\norders = ["
        end_marker = "\n]"
        start_index = current_content.find(start_marker)
        end_index = current_content.find(end_marker, start_index) + len(end_marker)
        if start_index == -1 or end_index == -1:
            logger.error("Failed to locate the orders block in messageHandler.py")
            return
        updated_content = (
            current_content[:start_index] +
            f"# Orders List\norders = [\n" +
            ",\n".join([f"    {repr(order)}" for order in orders]) +
            "\n]" +
            current_content[end_index:]
        )
        repo.update_file(
            path="messageHandler.py",
            message="Update orders via chatbot",
            content=updated_content,
            sha=content.sha
        )
        logger.info("GitHub repository updated successfully with new orders.")
    except Exception as e:
        logger.error(f"Failed to update GitHub repository: {str(e)}")

def analyze_and_match_product(image_url):
    try:
        # Download the user's image
        response = requests.get(image_url)
        user_img = Image.open(BytesIO(response.content))
        user_img = np.array(user_img)
        
        # Convert to grayscale and resize for comparison
        user_gray = cv2.cvtColor(user_img, cv2.COLOR_BGR2GRAY)
        user_gray = cv2.resize(user_gray, (250, 250))
        
        # Apply preprocessing to handle quality variations
        user_gray = cv2.GaussianBlur(user_gray, (5,5), 0)
        _, user_gray = cv2.threshold(user_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        best_match = None
        highest_score = 0
        
        # Compare with all product images
        for product in products:
            if 'image' in product and product['image']:
                try:
                    # Download product image
                    product_response = requests.get(product['image'])
                    product_img = Image.open(BytesIO(product_response.content))
                    product_img = np.array(product_img)
                    
                    # Convert to grayscale and resize
                    product_gray = cv2.cvtColor(product_img, cv2.COLOR_BGR2GRAY)
                    product_gray = cv2.resize(product_gray, (250, 250))
                    
                    # Apply same preprocessing to product image
                    product_gray = cv2.GaussianBlur(product_gray, (5,5), 0)
                    _, product_gray = cv2.threshold(product_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                    
                    # Calculate similarity score using multiple methods
                    ssim_score = ssim(user_gray, product_gray)
                    
                    # Additional matching techniques
                    orb = cv2.ORB_create()
                    kp1, des1 = orb.detectAndCompute(user_gray, None)
                    kp2, des2 = orb.detectAndCompute(product_gray, None)
                    
                    if des1 is not None and des2 is not None:
                        bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
                        matches = bf.match(des1, des2)
                        match_score = len(matches) / max(len(des1), len(des2)) if matches else 0
                    else:
                        match_score = 0
                    
                    # Combined score (weighted average)
                    combined_score = (ssim_score * 0.7) + (match_score * 0.3)
                    
                    # Update best match if this is better
                    if combined_score > highest_score:
                        highest_score = combined_score
                        best_match = product
                        
                except Exception as e:
                    logger.error(f"Error processing product image {product['image']}: {str(e)}")
                    continue
        
        # Return best match if similarity score is above threshold
        if best_match and highest_score > 0.4:  # Lowered threshold to 40% for better matching
            return best_match, highest_score
            
    except Exception as e:
        logger.error(f"Error in image analysis: {str(e)}")
    
    return None, 0
    
def extract_image_url(message):
    """Extract image URL from message text"""
    if message.startswith("image_url:"):
        return message.split("image_url:")[1].strip()
    return None

# Optimized system instruction template
def get_system_instruction():
    time_now = time.asctime(time.localtime(time.time()))
    product_list = format_product_list()
    order_list = format_order_list()
    delivery_records = format_delivery_records()
    
    return f"""# {settings['shop_name']} AI Chatbot System Instructions

## Introduction
I am {settings['ai_name']}, your AI assistant from {settings['shop_name']}. My purpose is to help with product inquiries and orders, as well as to sell products.
I respond in short, clear sentences. For unrelated questions, I'll politely redirect to {settings['shop_name']}-related topics. I can't share any details about my creation or creator because it's confidential.

## Company Info
Shop Name: {settings['shop_name']}
Contact: {settings['shop_number']}
Contact: {settings['shop_email']}
Currency: {settings['currency']}
Products: {settings['service_products']}
Returns: {settings['return_policy']}

## Currency
Always show prices in {settings['currency']} (e.g., "750{settings['currency']}").

## Delivery Info
{delivery_records}

## Payment Methods
Enabled payment methods:
- COD: {"Yes" if settings['payment_methods']['cod'] else "No"}
- Bkash: {"Yes" if settings['payment_methods']['bkash'] else "No"} {f"({settings['payment_methods']['bkash_number']} - {settings['payment_methods']['bkash_type']})" if settings['payment_methods']['bkash'] else ""}
- Nagad: {"Yes" if settings['payment_methods']['nagad'] else "No"} {f"({settings['payment_methods']['nagad_number']} - {settings['payment_methods']['nagad_type']})" if settings['payment_methods']['nagad'] else ""}
- PayPal: {"Yes" if settings['payment_methods']['paypal'] else "No"} {f"({settings['payment_methods']['paypal_email']})" if settings['payment_methods']['paypal'] else ""}

## Payment Instructions Example
When customer selects a payment method:
1. Provide the payment details (number/email as configured)
2. Show total: product price + delivery charge
3. Request transaction ID if needed
Example: "Please send {850 + 130} = 980{settings['currency']} to Nagad: {settings['payment_methods']['nagad_number']} (Personal). Send the Transaction ID after payment."

## Product Catalog
{product_list}

## Current Orders
{order_list}

## Behavior Guidelines
1. Keep replies short 1–2 lines max, sound human, and match the customer's tone and mood. Only go longer when truly needed.
2. Product inquiries: Ask for details if needed (size, color) or picture.
3. Filter products exactly when specific criteria given.
4. For budgets: Show matching products in range.
6. Don't send an image link with product details or a list if the user hasn't asked for it.
6. If a user wants to see a product, include the image URL in the format: "[Product Name] - [Image URL]" when showing product image."
7. Analyze the customer's product image, compare it with the catalog, show matching details if similarity >40%, otherwise request more details politely.

## Order Process
1. Collect: name, mobile, address, product details. When you have the required details, Send the list of available payment methods and ask the customer to select one.
2. If the customer selects COD, send the order confirmation message directly. Otherwise, send the payment details:
   - Provide payment details and total amount
   - Request transaction ID
3. After receiving the transaction ID, send a confirmation message.
Note: Make sure to send the text "Your order has been placed!" with the order confirmation message:
Your order has been placed!
   - Name: [Name]
   - Mobile: [Number]
   - Address: [Address]
   - Product: [Product] ([Size], [Color])
   - Price: [Price]{settings['currency']}
   - Payment Method: [Method]{" (Txn ID: [ID])" if "[Method]" != "COD" else ""}
   - Total: [Total]{settings['currency']}

## Reply after Order Confirmation
After sending order confirmation message, if the user responds with anything acknowledge it naturally without repeating the order confirmation message.

## Order Inquiry
If a customer inquires about their order, such as an update, status, or details, request their name and mobile number. If both the word-for-word name and digit-for-digit number do not match exactly from start 
to end, ask them to try again. Once an exact match is found, provide the order status.

## Handling Critical Issues Beyond AI's Capability
If a customer asks for an order detail change, order cancellation, return, or any situation that requires human assistance, politely direct them to the shop's contact number.
"""

def get_gemini_api_key():
    try:
        response = requests.get('https://ezbo.org/tools/api-keys.php?get_key=1')
        if response.status_code == 200:
            return response.text.strip()
        logger.error(f"Failed to get API key: HTTP {response.status_code}")
        return None
    except Exception as e:
        logger.error(f"Error fetching API key: {str(e)}")
        return None

def initialize_text_model():
    api_key = get_gemini_api_key()
    if not api_key:
        raise ValueError("No active Gemini API key available")
    
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        generation_config={
            "temperature": 0.3,
            "top_p": 0.95,
            "top_k": 30,
            "max_output_tokens": 8192,
        }
    )

def format_product_list():
    return "\n".join([
        f"{p['type']} ({p['category']}) - Size: {', '.join(map(str, p['size']))}, Color: {', '.join(p['color'])}, Image: {p.get('image', 'No image')}, Price: {p['price']}{settings['currency']}"
        for p in products
    ])

def format_order_list():
    return "\n".join([
        f"Name: {o['name']}, Mobile: {o['mobile']}, Product: {o['product']}, Status: {o['status']}"
        for o in orders
    ])

def extract_order_details(response):
    try:
        order = {}
        lines = [line.strip() for line in response.split("\n") if line.strip()]
        
        # Check if this is an order confirmation message
        if "Your order has been placed!" not in response:
            return None
            
        for line in lines:
            if line.startswith("- Name:"):
                order["name"] = line.split("Name:")[1].strip()
            elif line.startswith("- Mobile:"):
                order["mobile"] = line.split("Mobile:")[1].strip()
            elif line.startswith("- Address:"):
                order["address"] = line.split("Address:")[1].strip()
            elif line.startswith("- Product:"):
                order["product"] = line.split("Product:")[1].strip()
            elif line.startswith("- Price:"):
                price_str = line.split("Price:")[1].split(settings['currency'])[0].strip()
                order["price"] = int(float(price_str))
            elif line.startswith("- Payment Method:"):
                payment_part = line.split("Payment Method:")[1].strip()
                if "(Txn ID:" in payment_part:
                    parts = payment_part.split("(Txn ID:")
                    order["payment_method"] = parts[0].strip()
                    order["transaction_id"] = parts[1].replace(")", "").strip()
                else:
                    order["payment_method"] = payment_part
            elif line.startswith("- Total:"):
                total_str = line.split("Total:")[1].split(settings['currency'])[0].strip()
                order["total"] = int(float(total_str))
        
        # Calculate delivery charge
        if "price" in order and "total" in order:
            order["delivery_charge"] = order["total"] - order["price"]
            order["subtotal"] = order["price"]
        
        # Set default status
        order["status"] = "Preparing"
        
        # Add date for sales logs
        order["date"] = datetime.datetime.now().strftime("%Y-%m-%d")
        
        return order if all(k in order for k in ['name', 'mobile', 'product', 'price']) else None
        
    except Exception as e:
        logger.error(f"Error extracting order details: {str(e)}")
        return None

def handle_text_message(user_message, last_message):
    try:
        logger.info("Processing text message: %s", user_message)
        
        # Check if this is an image attachment
        if "image_url:" in user_message.lower():
            image_url = extract_image_url(user_message)
            if image_url:
                matched_product, score = analyze_and_match_product(image_url)
                if matched_product:
                    response = (
                        f"I found a similar product in our catalog ({(score*100):.1f}% match):\n"
                        f"{matched_product['type']} ({matched_product['category']})\n"
                        f"Sizes: {', '.join(matched_product['size'])}\n"
                        f"Colors: {', '.join(matched_product['color'])}\n"
                        f"Price: {matched_product['price']}{settings['currency']}\n"
                        f"Image: {matched_product['image']}"
                    )
                    # Return both the response and the matched product info to be saved in memory
                    return response, matched_product
                else:
                    return "I couldn't find a matching product in our catalog. Could you please describe what you're looking for?", None

        # Original processing continues if no image or no match found
        system_instruction = get_system_instruction()
        
        chat = initialize_text_model().start_chat(history=[])
        response = chat.send_message(f"{system_instruction}\n\nHuman: {user_message}")
        
        simplified_response = response.text.strip()
        
        # Clean up any remaining formatting characters
        simplified_response = simplified_response.replace("*", "")
        
        # Check if this is an order confirmation
        if "Your order has been placed!" in simplified_response:
            order_details = extract_order_details(simplified_response)
            if order_details:
                add_order(order_details)
                update_github_repo_orders(orders)
                logger.info("New order added and GitHub repository updated.")
        
        return simplified_response, None

    except Exception as e:
        logger.error(f"Error processing text message: {str(e)}")
        return "😔 Sorry, I encountered an error processing your message. Please try again later.", None
