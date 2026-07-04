import os
import sqlite3
from flask import Flask, render_template_string, request, redirect, session, url_for
import qrcode
import io
import base64

app = Flask(__name__)
app.secret_key = 'super_secret_grocery_key_2026'

# Directs your scanned QR code straight to your store menu page
PRODUCTION_STORE_URL = "https://kfm-cjav.onrender.com/customer"

def init_db():
    # If running on Render, use the writable /tmp folder, otherwise use local directory
    db_path = '/tmp/grocery.db' if os.environ.get('RENDER') else 'grocery.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            name TEXT NOT NULL,
            mrp REAL NOT NULL,
            sale_price REAL NOT NULL,
            instructions TEXT
        )
    ''')
    cursor.execute('SELECT COUNT(*) FROM products')
    if cursor.fetchone()[0] == 0:
        cursor.executemany('''
            INSERT INTO products (category, name, mrp, sale_price, instructions)
            VALUES (?, ?, ?, ?, ?)
        ''', [
            ('Oils', 'Fortune Mustard Oil 1L', 190.00, 175.00, 'Store in a cool dry place.'),
            ('Oils', 'Hathi Mustard Oil 1L', 200.00, 178.00, 'Perfect for traditional Indian cooking.'),
            ('Spices', 'Catch Turmeric Powder 200g', 60.00, 52.00, 'Keep airtight after opening.'),
            ('Oils', 'Nav Bhumi Ras Mustard Oil 1L', 190.00, 178.00, 'Store in a cool dry place.'),
            ('Oils', 'Saloni Mustard Oil 1L', 190.00, 180.00, 'Store in a cool dry place.'),
            ('Oils', 'Fortune Mustard Oil 1L', 190.00, 175.00, 'Store in a cool dry place.'),
            ('Spices', 'Mirch 100g', 90.00, 175.00, 'Store in a cool dry place.'),
            ('Spices', 'Dhania 100g', 190.00, 175.00, 'Store in a cool dry place.'),
            ('Spices', 'Catch Turmeric Powder 200g', 60.00, 52.00, 'Keep airtight after opening.'),
            ('Spices', 'Jeera 100g', 190.00, 175.00, 'Store in a cool dry place.'),
            ('Dairy', 'Milk 1L', 190.00, 175.00, 'Store in a cool dry place.'),
            ('Dairy', 'Cheese 200g', 190.00, 175.00, 'Store in a cool dry place.'),
            ('Dairy', 'Butter 250g', 190.00, 175.00, 'Store in a cool dry place.'),
            ('Dairy', 'Yogurt 500g', 190.00, 175.00, 'Store in a cool dry place.'),
            ('Dairy', 'Curd 250g', 190.00, 175.00, 'Store in a cool dry place.'),
            ('Dairy', 'Ghee 250g', 190.00, 175.00, 'Store in a cool dry place.'),
            ('Dairy', 'Cream 250g', 190.00, 175.00, 'Store in a cool dry place.'),
            ('Dairy', 'Buttermilk 500g', 190.00, 175.00, 'Store in a cool dry place.'),
            ('Atta', 'Aashirwad Atta 10kg', 190.00, 175.00, 'Store in a cool dry place.'),
            ('Atta', 'Aashirwad Atta 5kg', 190.00, 175.00, 'Store in a cool dry place.'),
            ('Atta', 'Fortune Atta 10kg', 190.00, 175.00, 'Store in a cool dry place.'),
            ('Atta', 'Fortune Atta 5kg', 190.00, 175.00, 'Store in a cool dry place.'),
            ('Atta', 'Bhajan Atta 10kg', 190.00, 175.00, 'Store in a cool dry place.'),
            ('Atta', 'Bhajan Atta 5kg', 190.00, 175.00, 'Store in a cool dry place.'),
            ('Atta', 'Swastik Atta 10kg', 190.00, 175.00, 'Store in a cool dry place.'),
            ('Atta', 'Swastik Atta 5kg', 190.00, 175.00, 'Store in a cool dry place.')
        ])
    conn.commit()
    conn.close()

def query_db(query, args=(), one=False):
    db_path = '/tmp/grocery.db' if os.environ.get('RENDER') else 'grocery.db'
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
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

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Smart Grocery Store</title>
    <style>
        :root { --primary: #2e7d32; --secondary: #388e3c; --bg: #f1f8e9; }
        body { font-family: 'Segoe UI', system-ui, sans-serif; margin: 0; padding: 20px; background: var(--bg); color: #333; }
        header { display: flex; justify-content: space-between; align-items: center; background: var(--primary); color: white; padding: 15px 20px; border-radius: 8px; margin-bottom: 20px; }
        header a { color: white; text-decoration: none; font-weight: bold; }
        .container { max-width: 800px; margin: 0 auto; }
        .card-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 20px; }
        .card { background: white; padding: 25px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); text-align: center; cursor: pointer; transition: transform 0.2s; border: 1px solid #e0e0e0; }
        .card:hover { transform: translateY(-3px); box-shadow: 0 6px 12px rgba(0,0,0,0.1); }
        .btn { background: var(--primary); color: white; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer; font-weight: 600; text-decoration: none; display: inline-block; }
        .btn-back { background: #616161; margin-bottom: 20px; }
        .price-tag { font-size: 24px; color: var(--primary); font-weight: bold; margin: 10px 0; }
        .mrp { text-decoration: line-through; color: #757575; font-size: 16px; }
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; font-weight: bold; }
        input, textarea { width: 100%; padding: 10px; border: 1px solid #ccc; border-radius: 6px; box-sizing: border-box; }
        .qr-box { background: white; padding: 30px; border-radius: 12px; text-align: center; max-width: 400px; margin: 40px auto; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🏪 Khandelwal Food Mart </h1>
            <div>
                {% if session.get('logged_in') %}
                    <a href="/admin/dashboard">Dashboard</a> | <a href="/logout">Logout</a>
                {% else %}
                    <a href="/admin/login">Store Admin Login</a>
                {% endif %}
            </div>
        </header>

        {% if view == 'categories' %}
            <h2>Select a Category</h2>
            <div class="card-grid">
                {% for cat in data %}
                    <div class="card" onclick="location.href='/customer/category/{{ cat }}'">
                        <h3>{{ cat }}</h3>
                        <p style="color: var(--secondary);">Browse Products →</p>
                    </div>
                {% endfor %}
            </div>
            
            <div class="qr-box">
                <h3>Your Shop QR Code</h3>
                <img src="data:image/png;base64,{{ qr_img }}" alt="Scan QR Code" style="width:200px;height:200px;"/>
                <p style="font-size:12px; color:#666;">Scan with your phone camera to open the store!</p>
            </div>

        {% elif view == 'products' %}
            <a href="/customer" class="btn btn-back">← Back to Categories</a>
            <h2>{{ current_category }} Items</h2>
            <div class="card-grid">
                {% for prod in data %}
                    <div class="card" onclick="location.href='/customer/product/{{ prod.id }}'">
                        <h3>{{ prod.name }}</h3>
                        <div class="price-tag">₹{{ prod.sale_price }}</div>
                    </div>
                {% endfor %}
            </div>

        {% elif view == 'description' %}
            <a href="/customer/category/{{ data.category }}" class="btn btn-back">← Back to Product List</a>
            <div class="card" style="text-align: left; cursor: default;">
                <h2 style="margin-top:10px;">{{ data.name }}</h2>
                <hr style="border: 0; border-top: 1px solid #eee;">
                <div class="price-tag">Special Price: ₹{{ data.sale_price }}</div>
                <div class="mrp">Normal MRP: ₹{{ data.mrp }}</div>
                <h3 style="margin-top: 25px; color: var(--secondary);">Instructions:</h3>
                <p style="line-height: 1.6; background: #fafafa; padding: 15px; border-left: 4px solid var(--primary);">{{ data.instructions }}</p>
            </div>

        {% elif view == 'login' %}
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

        {% elif view == 'dashboard' %}
            <h2>Welcome Back, Owner! Add New Products Below:</h2>
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
                    </div>
                    <div class="form-group">
                        <label>Customer Instructions</label>
                        <textarea name="instructions" rows="3" required></textarea>
                    </div>
                    <button type="submit" class="btn">➕ Add to Digital Menu</button>
                </form>
            </div>
        {% endif %}
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    return redirect(url_for('customer_home'))

@app.route('/customer')
def customer_home():
    cats = query_db('SELECT DISTINCT category FROM products')
    categories_list = [row['category'] for row in cats]
    qr_img = generate_qr_base64()
    return render_template_string(HTML_TEMPLATE, view='categories', data=categories_list, qr_img=qr_img)

@app.route('/customer/category/<cat_name>')
def customer_category(cat_name):
    prods = query_db('SELECT * FROM products WHERE category = ?', [cat_name])
    return render_template_string(HTML_TEMPLATE, view='products', data=prods, current_category=cat_name)

@app.route('/customer/product/<int:prod_id>')
def customer_product(prod_id):
    prod = query_db('SELECT * FROM products WHERE id = ?', [prod_id], one=True)
    return render_template_string(HTML_TEMPLATE, view='description', data=prod)

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if request.form['username'] == 'kfm' and request.form['password'] == '12345678':
            session['logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        return render_template_string(HTML_TEMPLATE, view='login', error='Incorrect password!')
    return render_template_string(HTML_TEMPLATE, view='login')

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('admin_login'))
    return render_template_string(HTML_TEMPLATE, view='dashboard')

@app.route('/admin/add', methods=['POST'])
def add_product():
    if not session.get('logged_in'):
        return redirect(url_for('admin_login'))
    query_db('INSERT INTO products (category, name, mrp, sale_price, instructions) VALUES (?, ?, ?, ?, ?)',
             [request.form['category'].strip(), request.form['name'].strip(), float(request.form['mrp']), float(request.form['sale_price']), request.form['instructions'].strip()])
    return redirect(url_for('customer_home'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('customer_home'))

# This will initialize the tables perfectly both locally and on Render
init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)