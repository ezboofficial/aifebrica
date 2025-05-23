from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, Response, session
import os
import logging
from flask_cors import CORS
import requests
import messageHandler
from collections import deque
from brain import query
from github import Github
import urllib.parse
from functools import wraps
import hashlib
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import send_from_directory
import datetime

load_dotenv()

app = Flask(__name__)
CORS(app)
app.secret_key = os.getenv("SECRET_KEY", "supersecretkey")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN")
GITHUB_ACCESS_TOKEN = os.getenv("GITHUB_ACCESS_TOKEN")
GITHUB_REPO_NAME = os.getenv("GITHUB_REPO_NAME")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

github = Github(GITHUB_ACCESS_TOKEN)
repo = github.get_repo(GITHUB_REPO_NAME)

user_memory = {}
AI_ENABLED = True

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def is_logged_in():
    return session.get('logged_in')

def update_user_memory(user_id, message):
    if user_id not in user_memory:
        user_memory[user_id] = deque(maxlen=20)
    user_memory[user_id].append(message)

def get_conversation_history(user_id):
    return "\n".join(user_memory.get(user_id, []))

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if is_logged_in():
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if (username == ADMIN_USERNAME and 
            password == ADMIN_PASSWORD):
            session['logged_in'] = True
            flash('Login successful!', 'success')
            next_page = request.args.get('next', url_for('dashboard'))
            return redirect(next_page)
        else:
            flash('Invalid username or password', 'error')
            return redirect(url_for('login'))
    
    return render_template('login.html', title="Login")

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

@app.route('/')
def home():
    if is_logged_in():
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', 
                         title="Dashboard", 
                         orders=messageHandler.get_orders(),
                         settings=messageHandler.get_settings(),
                         AI_ENABLED=AI_ENABLED)

@app.route('/toggle_ai', methods=['POST'])
@login_required
def toggle_ai():
    global AI_ENABLED
    AI_ENABLED = not AI_ENABLED
    return jsonify({'status': 'success', 'ai_enabled': AI_ENABLED})

@app.route('/webhook', methods=['GET'])
def verify():
    token_sent = request.args.get("hub.verify_token")
    if token_sent == VERIFY_TOKEN:
        logger.info("Webhook verification successful.")
        return request.args.get("hub.challenge", "")
    logger.error("Webhook verification failed: invalid verify token.")
    return "Verification failed", 403

