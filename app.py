from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, Response, session
import os
import logging
from flask_cors import CORS
import requests
import messageHandler
from github import Github
from functools import wraps
import hashlib
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import send_from_directory
import datetime
import tempfile
import shutil
import uuid
import json
import threading
import telegram_bot
import discord_bot
import page_bot

load_dotenv()

app = Flask(__name__)
CORS(app)
app.secret_key = os.getenv("SECRET_KEY", "supersecretkey")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

GITHUB_ACCESS_TOKEN = os.getenv("GITHUB_ACCESS_TOKEN")
GITHUB_REPO_NAME = os.getenv("GITHUB_REPO_NAME")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

github = Github(GITHUB_ACCESS_TOKEN)
repo = github.get_repo(GITHUB_REPO_NAME)

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
    if page_bot.verify_webhook(token_sent):
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
    page_bot.handle_facebook_message(data)
    return "EVENT_RECEIVED", 200

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
            messageHandler.update_github_repo_orders(messageHandler.get_orders())
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
        messageHandler.update_github_repo_orders(messageHandler.get_orders())
        return redirect(url_for('order_lists'))
    
    return render_template('vieworder.html', title="View Order", order=order, order_index=order_index, settings=messageHandler.get_settings())

@app.route('/saleslogs')
@login_required
def sales_logs():
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

@app.route('/download/saleslog')
@login_required
def download_saleslog():
    try:
        temp_dir = tempfile.mkdtemp()
        filename = f"sales_log_{uuid.uuid4().hex}.txt"
        filepath = os.path.join(temp_dir, filename)
        
        with open(filepath, 'w') as f:
            for log in messageHandler.sales_logs:
                f.write(f"Name: {log.get('name', 'N/A')}\n")
                f.write(f"Mobile: {log.get('mobile', 'N/A')}\n")
                f.write(f"Address: {log.get('address', 'N/A')}\n")
                f.write(f"Product: {log.get('product', 'N/A')}\n")
                f.write(f"Price: {log.get('price', 'N/A')}{messageHandler.get_settings().get('currency', '')}\n")
                f.write(f"Delivery Charge: {log.get('delivery_charge', 'N/A')}{messageHandler.get_settings().get('currency', '')}\n")
                f.write(f"Total: {log.get('total', 'N/A')}{messageHandler.get_settings().get('currency', '')}\n")
                f.write(f"Payment Method: {log.get('payment_method', 'N/A')}\n")
                if log.get('transaction_id'):
                    f.write(f"Transaction ID: {log.get('transaction_id', 'N/A')}\n")
                f.write(f"Status: {log.get('status', 'N/A')}\n")
                f.write(f"Date: {log.get('date', 'N/A')}\n")
                f.write("\n" + "="*50 + "\n\n")
        
        response = send_from_directory(
            temp_dir,
            filename,
            as_attachment=True,
            mimetype='text/plain'
        )
        
        response.call_on_close(lambda: shutil.rmtree(temp_dir, ignore_errors=True))
        return response
    except Exception as e:
        logger.error(f"Error generating sales log download: {str(e)}")
        flash("Error generating download file", "error")
        return redirect(url_for('sales_logs'))

