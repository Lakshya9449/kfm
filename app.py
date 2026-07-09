import os
import sqlite3
import json
from flask import Flask, render_template_string, request, redirect, session, url_for, flash
import qrcode
import io
import base64

app = Flask(__name__)
app.secret_key = 'super_secret_grocery_key_2026'

# Centralized data file path setup
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE = os.path.join(BASE_DIR, 'grocery.db')

# Configured directly for your live Render application url
PRODUCTION_STORE_URL = "https://kfm-cjav.onrender.com/customer"

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Products Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            name TEXT NOT NULL,
            mrp REAL NOT NULL,
            sale_price REAL NOT NULL,
            instructions TEXT,
            stock INTEGER DEFAULT 10
        )
    ''')
    
    # 2. Orders Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT NOT NULL,
            address TEXT NOT NULL,
            items_json TEXT NOT NULL,
            total_amount REAL NOT NULL,
            order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] == 0:
        cursor.executemany('''
            INSERT INTO products (category, name, mrp, sale_price, instructions, stock)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', [
            ('Oils', 'Fortune Mustard Oil 1L', 190.00, 175.00, 'Store in a cool dry place.', 15),
            ('Oils', 'Hathi Mustard Oil 1L', 200.00, 178.00, 'Perfect for traditional Indian cooking.', 8),
            ('Spices', 'Catch Turmeric Powder 200g', 60.00, 52.00, 'Keep airtight after opening.', 25),
            ('Dairy', 'Milk 1L', 190.00, 175.00, 'Store in a cool dry place.', 20),
            ('Dairy', 'Cheese 200g', 190.00, 175.00, 'Store in a cool dry place.', 5),
            ('Atta', 'Aashirwad Atta 10kg', 190.00, 175.00, 'Store in a cool dry place.', 12)
        ])
    conn.commit()
    conn.close()

def query_db(query, args=(), one=False):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(query, args)
    rv = cur.fetchall()
    conn.commit()
    conn.close()
    return (rv[0] if rv else None) if one else rv

def generate_qr_base64():
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(PRODUCTION_STORE_URL)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def calculate_delivery_charge(cart_total):
    """
    Implements a decreasing percentage delivery curve.
    At very low order values, the percentage is higher.
    As order value reaches closer to 1500, it drops down smoothly towards 0.
    At 1500 or more, delivery is completely free.
    """
    if cart_total >= 1500 or cart_total <= 0:
        return 0.0
    
    # Formula creates a smooth curve that scales down gracefully as value rises
    # Base fee scales dynamically according to the remaining gap to reach free delivery
    raw_charge = (1500 - cart_total) * 0.05 + 15.0
    return round(raw_charge, 2)