@app.route('/webhook', methods=['POST'])
def webhook():
    global AI_ENABLED
    if not AI_ENABLED:
        logger.info("AI is currently disabled - ignoring message")
        return "EVENT_RECEIVED", 200
        
    data = request.get_json()
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
                                # Enhanced thumbs-up detection
                                if (payload.get("sticker_id") == "369239263222822" or  # Standard thumbs-up sticker ID
                                    "thumbs up sign" in payload.get("title", "").lower() or  # From inspect element
                                    any(tag in payload.get("url", "").lower() 
                                    for tag in ["thumbs_up", "like.png", "fb_like", "thumbsup"]) or
                                    any(prop.get("d", "") == "M3.3,6H0.7C0.3,6,0,6.3,0,6.7v8.5C0,15.7,0.3,16,0.7,16h2.5C3.7,16,4,15.7,4,15.3V6.7C4,6.3,3.7,6,3.3,6z"
                                    for prop in payload.get("metadata", {}).get("elements", []))):
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
                                    response, matched_product = messageHandler.handle_text_message(
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
                        response, _ = messageHandler.handle_text_message(full_message, message_text)
                        
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

    return "EVENT_RECEIVED", 200
    
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
            logger.error(f"Failed to send image: {response.text}")
    except Exception as e:
        logger.error(f"Error sending image: {str(e)}")

def update_github_repo(products):
    try:
        repo = github.get_repo(GITHUB_REPO_NAME)
        content = repo.get_contents("messageHandler.py")
        current_content = content.decoded_content.decode("utf-8")
        start_marker = "# Product List\nproducts = ["
        end_marker = "\n]"
        start_index = current_content.find(start_marker)
        end_index = current_content.find(end_marker, start_index) + len(end_marker)

        if start_index == -1 or end_index == -1:
            logger.error("Failed to locate products block")
            return

        updated_content = (
            current_content[:start_index] +
            f"# Product List\nproducts = [\n" +
            ",\n".join([f"    {repr(product)}" for product in products]) +
            "\n]" +
            current_content[end_index:]
        )

        repo.update_file(
            path="messageHandler.py",
            message="Update products via dashboard",
            content=updated_content,
            sha=content.sha
        )
        logger.info("GitHub products updated")
    except Exception as e:
        logger.error(f"Failed to update GitHub products: {str(e)}")

def update_github_repo_settings(settings):
    try:
        repo = github.get_repo(GITHUB_REPO_NAME)
        content = repo.get_contents("messageHandler.py")
        current_content = content.decoded_content.decode("utf-8")
        
        delivery_records_str = "[\n"
        for record in settings['delivery_records']:
            delivery_records_str += f"        {repr(record)},\n"
        delivery_records_str += "    ]"
        
        new_settings_block = f"""
# Default settings
settings = {{
    "shop_name": "{settings['shop_name']}",
    "shop_number": "{settings['shop_number']}",
    "shop_email": "{settings['shop_email']}",
    "currency": "{settings['currency']}",
    "ai_name": "{settings['ai_name']}",
    "payment_methods": {{
        "cod": {settings['payment_methods']['cod']},
        "bkash": {settings['payment_methods']['bkash']},
        "nagad": {settings['payment_methods']['nagad']},
        "bkash_number": "{settings['payment_methods']['bkash_number']}",
        "nagad_number": "{settings['payment_methods']['nagad_number']}",
        "bkash_type": "{settings['payment_methods']['bkash_type']}",
        "nagad_type": "{settings['payment_methods']['nagad_type']}",
        "paypal": {settings['payment_methods']['paypal']},
        "paypal_email": "{settings['payment_methods']['paypal_email']}"
    }},
    "delivery_records": {delivery_records_str},
    "service_products": "{settings['service_products']}",
    "return_policy": "{settings['return_policy']}"
}}
"""
        start_marker = "# Default settings\nsettings = {"
        end_marker = "}\n"
        start_index = current_content.find(start_marker)
        end_index = current_content.find(end_marker, start_index) + len(end_marker)

        if start_index == -1 or end_index == -1:
            logger.error("Failed to locate settings block")
            return

        updated_content = (
            current_content[:start_index] +
            new_settings_block.strip() +
            "\n" +
            current_content[end_index:]
        )

        repo.update_file(
            path="messageHandler.py",
            message="Update AI settings via dashboard",
            content=updated_content,
            sha=content.sha
        )
        logger.info("GitHub settings updated")
    except Exception as e:
        logger.error(f"Failed to update GitHub settings: {str(e)}")
        
def update_github_repo_orders(orders):
    try:
        repo = github.get_repo(GITHUB_REPO_NAME)
        content = repo.get_contents("messageHandler.py")
        current_content = content.decoded_content.decode("utf-8")
        start_marker = "# Orders List\norders = ["
        end_marker = "\n]"
        start_index = current_content.find(start_marker)
        end_index = current_content.find(end_marker, start_index) + len(end_marker)

        if start_index == -1 or end_index == -1:
            logger.error("Failed to locate orders block")
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
            message="Update orders via dashboard",
            content=updated_content,
            sha=content.sha
        )
        logger.info("GitHub orders updated")
    except Exception as e:
        logger.error(f"Failed to update GitHub orders: {str(e)}")

@app.route('/orderlists', methods=['GET', 'POST'])
@login_required
def order_lists():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'update_status':
            order_index = int(request.form.get('order_index'))
            new_status = request.form.get('status')
            messageHandler.update_order_status(order_index, new_status)
            flash("Order status updated successfully!", "success")
            update_github_repo_orders(messageHandler.get_orders())
        return redirect(url_for('order_lists'))

    return render_template('orderlists.html', title="Order Lists", orders=messageHandler.get_orders(), AI_ENABLED=AI_ENABLED)