@app.route('/download/saleslog/<int:order_index>')
@login_required
def download_single_order(order_index):
    try:
        if order_index < 0 or order_index >= len(messageHandler.sales_logs):
            flash("Invalid order index", "error")
            return redirect(url_for('sales_logs'))
            
        temp_dir = tempfile.mkdtemp()
        filename = f"order_{order_index}_{uuid.uuid4().hex}.txt"
        filepath = os.path.join(temp_dir, filename)
        
        log = messageHandler.sales_logs[order_index]
        with open(filepath, 'w') as f:
            f.write(f"Name: {log.get('name', 'N/A')}\n")
            f.write(f"Mobile: {log.get('mobile', 'N/A')}\n")
            f.write(f"Address: {log.get('address', 'N/A')}\n")
            f.write(f"Product: {log.get('product', 'N/A')}\n")
            f.write(f"Price: {log.get('price', 'N/A')}{messageHandler.get_settings().get('currency', '')}\n")
            f.write(f"Delivery Charge: {log.get('delivery_charge', 'N/A')}{messageHandler.get_settings().get('currency', '')}\n")
            f.write(f"Total: {log.get('total', 'N/A')}{messageHandler.get_settings().get('currency', '')}\n")
            f.write(f"Payment Method: {log.get('payment_method', 'N/A')}\n")
            if log.get('transaction_id'):
                f.write(f"Transaction ID: {log.get('transaction_id', 'N/A')}\n")
            f.write(f"Status: {log.get('status', 'N/A')}\n")
            f.write(f"Date: {log.get('date', 'N/A')}\n")
            
        response = send_from_directory(
            temp_dir,
            filename,
            as_attachment=True,
            mimetype='text/plain'
        )
        
        response.call_on_close(lambda: shutil.rmtree(temp_dir, ignore_errors=True))
        return response
    except Exception as e:
        logger.error(f"Error generating single order download: {str(e)}")
        flash("Error generating download file", "error")
        return redirect(url_for('sales_logs'))

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
            messageHandler.add_product(new_product)
            flash("Product added successfully!", "success")
        elif action == 'edit':
            product_index = int(request.form.get('product_index'))
            messageHandler.update_product(product_index, {
                "category": request.form.get('category'),
                "type": request.form.get('type'),
                "size": [s.strip() for s in request.form.get('size').split(',')],
                "color": [c.strip() for c in request.form.get('color').split(',')],
                "image": request.form.get('image'),
                "price": int(request.form.get('price'))
            })
            flash("Product updated successfully!", "success")
        elif action == 'remove':
            product_index = int(request.form.get('product_index'))
            product_image = messageHandler.products[product_index]['image']
            messageHandler.remove_product(product_index)
            flash("Product removed successfully!", "success")
            
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
            messageHandler.update_github_repo_settings(settings)
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
            messageHandler.update_github_repo_settings(settings)
            flash("Delivery record updated successfully!", "success")
        elif action == 'remove':
            record_index = int(request.form.get('record_index'))
            settings = messageHandler.get_settings()
            settings['delivery_records'].pop(record_index)
            messageHandler.update_settings(delivery_records=settings['delivery_records'])
            messageHandler.update_github_repo_settings(settings)
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

        messageHandler.update_github_repo_settings(messageHandler.get_settings())

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
        smtp_server = os.getenv("SMTP_SERVER")
        smtp_port = int(os.getenv("SMTP_PORT"))
        smtp_username = os.getenv("SMTP_USERNAME")
        smtp_password = os.getenv("SMTP_PASSWORD")
        email_from = os.getenv("EMAIL_FROM")
        
        settings = messageHandler.get_settings()
        email_to = settings['shop_email']
        
        if not email_to:
            logger.error("No shop email configured in settings")
            return False

        msg = MIMEMultipart('alternative')
        msg['From'] = email_from
        msg['To'] = email_to
        msg['Subject'] = f"a!Panel - New Order Received : {order['product']}"

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

        part1 = MIMEText(text, 'plain')
        part2 = MIMEText(html, 'html')
        msg.attach(part1)
        msg.attach(part2)

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
    # Start Flask app in a separate thread
    flask_thread = threading.Thread(
        target=app.run,
        kwargs={'debug': True, 'host': '0.0.0.0', 'port': 3000, 'use_reloader': False}
    )
    flask_thread.daemon = True
    flask_thread.start()
    
    # Start Discord bot in a separate thread
    discord_thread = threading.Thread(target=discord_bot.run_discord_bot)
    discord_thread.daemon = True
    discord_thread.start()
    
    # Start Telegram bot in main thread
    telegram_bot.main()
    
    # Start Facebook Page bot
    page_bot.run_page_bot()