# --- MAIN BASE HTML TEMPLATE ---
HTML_TEMPLATE_BASE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Smart Grocery Store</title>
    <style>
        :root { --primary: #2e7d32; --secondary: #388e3c; --bg: #f1f8e9; --danger: #c62828; --warning: #f57c00; }
        body { font-family: 'Segoe UI', system-ui, sans-serif; margin: 0; padding: 20px; background: var(--bg); color: #333; }
        header { display: flex; align-items: center; justify-content: space-between; background: var(--primary); color: white; padding: 15px 20px; border-radius: 8px; margin-bottom: 20px; position: relative; }
        header h1 { margin: 0; font-size: 22px; display: flex; align-items: center; gap: 10px; }
        .menu-btn { background: none; border: none; color: white; font-size: 24px; cursor: pointer; padding: 5px; }
        .nav-menu { position: fixed; top: 0; left: -280px; width: 280px; height: 100%; background: white; box-shadow: 4px 0 10px rgba(0,0,0,0.1); z-index: 1000; transition: 0.3s ease; padding: 20px; box-sizing: border-box; }
        .nav-menu.active { left: 0; }
        .nav-overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.4); z-index: 999; display: none; }
        .nav-overlay.active { display: block; }
        .nav-menu h3 { margin-top: 0; border-bottom: 2px solid var(--primary); padding-bottom: 10px; color: var(--primary); }
        .nav-menu a { display: block; padding: 12px 10px; color: #333; text-decoration: none; border-radius: 4px; margin-bottom: 5px; font-weight: 500; }
        .nav-menu a:hover { background: #e8f5e9; color: var(--primary); }
        .container { max-width: 900px; margin: 0 auto; }
        .card-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 20px; }
        .card { background: white; padding: 25px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); text-align: center; border: 1px solid #e0e0e0; display: flex; flex-direction: column; justify-content: space-between; }
        .card-click { cursor: pointer; width: 100%; }
        .card:hover { transform: translateY(-3px); box-shadow: 0 6px 12px rgba(0,0,0,0.1); transition: 0.2s; }
        .btn { background: var(--primary); color: white; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer; font-weight: 600; text-decoration: none; display: inline-block; text-align: center; }
        .btn-back { background: #616161; margin-bottom: 20px; }
        .btn-disabled { background: #bdc3c7; cursor: not-allowed; }
        .btn-edit { background: #ff9100; color: white; padding: 4px 10px; font-size: 13px; border-radius: 4px; text-decoration: none; }
        .price-tag { font-size: 24px; color: var(--primary); font-weight: bold; margin: 10px 0; }
        .mrp { text-decoration: line-through; color: #757575; font-size: 16px; }
        .badge { background: var(--danger); color: white; padding: 4px 8px; font-size: 12px; border-radius: 4px; font-weight: bold; display: inline-block; }
        .badge-success { background: var(--primary); }
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; font-weight: bold; }
        input, textarea, select { width: 100%; padding: 10px; border: 1px solid #ccc; border-radius: 6px; box-sizing: border-box; }
        .qty-input { width: 80px; text-align: center; display: inline-block; margin-right: 10px; }
        .alert { background: #ffcdd2; color: #b71c1c; padding: 12px; border-radius: 6px; margin-bottom: 20px; border-left: 5px solid var(--danger); }
        .alert-info { background: #e3f2fd; color: #0d47a1; border-left: 5px solid #2196f3; }
        .alert-warning { background: #fff3e0; color: #e65100; border-left: 5px solid var(--warning); }
        table { width: 100%; border-collapse: collapse; margin-top: 15px; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
        th, td { padding: 12px 15px; text-align: left; border-bottom: 1px solid #eee; }
        th { background: #e8f5e9; color: var(--primary); font-weight: bold; }
        .report-box { display: flex; gap: 20px; margin-bottom: 30px; }
        .report-card { background: white; padding: 20px; border-radius: 8px; flex: 1; box-shadow: 0 2px 4px rgba(0,0,0,0.05); text-align: center; border-top: 4px solid var(--primary); }
    </style>
</head>
<body>
    <div class="nav-overlay" id="navOverlay" onclick="toggleMenu()"></div>
    <div class="nav-menu" id="navMenu">
        <h3>Store Navigation</h3>
        <a href="/customer">🏪 Shop Categories</a>
        <a href="/cart">🛒 View Shopping Cart</a>
        <hr style="border:0; border-top: 1px solid #eee; margin: 15px 0;">
        {% if is_logged_in %}
            <a href="/admin/dashboard">📊 Admin Dashboard</a>
            <a href="/logout">🚪 Logout</a>
        {% else %}
            <a href="/admin/login">🔑 Admin Login</a>
        {% endif %}
    </div>

    <div class="container">
        <header>
            <button class="menu-btn" onclick="toggleMenu()">☰</button>
            <h1>🏪 Khandelwal Food Mart</h1>
            <a href="/cart" style="color: white; text-decoration: none; font-weight: bold;">🛒 Cart</a>
        </header>

        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}
            {% for category, msg in messages %}
              <div class="alert {% if category == 'info' %}alert-info{% endif %}">{{ msg }}</div>
            {% endfor %}
          {% endif %}
        {% endwith %}

        {{ view_content | safe }}
    </div>

    <script>
        function toggleMenu() {
            document.getElementById('navMenu').classList.toggle('active');
            document.getElementById('navOverlay').classList.toggle('active');
        }
    </script>
</body>
</html>
"""

def render_store_page(view_content_template, context_data=None):
    if context_data is None:
        context_data = {}
    context_data['is_logged_in'] = session.get('logged_in', False)
    full_compiled_page = HTML_TEMPLATE_BASE.replace("{{ view_content | safe }}", view_content_template)
    return render_template_string(full_compiled_page, **context_data)

# --- CUSTOMER ENDPOINTS ---

@app.route('/')
def index():
    return redirect(url_for('customer_home'))

@app.route('/customer')
def customer_home():
    try:
        init_db()
    except Exception as e:
        pass

    cats = query_db('SELECT DISTINCT category FROM products')
    categories_list = [row['category'] for row in cats]
    qr_img = generate_qr_base64()
    
    content = """
    <h2>Select a Category</h2>
    <div class="card-grid">
        {% for cat in categories %}
            <div class="card" style="cursor: pointer;" onclick="location.href='/customer/category/{{ cat }}'">
                <h3>{{ cat }}</h3>
                <p style="color: var(--secondary);">Browse Products →</p>
            </div>
        {% endfor %}
    </div>
    
    <div style="background: white; padding: 30px; border-radius: 12px; text-align: center; max-width: 400px; margin: 40px auto; box-shadow: 0 4px 6px rgba(0,0,0,0.05);">
        <h3>Your Shop QR Code</h3>
        <img src="data:image/png;base64,{{ qr_img }}" alt="Scan QR Code" style="width:200px;height:200px;"/>
        <p style="font-size:12px; color:#666;">Scan with your phone camera to share the store menu!</p>
    </div>
    """
    return render_store_page(content, {'categories': categories_list, 'qr_img': qr_img})

@app.route('/customer/category/<cat_name>')
def customer_category(cat_name):
    prods = query_db('SELECT * FROM products WHERE category = ?', [cat_name])
    content = """
    <a href="/customer" class="btn btn-back">← Back to Categories</a>
    <h2>{{ current_category }} Items</h2>
    <div class="card-grid">
        {% for prod in data %}
            <div class="card">
                <div class="card-click" onclick="location.href='/customer/product/{{ prod[\'id\'] }}'">
                    <h3>{{ prod[\'name\'] }}</h3>
                    <div class="price-tag">₹{{ prod[\'sale_price\'] }}</div>
                    {% if prod[\'stock\'] <= 0 %}
                        <span class="badge" style="margin-bottom:15px;">Out of Stock</span>
                    {% else %}
                        <span class="badge badge-success" style="margin-bottom:15px;">In Stock</span>
                    {% endif %}
                </div>
                
                {% if prod[\'stock\'] > 0 %}
                    <form action="/cart/add/{{ prod[\'id\'] }}" method="post">
                        <input type="hidden" name="quantity" value="1">
                        <button type="submit" class="btn" style="width:100%;">🛒 Add to Cart</button>
                    </form>
                {% endif %}
            </div>
        {% endfor %}
    </div>
    """
    return render_store_page(content, {'data': prods, 'current_category': cat_name})

@app.route('/customer/product/<int:prod_id>')
def customer_product(prod_id):
    prod = query_db('SELECT * FROM products WHERE id = ?', [prod_id], one=True)
    content = """
    <a href="/customer/category/{{ data[\'category\'] }}" class="btn btn-back">← Back to Product List</a>
    <div class="card" style="text-align: left;">
        <h2 style="margin-top:10px;">{{ data[\'name\'] }}</h2>
        <hr style="border: 0; border-top: 1px solid #eee;">
        <div class="price-tag">Special Price: ₹{{ data[\'sale_price\'] }}</div>
        <div class="mrp">Normal MRP: ₹{{ data[\'mrp\'] }}</div>
        
        <h3 style="margin-top: 25px; color: var(--secondary);">Instructions:</h3>
        <p style="line-height: 1.6; background: #fafafa; padding: 15px; border-left: 4px solid var(--primary); margin-bottom: 25px;">{{ data[\'instructions\'] }}</p>
        
        {% if data[\'stock\'] <= 0 %}
            <div class="badge" style="font-size: 16px; padding: 10px;">⚠️ Currently Out of Stock</div>
        {% else %}
            <form action="/cart/add/{{ data[\'id\'] }}" method="post" style="background: #f9f9f9; padding: 15px; border-radius: 8px; display: inline-block;">
                <label for="quantity" style="display:inline; margin-right:10px;">Quantity:</label>
                <input type="number" name="quantity" id="quantity" class="qty-input" value="1" min="1" max="{{ data[\'stock\'] }}">
                <button type="submit" class="btn">🛒 Add to Cart</button>
            </form>
        {% endif %}
    </div>
    """
    return render_store_page(content, {'data': prod})

@app.route('/cart')
def view_cart():
    cart = session.get('cart', {})
    cart_items = []
    cart_total = 0.0
    
    if cart:
        placeholders = ','.join('?' for _ in cart.keys())
        products = query_db(f'SELECT * FROM products WHERE id IN ({placeholders})', list(map(int, cart.keys())))
        for p in products:
            p_id = str(p['id'])
            qty = int(cart[p_id])
            total_item_cost = p['sale_price'] * qty
            cart_total += total_item_cost
            cart_items.append({
                'id': p['id'], 'name': p['name'], 'price': p['sale_price'],
                'qty': qty, 'total': round(total_item_cost, 2)
            })
            
    delivery_charge = calculate_delivery_charge(cart_total)
    delivery_percentage = round((delivery_charge / cart_total * 100), 1) if cart_total > 0 else 0
    grand_total = round(cart_total + delivery_charge, 2)
    
    content = """
    <h2>🛒 Your Shopping Cart</h2>
    {% if not cart_items %}
        <div class="card" style="padding: 40px; text-align: center;">
            <h3>Your cart is empty!</h3>
            <a href="/customer" class="btn" style="margin-top: 15px;">Start Browsing Products</a>
        </div>
    {% else %}
        
        {% if cart_total < 1500 %}
            <div class="alert alert-warning" style="font-weight: 600; font-size: 15px; text-align: center;">
                💡 Shop for <strong>₹{{ round(1500 - cart_total, 2) }}</strong> more to unlock <strong>FREE Delivery!</strong><br>
                <span style="font-size: 13px; font-weight: normal; color: #555;">(Orders above ₹1500 are completely free)</span>
            </div>
        {% else %}
            <div class="alert alert-info" style="font-weight: 600; font-size: 15px; text-align: center; border-left: 5px solid var(--primary);">
                🎉 Congratulations! Your order qualifies for <strong>FREE Delivery</strong>.
            </div>
        {% endif %}

        <table>
            <thead>
                <tr>
                    <th>Item Name</th>
                    <th>Price</th>
                    <th>Quantity</th>
                    <th>Total</th>
                    <th>Action</th>
                </tr>
            </thead>
            <tbody>
                {% for item in cart_items %}
                <tr>
                    <td>{{ item.name }}</td>
                    <td>₹{{ item.price }}</td>
                    <td>{{ item.qty }}</td>
                    <td>₹{{ item.total }}</td>
                    <td><a href="/cart/remove/{{ item.id }}" style="color: var(--danger); text-decoration: none; font-weight: bold;">Remove</a></td>
                </tr>
                {% endfor %}
                <tr style="background: #fafafa;">
                    <td colspan="3" style="text-align: right; font-weight: bold;">Items Subtotal:</td>
                    <td colspan="2" style="font-weight: bold;">₹{{ cart_total }}</td>
                </tr>
                <tr style="background: #fafafa;">
                    <td colspan="3" style="text-align: right; font-weight: bold;">
                        Delivery Charges: 
                        {% if cart_total < 1500 %}
                            <span style="font-size: 11px; font-weight: normal; color: #e65100;">({{ delivery_percentage }}% rate applied)</span>
                        {% endif %}
                    </td>
                    <td colspan="2" style="font-weight: bold; color: {% if delivery_charge == 0 %}var(--primary){% else %}var(--warning){% endif %};">
                        {% if delivery_charge == 0 %}FREE{% else %}+ ₹{{ delivery_charge }}{% endif %}
                    </td>
                </tr>
                <tr style="font-weight: bold; background: #f0fdf4;">
                    <td colspan="3" style="text-align: right; font-size: 16px;">Total Payable Amount:</td>
                    <td colspan="2" style="color: var(--primary); font-size: 20px;">₹{{ grand_total }}</td>
                </tr>
            </tbody>
        </table>

        <div class="card" style="text-align: left; margin-top: 30px;">
            <h3>🚚 Cash on Delivery (COD) Home Delivery</h3>
            <form action="/cart/checkout" method="post" style="margin-top: 15px;">
                <div class="form-group">
                    <label>Mobile Phone Number</label>
                    <input type="tel" name="phone" placeholder="Enter 10-digit mobile number" required>
                </div>
                <div class="form-group">
                    <label>Full Delivery Address</label>
                    <textarea name="address" rows="3" placeholder="Enter your full home drop-off location address" required></textarea>
                </div>
                <button type="submit" class="btn" style="width: 100%; background: var(--secondary); font-size: 16px; padding: 12px;">📦 Place Cash on Delivery Order</button>
            </form>
        </div>
    {% endif %}
    """
    return render_store_page(content, {
        'cart_items': cart_items, 
        'cart_total': round(cart_total, 2), 
        'delivery_charge': delivery_charge,
        'delivery_percentage': delivery_percentage,
        'grand_total': grand_total,
        'round': round
    })

@app.route('/cart/add/<int:prod_id>', methods=['POST'])
def add_to_cart(prod_id):
    quantity = int(request.form.get('quantity', 1))
    prod = query_db('SELECT * FROM products WHERE id = ?', [prod_id], one=True)
    
    if not prod or prod['stock'] <= 0:
        flash("Sorry, this item is currently out of stock!", "error")
        return redirect(request.referrer or url_for('customer_home'))
        
    cart = session.get('cart', {})
    current_in_cart = cart.get(str(prod_id), 0)
    new_quantity = current_in_cart + quantity
    
    if new_quantity > prod['stock']:
        flash(f"Cannot add requested amount. Inventory limit exceeded.", "error")
        cart[str(prod_id)] = prod['stock']
    else:
        cart[str(prod_id)] = new_quantity
        flash(f"Added {quantity} x {prod['name']} to your cart!", "info")
        
    session['cart'] = cart
    session.modified = True
    
    return redirect(request.referrer or url_for('customer_home'))

@app.route('/cart/remove/<string:prod_id>')
def remove_from_cart(prod_id):
    cart = session.get('cart', {})
    if prod_id in cart:
        cart.pop(prod_id)
    session['cart'] = cart
    flash("Item removed from your basket.", "info")
    return redirect(url_for('view_cart'))

@app.route('/cart/checkout', methods=['POST'])
def checkout_cart():
    cart = session.get('cart', {})
    if not cart:
        return redirect(url_for('customer_home'))
        
    phone = request.form.get('phone', '').strip()
    address = request.form.get('address', '').strip()
    
    placeholders = ','.join('?' for _ in cart.keys())
    products = query_db(f'SELECT * FROM products WHERE id IN ({placeholders})', list(map(int, cart.keys())))
    
    cart_total = 0.0
    items_summary_list = []
    
    for p in products:
        p_id = str(p['id'])
        qty = int(cart[p_id])
        if qty > p['stock']:
            flash(f"Stock constraint issue: '{p['name']}' has only {p['stock']} remaining units.", "error")
            return redirect(url_for('view_cart'))
        cart_total += (p['sale_price'] * qty)
        items_summary_list.append(f"{p['name']} (x{qty})")
        
    delivery_charge = calculate_delivery_charge(cart_total)
    grand_final_total = round(cart_total + delivery_charge, 2)
        
    for p in products:
        p_id = str(p['id'])
        qty = int(cart[p_id])
        query_db('UPDATE products SET stock = stock - ? WHERE id = ?', [qty, int(p_id)])
        
    items_summary_str = f"{', '.join(items_summary_list)} | [Delivery Fee: ₹{delivery_charge}]"
    query_db('INSERT INTO orders (phone, address, items_json, total_amount) VALUES (?, ?, ?, ?)', [phone, address, items_summary_str, grand_final_total])
             
    session.pop('cart', None)
    flash("Success! Your Cash on Delivery order has been registered.", "info")
    return redirect(url_for('customer_home'))

# --- ADMIN ENDPOINTS ---

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    error_msg = None
    if request.method == 'POST':
        if request.form['username'] == 'kfm' and request.form['password'] == '114251':
            session['logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        error_msg = 'Incorrect credentials!'
        
    content = """
    <div class="card" style="max-width: 400px; margin: 40px auto; text-align: left;">
        <h2>Admin Management Portal</h2>
        {% if error %}<p style="color:red;">{{ error }}</p>{% endif %}
        <form action="/admin/login" method="post">
            <div class="form-group">
                <label>Admin Username</label>
                <input type="text" name="username" required>
            </div>
            <div class="form-group">
                <label>Password</label>
                <input type="password" name="password" required>
            </div>
            <button type="submit" class="btn" style="width:100%;">Unlock Dashboard</button>
        </form>
    </div>
    """
    return render_store_page(content, {'error': error_msg})

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('admin_login'))
        
    all_products = query_db('SELECT * FROM products ORDER BY category, name')
    orders = query_db('SELECT * FROM orders ORDER BY order_date DESC')
    sales_agg = query_db('SELECT SUM(total_amount) as total, COUNT(id) as count FROM orders', one=True)
    
    report = {
        'total_sales': round(sales_agg['total'], 2) if sales_agg['total'] else 0.0,
        'total_orders': sales_agg['count'] if sales_agg['count'] else 0
    }
    
    content = """
    <h2>📊 Store Administration Panel</h2>
    <div class="report-box">
        <div class="report-card">
            <h3>Gross Store Revenue</h3>
            <p style="font-size: 28px; color: var(--primary); font-weight: bold; margin: 5px 0;">₹{{ report.total_sales }}</p>
            <span style="font-size: 12px; color: #666;">All completed COD deliveries</span>
        </div>
        <div class="report-card">
            <h3>Dispatched Shipments</h3>
            <p style="font-size: 28px; color: var(--secondary); font-weight: bold; margin: 5px 0;">{{ report.total_orders }}</p>
            <span style="font-size: 12px; color: #666;">Total incoming orders recorded</span>
        </div>
    </div>

    <h2>🚚 Incoming Home Delivery Dispatches</h2>
    {% if not active_orders %}
        <p style="background: white; padding: 20px; border-radius: 8px; color: #666;">No customer delivery orders placed yet.</p>
    {% else %}
        {% for order in active_orders %}
            <div class="card" style="text-align: left; margin-bottom: 15px; border-left: 5px solid var(--secondary);">
                <strong>Order #{{ order[\'id\'] }} — Total: ₹{{ order[\'total_amount\'] }}</strong><br>
                <span style="font-size: 13px; color: #666;">Placed Date: {{ order[\'order_date\'] }}</span>
                <p style="margin: 8px 0;">📞 <strong>Phone:</strong> {{ order[\'phone\'] }} | 📍 <strong>Address:</strong> {{ order[\'address\'] }}</p>
                <div style="background: #fcfcfc; padding: 10px; border-radius: 4px; font-size: 14px;">
                    <strong>Basket:</strong> {{ order[\'items_json\'] }}
                </div>
            </div>
        {% endfor %}
    {% endif %}
    
    <hr style="border:0; border-top: 1px solid #ccc; margin: 40px 0;">

    <h2>➕ Add New Catalog Product</h2>
    <div class="card" style="text-align: left; margin-bottom: 30px;">
        <form action="/admin/add" method="post">
            <div class="form-group">
                <label>Product Category</label>
                <input type="text" name="category" placeholder="Oils" required>
            </div>
            <div class="form-group">
                <label>Product Brand Name & Size</label>
                <input type="text" name="name" placeholder="Fortune Premium Mustard Oil 1L" required>
            </div>
            <div class="form-group" style="display: flex; gap: 10px;">
                <div style="flex: 1;">
                    <label>MRP (₹)</label>
                    <input type="number" step="0.01" name="mrp" required>
                </div>
                <div style="flex: 1;">
                    <label>Sale Price (₹)</label>
                    <input type="number" step="0.01" name="sale_price" required>
                </div>
                <div style="flex: 1;">
                    <label>Initial Stock Count</label>
                    <input type="number" name="stock" value="10" min="0" required>
                </div>
            </div>
            <div class="form-group">
                <label>Customer Instructions</label>
                <textarea name="instructions" rows="3" required></textarea>
            </div>
            <button type="submit" class="btn">➕ Add to Digital Menu</button>
        </form>
    </div>

    <h2>Current Inventory Listing (Admin View Only)</h2>
    <table>
        <thead>
            <tr>
                <th>Category</th>
                <th>Name</th>
                <th>Sale Price</th>
                <th>Stock Units</th>
                <th>Action</th>
            </tr>
        </thead>
        <tbody>
            {% for prod in data %}
            <tr>
                <td>{{ prod[\'category\'] }}</td>
                <td>{{ prod[\'name\'] }}</td>
                <td>₹{{ prod[\'sale_price\'] }}</td>
                <td>
                    {% if prod[\'stock\'] <= 0 %}
                        <span class="badge">0 (Out of Stock)</span>
                    {% else %}
                        {{ prod[\'stock\'] }} units
                    {% endif %}
                </td>
                <td><a href="/admin/edit/{{ prod[\'id\'] }}" class="btn-edit">✏️ Edit</a></td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
    """
    return render_store_page(content, {'data': all_products, 'active_orders': orders, 'report': report})

@app.route('/admin/add', methods=['POST'])
def add_product():
    if not session.get('logged_in'):
        return redirect(url_for('admin_login'))
    query_db('INSERT INTO products (category, name, mrp, sale_price, instructions, stock) VALUES (?, ?, ?, ?, ?, ?)',
             [request.form['category'].strip(), request.form['name'].strip(), float(request.form['mrp']), float(request.form['sale_price']), request.form['instructions'].strip(), int(request.form['stock'])])
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/edit/<int:prod_id>')
def edit_product(prod_id):
    if not session.get('logged_in'):
        return redirect(url_for('admin_login'))
    prod = query_db('SELECT * FROM products WHERE id = ?', [prod_id], one=True)
    
    content = """
    <a href="/admin/dashboard" class="btn btn-back">← Back to Dashboard</a>
    <h2>Modify Product & Stock Controls</h2>
    <div class="card" style="text-align: left;">
        <form action="/admin/update/{{ data[\'id\'] }}" method="post">
            <div class="form-group">
                <label>Product Category</label>
                <input type="text" name="category" value="{{ data[\'category\'] }}" required>
            </div>
            <div class="form-group">
                <label>Product Brand Name & Size</label>
                <input type="text" name="name" value="{{ data[\'name\'] }}" required>
            </div>
            <div class="form-group" style="display: flex; gap: 10px;">
                <div style="flex: 1;">
                    <label>MRP (₹)</label>
                    <input type="number" step="0.01" name="mrp" value="{{ data[\'mrp\'] }}" required>
                </div>
                <div style="flex: 1;">
                    <label>Sale Price (₹)</label>
                    <input type="number" step="0.01" name="sale_price" value="{{ data[\'sale_price\'] }}" required>
                </div>
                <div style="flex: 1; background: #fffde7; padding: 5px; border-radius: 6px;">
                    <label style="color: #b76e00;">📦 Warehouse Stock Units</label>
                    <input type="number" name="stock" value="{{ data[\'stock\'] }}" min="0" required>
                </div>
            </div>
            <div class="form-group">
                <label>Customer Instructions</label>
                <textarea name="instructions" rows="3" required>{{ data[\'instructions\'] }}</textarea>
            </div>
            <button type="submit" class="btn" style="background: #ff9100;">💾 Save Changes</button>
        </form>
    </div>
    """
    return render_store_page(content, {'data': prod})

@app.route('/admin/update/<int:prod_id>', methods=['POST'])
def update_product(prod_id):
    if not session.get('logged_in'):
        return redirect(url_for('admin_login'))
    query_db('''
        UPDATE products 
        SET category = ?, name = ?, mrp = ?, sale_price = ?, instructions = ?, stock = ?
        WHERE id = ?
    ''', [
        request.form['category'].strip(), request.form['name'].strip(),
        float(request.form['mrp']), float(request.form['sale_price']),
        request.form['instructions'].strip(), int(request.form['stock']), prod_id
    ])
    return redirect(url_for('admin_dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('customer_home'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)             