@app.route('/order/<int:order_index>', methods=['GET', 'POST'])
@login_required
def view_order(order_index):
    order = messageHandler.get_orders()[order_index]
    if request.method == 'POST':
        new_status = request.form.get('status')
        messageHandler.update_order_status(order_index, new_status)
        flash("Order status updated successfully!", "success")
        update_github_repo_orders(messageHandler.get_orders())
        return redirect(url_for('order_lists'))
    
    return render_template('vieworder.html', title="View Order", order=order, order_index=order_index, settings=messageHandler.get_settings())

@app.route('/saleslogs', methods=['GET', 'POST'])
@login_required
def sales_logs():
    if request.method == 'POST':
        if request.form.get('action') == 'download_all':
            import json
            from io import StringIO
            output = StringIO()
            json.dump(messageHandler.sales_logs, output, indent=4)
            output.seek(0)
            return Response(
                output,
                mimetype="application/json",
                headers={"Content-Disposition": "attachment;filename=sales_logs.json"}
            )

    categories = set()
    for log in messageHandler.sales_logs:
        product = log['product']
        if 'Shirt' in product:
            categories.add('Shirt')
        if 'Pant' in product:
            categories.add('Pant')
        if 'Shoes' in product:
            categories.add('Shoes')
        if 'Bag' in product:
            categories.add('Bag')
        if 'Accessory' in product:
            categories.add('Accessory')

    return render_template('saleslogs.html', title="Sales Logs", sales_logs=messageHandler.sales_logs, settings=messageHandler.get_settings(), categories=categories)

@app.route('/analyzeai')
@login_required
def analyze_ai():
    total_earnings = sum(order['total'] for order in messageHandler.sales_logs if 'total' in order)
    total_orders = len(messageHandler.sales_logs) + len(messageHandler.get_orders())
    delivered_orders = len([order for order in messageHandler.sales_logs if order['status'] == 'Delivered'])
    canceled_orders = len([order for order in messageHandler.sales_logs if order['status'] == 'Canceled'])
    preparing_orders = len([order for order in messageHandler.get_orders() if order['status'] == 'Preparing'])
    shipping_orders = len([order for order in messageHandler.get_orders() if order['status'] == 'Shipping'])
    delivering_orders = len([order for order in messageHandler.get_orders() if order['status'] == 'Delivering'])

    from collections import defaultdict
    product_sales = defaultdict(int)
    for order in messageHandler.sales_logs:
        product_sales[order['product']] += 1
    best_selling_products = sorted(product_sales.items(), key=lambda x: x[1], reverse=True)[:5]
    best_selling_products_labels = [product[0] for product in best_selling_products]
    best_selling_products_data = [product[1] for product in best_selling_products]

    from datetime import datetime, timedelta
    orders_over_time = defaultdict(int)
    for order in messageHandler.sales_logs:
        order_date = datetime.strptime(order['date'], "%Y-%m-%d")
        if order_date >= datetime.now() - timedelta(days=7):
            orders_over_time[order_date.strftime("%Y-%m-%d")] += 1
    orders_over_time_labels = sorted(orders_over_time.keys())
    orders_over_time_data = [orders_over_time[date] for date in orders_over_time_labels]

    max_earnings = max(total_earnings, 1)
    max_orders = max(total_orders, 1)

    return render_template(
        'analyzeai.html',
        title="Analyze AI",
        total_earnings=total_earnings,
        total_orders=total_orders,
        preparing_orders=preparing_orders,
        delivered_orders=delivered_orders,
        canceled_orders=canceled_orders,
        shipping_orders=shipping_orders,
        delivering_orders=delivering_orders,
        best_selling_products_labels=best_selling_products_labels,
        best_selling_products_data=best_selling_products_data,
        orders_over_time_labels=orders_over_time_labels,
        orders_over_time_data=orders_over_time_data,
        max_earnings=max_earnings,
        max_orders=max_orders,
        settings=messageHandler.get_settings()
    )

