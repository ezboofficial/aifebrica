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
from system_instruction import get_system_instruction

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
        {'country': 'Bangladesh', 'region': 'Inside Dhaka ', 'delivery_time': '1-3 Days', 'delivery_charge': 60},
        {'country': 'Bangladesh ', 'region': 'Outside Dhaka ', 'delivery_time': '3-5 Days', 'delivery_charge': 130},
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

# Product List
products = [
    {'category': 'Shirt', 'type': 'Denim Shirt', 'size': ['M', 'L', 'XL'], 'color': ['Blue', 'Gray'], 'image': 'https://ezbo.org/product-image/uploads/img_682c988cbd00b6.10732605.jpg', 'price': 785},
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
    {'name': 'Adiba', 'mobile': '01707322649', 'address': 'Karatia,Tangail', 'product': 'Denim Shirt (XL, Blue)', 'price': 780, 'payment_method': 'COD', 'total': 840, 'delivery_charge': 60, 'subtotal': 780, 'status': 'Preparing', 'date': '2025-06-07'},
    {'name': 'Adiba', 'mobile': '01707322649', 'address': '12-7,Karatia, Tangail', 'product': 'Denim Shirt (XL, Blue)', 'price': 780, 'payment_method': 'Bkash', 'transaction_id': 'CF30M88M2I', 'total': 940, 'delivery_charge': 160, 'subtotal': 780, 'status': 'Preparing', 'date': '2025-06-07'},
    {'name': 'Mr. Beast', 'mobile': '01709805110', 'address': 'Sector 10, Road 8, Uttara, Dhaka', 'product': 'Dress Shoes (40, Black)', 'price': 950, 'payment_method': 'Bkash', 'transaction_id': 'TXN23060511254789', 'total': 1010, 'delivery_charge': 60, 'subtotal': 950, 'status': 'Shipping', 'date': '2025-06-07'},
    {'name': 'Abdur Rahman', 'mobile': '01709702692', 'address': 'Dhaka, Boshundhora 18', 'product': 'Denim Shirt (XL, Gray)', 'price': 785, 'payment_method': 'Bkash', 'transaction_id': 'CF73PTCKCP', 'total': 845, 'delivery_charge': 60, 'subtotal': 785, 'status': 'Preparing', 'date': '2025-06-09'},
    {'name': 'Jhon', 'mobile': '01711111111', 'address': 'Mirpur 10, Kazi Para, Dhaka', 'product': 'Denim Shirt (XL, Blue)', 'price': 785, 'payment_method': 'Bkash', 'transaction_id': '234568434zer', 'total': 845, 'delivery_charge': 60, 'subtotal': 785, 'status': 'Preparing', 'date': '2025-06-10'}
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
        
        try:
            content = repo.get_contents("templates/saleslogs.txt")
            logs_str = content.decoded_content.decode("utf-8").strip()
            
            if not logs_str:
                sales_logs.clear()
                logger.info("Initialized empty sales logs from blank file.")
                return
                
            logs = logs_str.splitlines()
            sales_logs.clear()
            for log in logs:
                if log.strip():
                    sales_logs.append(eval(log.strip()))
            logger.info("Sales logs loaded from GitHub.")
            
        except Exception as e:
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
        response = requests.get(image_url)
        user_img = Image.open(BytesIO(response.content))
        user_img = np.array(user_img)
        
        user_gray = cv2.cvtColor(user_img, cv2.COLOR_BGR2GRAY)
        user_gray = cv2.resize(user_gray, (250, 250))
        
        user_gray = cv2.GaussianBlur(user_gray, (5,5), 0)
        _, user_gray = cv2.threshold(user_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        best_match = None
        highest_score = 0
        
        for product in products:
            if 'image' in product and product['image']:
                try:
                    product_response = requests.get(product['image'])
                    product_img = Image.open(BytesIO(product_response.content))
                    product_img = np.array(product_img)
                    
                    product_gray = cv2.cvtColor(product_img, cv2.COLOR_BGR2GRAY)
                    product_gray = cv2.resize(product_gray, (250, 250))
                    
                    product_gray = cv2.GaussianBlur(product_gray, (5,5), 0)
                    _, product_gray = cv2.threshold(product_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                    
                    ssim_score = ssim(user_gray, product_gray)
                    
                    orb = cv2.ORB_create()
                    kp1, des1 = orb.detectAndCompute(user_gray, None)
                    kp2, des2 = orb.detectAndCompute(product_gray, None)
                    
                    if des1 is not None and des2 is not None:
                        bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
                        matches = bf.match(des1, des2)
                        match_score = len(matches) / max(len(des1), len(des2)) if matches else 0
                    else:
                        match_score = 0
                    
                    combined_score = (ssim_score * 0.7) + (match_score * 0.3)
                    
                    if combined_score > highest_score:
                        highest_score = combined_score
                        best_match = product
                        
                except Exception as e:
                    logger.error(f"Error processing product image {product['image']}: {str(e)}")
                    continue
        
        if best_match and highest_score > 0.4:
            return best_match, highest_score
            
    except Exception as e:
        logger.error(f"Error in image analysis: {str(e)}")
    
    return None, 0
    
def extract_image_url(message):
    if message.startswith("image_url:"):
        return message.split("image_url:")[1].strip()
    return None

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

def extract_order_details(response):
    try:
        order = {}
        lines = [line.strip() for line in response.split("\n") if line.strip()]
        
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
        
        if "price" in order and "total" in order:
            order["delivery_charge"] = order["total"] - order["price"]
            order["subtotal"] = order["price"]
        
        order["status"] = "Preparing"
        order["date"] = datetime.datetime.now().strftime("%Y-%m-%d")
        
        return order if all(k in order for k in ['name', 'mobile', 'product', 'price']) else None
        
    except Exception as e:
        logger.error(f"Error extracting order details: {str(e)}")
        return None

def handle_text_message(user_message, last_message):
    try:
        logger.info("Processing text message: %s", user_message)
        
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
                    return response, matched_product
                else:
                    return "No Match Found!!\n\n- I couldn't find anything matching in our catalog.\n- To help me assist you, please follow these steps:\n\n 1. Visit our Facebook page.\n 2. Download an image of the product you need.\n 3. Send it to me directly.\n\n- You can also describe what you're looking for, I can then show you your needed product with an image.", None

        system_instruction = get_system_instruction(settings, products, orders)
        
        chat = initialize_text_model().start_chat(history=[])
        response = chat.send_message(f"{system_instruction}\n\nHuman: {user_message}")
        
        simplified_response = response.text.strip()
        simplified_response = simplified_response.replace("*", "")
        
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