@app.route('/stocklists', methods=['GET', 'POST'])
@login_required
def stock_lists():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            new_product = {
                "category": request.form.get('category'),
                "type": request.form.get('type'),
                "size": [s.strip() for s in request.form.get('size').split(',')],
                "color": [c.strip() for c in request.form.get('color').split(',')],
                "image": request.form.get('image'),
                "price": int(request.form.get('price'))
            }
            messageHandler.products.append(new_product)
            flash("Product added successfully!", "success")
            update_github_repo(messageHandler.products)
        elif action == 'edit':
            product_index = int(request.form.get('product_index'))
            messageHandler.products[product_index] = {
                "category": request.form.get('category'),
                "type": request.form.get('type'),
                "size": [s.strip() for s in request.form.get('size').split(',')],
                "color": [c.strip() for c in request.form.get('color').split(',')],
                "image": request.form.get('image'),
                "price": int(request.form.get('price'))
            }
            flash("Product updated successfully!", "success")
            update_github_repo(messageHandler.products)
        elif action == 'remove':
            product_index = int(request.form.get('product_index'))
            # Get the product image URL before removing the product
            product_image = messageHandler.products[product_index]['image']
            # Remove the product
            messageHandler.products.pop(product_index)
            flash("Product removed successfully!", "success")
            update_github_repo(messageHandler.products)
            
            # Delete the associated image if it exists
            if product_image:
                try:
                    response = requests.post(
                        'https://ezbo.org/product-image/uploader.php?token=123456',
                        data={'action': 'remove', 'image_url': product_image}
                    )
                    if response.status_code != 200:
                        logger.error(f"Failed to delete image: {response.text}")
                except Exception as e:
                    logger.error(f"Error deleting product image: {str(e)}")

        return redirect(url_for('stock_lists'))

    categories = set(product['category'] for product in messageHandler.products)
    colors = set(color for product in messageHandler.products for color in product['color'])

    return render_template(
        'stocklists.html',
        title="Stock Lists",
        products=messageHandler.products,
        settings=messageHandler.get_settings(),
        categories=categories,
        colors=colors
    )
    
@app.route('/shipsetup', methods=['GET', 'POST'])
@login_required
def ship_setup():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            new_record = {
                'country': request.form.get('country'),
                'region': request.form.get('region'),
                'delivery_time': request.form.get('delivery_time'),
                'delivery_charge': int(request.form.get('delivery_charge'))
            }
            settings = messageHandler.get_settings()
            settings['delivery_records'].append(new_record)
            messageHandler.update_settings(delivery_records=settings['delivery_records'])
            update_github_repo_settings(settings)
            flash("Delivery record added successfully!", "success")
        elif action == 'edit':
            record_index = int(request.form.get('record_index'))
            settings = messageHandler.get_settings()
            settings['delivery_records'][record_index] = {
                'country': request.form.get('country'),
                'region': request.form.get('region'),
                'delivery_time': request.form.get('delivery_time'),
                'delivery_charge': int(request.form.get('delivery_charge'))
            }
            messageHandler.update_settings(delivery_records=settings['delivery_records'])
            update_github_repo_settings(settings)
            flash("Delivery record updated successfully!", "success")
        elif action == 'remove':
            record_index = int(request.form.get('record_index'))
            settings = messageHandler.get_settings()
            settings['delivery_records'].pop(record_index)
            messageHandler.update_settings(delivery_records=settings['delivery_records'])
            update_github_repo_settings(settings)
            flash("Delivery record removed successfully!", "success")
        return redirect(url_for('ship_setup'))

    return render_template('shipsetup.html', title="Ship Setup", settings=messageHandler.get_settings())

@app.route('/aisettings', methods=['GET', 'POST'])
@login_required
def ai_settings():
    if request.method == 'POST':
        new_shop_name = request.form.get('shop_name')
        new_shop_number = request.form.get('shop_number')
        new_shop_email = request.form.get('shop_email')
        new_currency = request.form.get('selectedCurrency')
        new_ai_name = request.form.get('ai_name')
        cod_enabled = request.form.get('cod_enabled') == 'on'
        bkash_enabled = request.form.get('bkash_enabled') == 'on'
        nagad_enabled = request.form.get('nagad_enabled') == 'on'
        paypal_enabled = request.form.get('paypal_enabled') == 'on'
        
        if not cod_enabled and not bkash_enabled and not nagad_enabled and not paypal_enabled:
            flash("You must enable at least one payment method.", "error")
            return redirect(url_for('ai_settings'))
        
        service_products = request.form.get('service_products')
        return_policy = request.form.get('return_policy')
        
        payment_methods = {
            "cod": cod_enabled,
            "bkash": bkash_enabled,
            "nagad": nagad_enabled,
            "bkash_number": request.form.get('bkash_number'),
            "nagad_number": request.form.get('nagad_number'),
            "bkash_type": request.form.get('bkash_type'),
            "nagad_type": request.form.get('nagad_type'),
            "paypal": paypal_enabled,
            "paypal_email": request.form.get('paypal_email')
        }
        
        messageHandler.update_settings(
            shop_name=new_shop_name,
            shop_number=new_shop_number,
            shop_email=new_shop_email,
            currency=new_currency,
            ai_name=new_ai_name,
            payment_methods=payment_methods,
            service_products=service_products,
            return_policy=return_policy
        )

        update_github_repo_settings(messageHandler.get_settings())

        flash("Settings updated successfully!", "success")
        return redirect(url_for('ai_settings'))

    return render_template('aisettings.html', title="AI Settings", settings=messageHandler.get_settings(), AI_ENABLED=AI_ENABLED)

@app.route('/api', methods=['GET'])
def api():
    query = request.args.get('query')
    if not query:
        return jsonify({"error": "No query provided"}), 400
   
    response, _ = messageHandler.handle_text_message(query, last_message=None)
   
    return jsonify(response) 

@app.route('/api2', methods=['GET'])
def api2():
    user_query = request.args.get('query')
    if not user_query:
        return jsonify({"error": "No query provided"}), 400
   
    response_1, response_2 = query(user_query)
   
    return jsonify({"bing_response": response_1, "google_response": response_2}) 

def send_order_notification(order):
    try:
        # Get email configuration
        smtp_server = os.getenv("SMTP_SERVER")
        smtp_port = int(os.getenv("SMTP_PORT"))
        smtp_username = os.getenv("SMTP_USERNAME")
        smtp_password = os.getenv("SMTP_PASSWORD")
        email_from = os.getenv("EMAIL_FROM")
        
        # Get shop email from settings
        settings = messageHandler.get_settings()
        email_to = settings['shop_email']
        
        if not email_to:
            logger.error("No shop email configured in settings")
            return False

        # Create message
        msg = MIMEMultipart('alternative')
        msg['From'] = email_from
        msg['To'] = email_to
        msg['Subject'] = f"a!Panel - New Order Received : {order['product']}"

        # Email body - HTML version
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>New Order Notification</title>
            <style>
                body {{
                    font-family: 'Arial', sans-serif;
                    line-height: 1.6;
                    color: #333;
                    margin: 0;
                    padding: 0;
                    background-color: #f5f5f5;
                }}
                .container {{
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: #ffffff;
                    border-radius: 5px;
                    box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
                }}
                .content {{
                    padding: 20px;
                }}
                .order-details {{
                    background-color: #1a1a1a;
                    color: #ffffff;
                    padding: 15px;
                    border-radius: 5px;
                    margin-bottom: 20px;
                }}
                .order-details h2 {{
                    color: #00ffff;
                    margin-top: 0;
                }}
                .detail-row {{
                    display: flex;
                    margin-bottom: 10px;
                }}
                .detail-label {{
                    font-weight: bold;
                    color: #00ffff;
                    width: 150px;
                }}
                .detail-value {{
                    flex: 1;
                }}
                .footer {{
                    text-align: center;
                    padding: 20px;
                    font-size: 12px;
                    color: #777;
                }}
                .status-badge {{
                    display: inline-block;
                    padding: 5px 10px;
                    background-color: #00ffff;
                    color: #0a0a0a;
                    border-radius: 20px;
                    font-weight: bold;
                    font-size: 14px;
                }}
                @media only screen and (max-width: 600px) {{
                    .container {{
                        width: 100%;
                        border-radius: 0;
                    }}
                    .detail-row {{
                        flex-direction: column;
                    }}
                    .detail-label {{
                        width: 100%;
                        margin-bottom: 5px;
                    }}
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="content">
                    <h1 style="color: #000000;">New Order Received</h1>
                    <p>Hello {settings['shop_name']} team,</p>
                    <p>You have received a new order through your a!Panel. Please find the details below:</p>
                    
                    <div class="order-details">
                        <h2>Order Summary</h2>
                        <div class="detail-row">
                            <div class="detail-label">Customer Name:</div>
                            <div class="detail-value">{order['name']}</div>
                        </div>
                        <div class="detail-row">
                            <div class="detail-label">Mobile:</div>
                            <div class="detail-value">{order['mobile']}</div>
                        </div>
                        <div class="detail-row">
                            <div class="detail-label">Address:</div>
                            <div class="detail-value">{order['address']}</div>
                        </div>
                        <div class="detail-row">
                            <div class="detail-label">Product:</div>
                            <div class="detail-value">{order['product']}</div>
                        </div>
                        <div class="detail-row">
                            <div class="detail-label">Price:</div>
                            <div class="detail-value">{order['price']}{settings['currency']}</div>
                        </div>
                        <div class="detail-row">
                            <div class="detail-label">Delivery Charge:</div>
                            <div class="detail-value">{order['delivery_charge']}{settings['currency']}</div>
                        </div>
                        <div class="detail-row">
                            <div class="detail-label">Total:</div>
                            <div class="detail-value">{order['total']}{settings['currency']}</div>
                        </div>
                        <div class="detail-row">
                            <div class="detail-label">Payment Method:</div>
                            <div class="detail-value">
                                {order['payment_method']}
                                {f"(Txn ID: {order['transaction_id']})" if 'transaction_id' in order else ""}
                            </div>
                        </div>
                        <div class="detail-row">
                            <div class="detail-label">Status:</div>
                            <div class="detail-value">
                                <span class="status-badge">{order['status']}</span>
                            </div>
                        </div>
                        <div class="detail-row">
                            <div class="detail-label">Date:</div>
                            <div class="detail-value">{order['date']}</div>
                        </div>
                    </div>
                    
                    <p>Please process this order as soon as possible.</p>
                    <p>Thank you for using a!Panel!</p>
                </div>
                
                <div class="footer">
                    <p>This is an automated message from a!Panel. Please do not reply to this email.</p>
                    <p>&copy; {datetime.datetime.now().year} a!Panel. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """

        # Plain text version for email clients that don't support HTML
        text = f"""
        New Order Notification - a!Panel
        ================================

        Shop: {settings['shop_name']}
        Customer Name: {order['name']}
        Mobile: {order['mobile']}
        Address: {order['address']}
        Product: {order['product']}
        Price: {order['price']}{settings['currency']}
        Delivery Charge: {order['delivery_charge']}{settings['currency']}
        Total: {order['total']}{settings['currency']}
        Payment Method: {order['payment_method']}{f" (Txn ID: {order['transaction_id']})" if 'transaction_id' in order else ""}
        Status: {order['status']}
        Date: {order['date']}

        Please process this order as soon as possible.

        This is an automated message from a!Panel.
        """

        # Attach both HTML and plain text versions
        part1 = MIMEText(text, 'plain')
        part2 = MIMEText(html, 'html')
        msg.attach(part1)
        msg.attach(part2)

        # Send email
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.send_message(msg)
        
        logger.info(f"Order notification email sent to shop email: {email_to}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send order notification email: {str(e)}")
        return False

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=3000)
