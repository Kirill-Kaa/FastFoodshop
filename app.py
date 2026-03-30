from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
from datetime import datetime
from PIL import Image

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this-in-production'

DATABASE = 'food_store.db'

# Loyalty program settings
POINTS_PER_PENNY = 1  # 1 penny = 1 point
PENNIES_PER_POINT = 1  # 1 point = 1 penny when redeeming

UPLOAD_FOLDER = 'static/uploads/products'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_IMAGE_SIZE = (800, 800)  # Max dimensions for uploaded images
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_image(file, product_id):
    """Process and save uploaded image"""
    if file and allowed_file(file.filename):
        # Generate secure filename
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"product_{product_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.{ext}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        # Open and resize image
        img = Image.open(file)
        img.thumbnail(MAX_IMAGE_SIZE, Image.Resampling.LANCZOS)
        
        # Convert RGBA to RGB if necessary
        if img.mode == 'RGBA':
            img = img.convert('RGB')
        
        # Save image
        img.save(filepath, quality=85, optimize=True)
        
        # Return the URL path
        return f"/static/uploads/products/{filename}"
    
    return None

def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def login_required(f):
    """Decorator to require login for certain routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def get_user_points(user_id):
    """Get user's current loyalty points balance"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT loyalty_points FROM users WHERE id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result['loyalty_points'] if result else 0

def add_points(user_id, points, description):
    """Add loyalty points to user account"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Update user points
    cursor.execute('UPDATE users SET loyalty_points = loyalty_points + ? WHERE id = ?', 
                   (points, user_id))
    
    # Record transaction
    cursor.execute('''
        INSERT INTO loyalty_transactions (user_id, points, description, transaction_type)
        VALUES (?, ?, ?, ?)
    ''', (user_id, points, description, 'earned' if points > 0 else 'redeemed'))
    
    conn.commit()
    conn.close()

def init_db():
    """Initialize database with tables and sample data"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Create products table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            price REAL NOT NULL,
            category TEXT NOT NULL,
            image_url TEXT,
            in_stock INTEGER DEFAULT 1
        )
    ''')
    
    # Create users table (add loyalty_points column)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT,
            phone TEXT,
            address TEXT,
            city TEXT,
            postal_code TEXT,
            loyalty_points INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create loyalty transactions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS loyalty_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            points INTEGER NOT NULL,
            description TEXT,
            transaction_type TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Create vouchers table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vouchers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            discount_percent INTEGER NOT NULL,
            is_used INTEGER DEFAULT 0,
            used_order_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Create cart table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cart (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (product_id) REFERENCES products (id),
            UNIQUE(user_id, product_id)
        )
    ''')
    
    # Create orders table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            total_amount REAL NOT NULL,
            points_redeemed INTEGER DEFAULT 0,
            points_earned INTEGER DEFAULT 0,
            discount_percent INTEGER DEFAULT 0,
            discount_amount REAL DEFAULT 0,
            final_amount REAL NOT NULL,
            voucher_id INTEGER,
            status TEXT DEFAULT 'pending',
            delivery_address TEXT,
            delivery_city TEXT,
            delivery_postal_code TEXT,
            phone TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (voucher_id) REFERENCES vouchers (id)
        )
    ''')
    
    # Create order_items table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            price REAL NOT NULL,
            quantity INTEGER NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders (id),
            FOREIGN KEY (product_id) REFERENCES products (id)
        )
    ''')
    
    # Check if we already have products
    cursor.execute('SELECT COUNT(*) FROM products')
    if cursor.fetchone()[0] == 0:
        # Insert sample products
        sample_products = [
            ('Margherita Pizza', 'Classic pizza with fresh mozzarella and basil', 12.99, 'Pizza', 'https://images.unsplash.com/photo-1574071318508-1cdbab80d002?w=400', 1),
            ('Pepperoni Pizza', 'Loaded with pepperoni and cheese', 14.99, 'Pizza', 'https://images.unsplash.com/photo-1628840042765-356cda07504e?w=400', 1),
            ('Caesar Salad', 'Crisp romaine lettuce with Caesar dressing', 8.99, 'Salads', 'https://images.unsplash.com/photo-1546793665-c74683f339c1?w=400', 1),
            ('Chicken Burger', 'Grilled chicken with fresh vegetables', 11.99, 'Burgers', 'https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=400', 1),
            ('Beef Burger', 'Juicy beef patty with special sauce', 13.99, 'Burgers', 'https://images.unsplash.com/photo-1550547660-d9450f859349?w=400', 1),
            ('Pasta Carbonara', 'Creamy pasta with bacon and parmesan', 13.99, 'Pasta', 'https://images.unsplash.com/photo-1612874742237-6526221588e3?w=400', 1),
            ('Greek Salad', 'Fresh vegetables with feta cheese', 9.99, 'Salads', 'https://images.unsplash.com/photo-1540189549336-e6e99c3679fe?w=400', 1),
            ('Spaghetti Bolognese', 'Traditional meat sauce pasta', 12.99, 'Pasta', 'https://images.unsplash.com/photo-1621996346565-e3dbc646d9a9?w=400', 1),
            ('Veggie Pizza', 'Loaded with fresh vegetables', 13.99, 'Pizza', 'https://images.unsplash.com/photo-1511689660979-10d2b1aada49?w=400', 1),
            ('BBQ Chicken Burger', 'Chicken with tangy BBQ sauce', 12.99, 'Burgers', 'https://images.unsplash.com/photo-1553979459-d2229ba7433b?w=400', 1),
        ]
        
        cursor.executemany('''
            INSERT INTO products (name, description, price, category, image_url, in_stock)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', sample_products)
    
    conn.commit()
    conn.close()

@app.route('/loyalty/buy-voucher/<int:discount>', methods=['POST'])
@login_required
def buy_voucher(discount):
    """Buy a discount voucher with points"""
    # Define voucher prices
    voucher_prices = {
        15: 1500,  # 15% discount costs 1500 points
        20: 2000   # 20% discount costs 2000 points
    }
    
    if discount not in voucher_prices:
        flash('Invalid voucher type!', 'danger')
        return redirect(url_for('loyalty'))
    
    points_cost = voucher_prices[discount]
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Get user points
        cursor.execute('SELECT loyalty_points FROM users WHERE id = ?', (session['user_id'],))
        current_points = cursor.fetchone()['loyalty_points']
        
        if current_points < points_cost:
            flash(f'Not enough points! You need {points_cost} points for this voucher.', 'danger')
            conn.close()
            return redirect(url_for('loyalty'))
        
        # Deduct points
        cursor.execute('''
            UPDATE users SET loyalty_points = loyalty_points - ? WHERE id = ?
        ''', (points_cost, session['user_id']))
        
        # Create voucher
        cursor.execute('''
            INSERT INTO vouchers (user_id, discount_percent, is_used)
            VALUES (?, ?, 0)
        ''', (session['user_id'], discount))
        
        # Record transaction
        cursor.execute('''
            INSERT INTO loyalty_transactions (user_id, points, description, transaction_type)
            VALUES (?, ?, ?, ?)
        ''', (session['user_id'], -points_cost, f'Bought {discount}% discount voucher', 'redeemed'))
        
        conn.commit()
        flash(f'Successfully purchased {discount}% discount voucher!', 'success')
        
    except Exception as e:
        conn.rollback()
        flash(f'An error occurred: {str(e)}', 'danger')
    finally:
        conn.close()
    
    return redirect(url_for('loyalty'))

@app.route('/')
def index():
    """Home page"""
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration"""
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        full_name = request.form.get('full_name')
        
        if not username or not email or not password:
            flash('All fields are required!', 'danger')
            return redirect(url_for('register'))
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Check if username or email already exists
        cursor.execute('SELECT id FROM users WHERE username = ? OR email = ?', (username, email))
        if cursor.fetchone():
            flash('Username or email already exists!', 'danger')
            conn.close()
            return redirect(url_for('register'))
        
        # Create new user with 0 loyalty points
        password_hash = generate_password_hash(password)
        cursor.execute('''
            INSERT INTO users (username, email, password_hash, full_name, loyalty_points)
            VALUES (?, ?, ?, ?, 0)
        ''', (username, email, password_hash, full_name))
        
        conn.commit()
        conn.close()
        
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        conn.close()
        
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash(f'Welcome back, {user["username"]}!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password!', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """User logout"""
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/account')
@login_required
def account():
    """User account page"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],))
    user = cursor.fetchone()
    
    # Get order history
    cursor.execute('''
        SELECT o.id, o.total_amount, o.final_amount, o.points_earned, 
               o.points_redeemed, o.status, o.created_at,
               COUNT(oi.id) as item_count
        FROM orders o
        LEFT JOIN order_items oi ON o.id = oi.order_id
        WHERE o.user_id = ?
        GROUP BY o.id
        ORDER BY o.created_at DESC
    ''', (session['user_id'],))
    orders = cursor.fetchall()
    
    # Get loyalty transactions
    cursor.execute('''
        SELECT * FROM loyalty_transactions
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT 10
    ''', (session['user_id'],))
    transactions = cursor.fetchall()
    
    conn.close()
    
    return render_template('account.html', user=user, orders=orders, transactions=transactions)

@app.route('/account/update', methods=['POST'])
@login_required
def update_account():
    """Update user account information"""
    full_name = request.form.get('full_name')
    phone = request.form.get('phone')
    address = request.form.get('address')
    city = request.form.get('city')
    postal_code = request.form.get('postal_code')
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE users 
        SET full_name = ?, phone = ?, address = ?, city = ?, postal_code = ?
        WHERE id = ?
    ''', (full_name, phone, address, city, postal_code, session['user_id']))
    
    conn.commit()
    conn.close()
    
    flash('Account information updated successfully!', 'success')
    return redirect(url_for('account'))

@app.route('/loyalty')
@login_required
def loyalty():
    """Loyalty program page"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT loyalty_points FROM users WHERE id = ?', (session['user_id'],))
    user = cursor.fetchone()
    points = user['loyalty_points']
    
    # Get recent transactions
    cursor.execute('''
        SELECT * FROM loyalty_transactions
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT 20
    ''', (session['user_id'],))
    transactions = cursor.fetchall()
    
    # Get active vouchers
    cursor.execute('''
        SELECT * FROM vouchers
        WHERE user_id = ? AND is_used = 0
        ORDER BY created_at DESC
    ''', (session['user_id'],))
    vouchers = cursor.fetchall()
    
    conn.close()
    
    # Calculate points value
    points_value = points / 100
    
    return render_template('loyalty.html', points=points, points_value=points_value, 
                         transactions=transactions, vouchers=vouchers)

@app.route('/order/<int:order_id>')
@login_required
def order_detail(order_id):
    """View order details"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Get order
    cursor.execute('''
        SELECT * FROM orders 
        WHERE id = ? AND user_id = ?
    ''', (order_id, session['user_id']))
    order = cursor.fetchone()
    
    if not order:
        flash('Order not found!', 'danger')
        return redirect(url_for('account'))
    
    # Get order items
    cursor.execute('''
        SELECT * FROM order_items
        WHERE order_id = ?
    ''', (order_id,))
    items = cursor.fetchall()
    
    conn.close()
    
    return render_template('order_detail.html', order=order, items=items)

@app.route('/catalog')
def catalog():
    """Product catalog page"""
    conn = get_db()
    cursor = conn.cursor()
    
    category = request.args.get('category', 'all')
    
    if category == 'all':
        cursor.execute('SELECT * FROM products WHERE in_stock = 1 ORDER BY category, name')
    else:
        cursor.execute('SELECT * FROM products WHERE category = ? AND in_stock = 1 ORDER BY name', (category,))
    
    products = cursor.fetchall()
    
    cursor.execute('SELECT DISTINCT category FROM products ORDER BY category')
    categories = [row['category'] for row in cursor.fetchall()]
    
    conn.close()
    
    return render_template('catalog.html', products=products, categories=categories, selected_category=category)

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    """Individual product page"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM products WHERE id = ?', (product_id,))
    product = cursor.fetchone()
    conn.close()
    
    if product is None:
        return "Product not found", 404
    
    return render_template('product.html', product=product)

@app.route('/cart')
@login_required
def view_cart():
    """View shopping cart"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT c.id, c.quantity, p.id as product_id, p.name, p.price, p.image_url
        FROM cart c
        JOIN products p ON c.product_id = p.id
        WHERE c.user_id = ?
    ''', (session['user_id'],))
    
    cart_items = cursor.fetchall()
    
    # Calculate total
    total = sum(item['price'] * item['quantity'] for item in cart_items)
    
    # Get user points
    points = get_user_points(session['user_id'])
    
    conn.close()
    
    return render_template('cart.html', cart_items=cart_items, total=total, points=points)

@app.route('/cart/add/<int:product_id>', methods=['POST'])
@login_required
def add_to_cart(product_id):
    """Add product to cart"""
    quantity = int(request.form.get('quantity', 1))
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Check if item already in cart
    cursor.execute('SELECT * FROM cart WHERE user_id = ? AND product_id = ?', 
                   (session['user_id'], product_id))
    existing_item = cursor.fetchone()
    
    if existing_item:
        # Update quantity
        new_quantity = existing_item['quantity'] + quantity
        cursor.execute('UPDATE cart SET quantity = ? WHERE id = ?', 
                       (new_quantity, existing_item['id']))
    else:
        # Add new item
        cursor.execute('INSERT INTO cart (user_id, product_id, quantity) VALUES (?, ?, ?)',
                       (session['user_id'], product_id, quantity))
    
    conn.commit()
    conn.close()
    
    flash('Item added to cart!', 'success')
    return redirect(url_for('view_cart'))

@app.route('/cart/update/<int:cart_id>', methods=['POST'])
@login_required
def update_cart(cart_id):
    """Update cart item quantity"""
    quantity = int(request.form.get('quantity', 1))
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('UPDATE cart SET quantity = ? WHERE id = ? AND user_id = ?',
                   (quantity, cart_id, session['user_id']))
    
    conn.commit()
    conn.close()
    
    flash('Cart updated!', 'success')
    return redirect(url_for('view_cart'))

@app.route('/cart/remove/<int:cart_id>')
@login_required
def remove_from_cart(cart_id):
    """Remove item from cart"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM cart WHERE id = ? AND user_id = ?',
                   (cart_id, session['user_id']))
    
    conn.commit()
    conn.close()
    
    flash('Item removed from cart!', 'info')
    return redirect(url_for('view_cart'))

@app.route('/cart/clear')
@login_required
def clear_cart():
    """Clear all items from cart"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM cart WHERE user_id = ?', (session['user_id'],))
    
    conn.commit()
    conn.close()
    
    flash('Cart cleared!', 'info')
    return redirect(url_for('view_cart'))

@app.route('/checkout')
@login_required
def checkout():
    """Checkout page"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Get cart items
    cursor.execute('''
        SELECT c.id, c.quantity, p.id as product_id, p.name, p.price, p.image_url
        FROM cart c
        JOIN products p ON c.product_id = p.id
        WHERE c.user_id = ?
    ''', (session['user_id'],))
    
    cart_items = cursor.fetchall()
    
    if not cart_items:
        flash('Your cart is empty!', 'warning')
        return redirect(url_for('catalog'))
    
    # Calculate total
    total = sum(item['price'] * item['quantity'] for item in cart_items)
    
    # Get user info
    cursor.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],))
    user = cursor.fetchone()
    
    # Get available vouchers
    cursor.execute('''
        SELECT * FROM vouchers
        WHERE user_id = ? AND is_used = 0
        ORDER BY discount_percent DESC
    ''', (session['user_id'],))
    vouchers = cursor.fetchall()
    
    points = user['loyalty_points']
    max_points_usable = int(total * 100)
    
    conn.close()
    
    return render_template('checkout.html', cart_items=cart_items, total=total, 
                         user=user, points=points, max_points_usable=max_points_usable,
                         vouchers=vouchers)

@app.route('/checkout/process', methods=['POST'])
@login_required
def process_checkout():
    """Process the order"""
    # Get form data
    delivery_address = request.form.get('address')
    delivery_city = request.form.get('city')
    delivery_postal_code = request.form.get('postal_code')
    phone = request.form.get('phone')
    notes = request.form.get('notes')
    points_to_redeem = int(request.form.get('points_to_redeem', 0))
    voucher_id = request.form.get('voucher_id')
    
    if not delivery_address or not delivery_city or not delivery_postal_code or not phone:
        flash('Please fill in all required delivery information!', 'danger')
        return redirect(url_for('checkout'))
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Get cart items
        cursor.execute('''
            SELECT c.id, c.quantity, p.id as product_id, p.name, p.price
            FROM cart c
            JOIN products p ON c.product_id = p.id
            WHERE c.user_id = ?
        ''', (session['user_id'],))
        
        cart_items = cursor.fetchall()
        
        if not cart_items:
            flash('Your cart is empty!', 'warning')
            conn.close()
            return redirect(url_for('catalog'))
        
        # Get user points
        cursor.execute('SELECT loyalty_points FROM users WHERE id = ?', (session['user_id'],))
        current_points = cursor.fetchone()['loyalty_points']
        
        # Calculate totals
        total = sum(item['price'] * item['quantity'] for item in cart_items)
        total_pennies = int(total * 100)
        
        # Handle voucher discount
        discount_percent = 0
        voucher_id_final = None
        
        if voucher_id and voucher_id != '':
            cursor.execute('''
                SELECT * FROM vouchers 
                WHERE id = ? AND user_id = ? AND is_used = 0
            ''', (voucher_id, session['user_id']))
            voucher = cursor.fetchone()
            
            if voucher:
                discount_percent = voucher['discount_percent']
                voucher_id_final = voucher['id']
        
        # Calculate discount from voucher
        voucher_discount = (total * discount_percent / 100) if discount_percent > 0 else 0
        
        # Validate points redemption
        if points_to_redeem > current_points:
            flash('You don\'t have enough points!', 'danger')
            conn.close()
            return redirect(url_for('checkout'))
        
        if points_to_redeem > total_pennies:
            flash('You can\'t use more points than the order total!', 'danger')
            conn.close()
            return redirect(url_for('checkout'))
        
        # Calculate final amount
        points_discount = points_to_redeem / 100
        total_discount = voucher_discount + points_discount
        final_amount = max(0, total - total_discount)
        
        # Calculate points earned (1 penny = 1 point, based on final amount paid)
        points_earned = int(final_amount * 100)
        
        # Create order
        cursor.execute('''
            INSERT INTO orders (user_id, total_amount, points_redeemed, points_earned,
                              discount_percent, discount_amount, final_amount, voucher_id,
                              status, delivery_address, delivery_city, delivery_postal_code, 
                              phone, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?)
        ''', (session['user_id'], total, points_to_redeem, points_earned, discount_percent,
              total_discount, final_amount, voucher_id_final, delivery_address, 
              delivery_city, delivery_postal_code, phone, notes))
        
        order_id = cursor.lastrowid
        
        # Create order items
        for item in cart_items:
            cursor.execute('''
                INSERT INTO order_items (order_id, product_id, product_name, price, quantity)
                VALUES (?, ?, ?, ?, ?)
            ''', (order_id, item['product_id'], item['name'], item['price'], item['quantity']))
        
        # Mark voucher as used
        if voucher_id_final:
            cursor.execute('''
                UPDATE vouchers SET is_used = 1, used_order_id = ? WHERE id = ?
            ''', (order_id, voucher_id_final))
        
        # Update user points
        net_points_change = points_earned - points_to_redeem
        cursor.execute('''
            UPDATE users SET loyalty_points = loyalty_points + ? WHERE id = ?
        ''', (net_points_change, session['user_id']))
        
        # Record redemption transaction if points were used
        if points_to_redeem > 0:
            cursor.execute('''
                INSERT INTO loyalty_transactions (user_id, points, description, transaction_type)
                VALUES (?, ?, ?, ?)
            ''', (session['user_id'], -points_to_redeem, f'Redeemed for Order #{order_id}', 'redeemed'))
        
        # Record earning transaction if points were earned
        if points_earned > 0:
            cursor.execute('''
                INSERT INTO loyalty_transactions (user_id, points, description, transaction_type)
                VALUES (?, ?, ?, ?)
            ''', (session['user_id'], points_earned, f'Earned from Order #{order_id}', 'earned'))
        
        # Clear cart
        cursor.execute('DELETE FROM cart WHERE user_id = ?', (session['user_id'],))
        
        # Commit all changes together
        conn.commit()
        
        flash(f'Order placed successfully! Order #{order_id}', 'success')
        if points_earned > 0:
            flash(f'You earned {points_earned} loyalty points!', 'success')
        
        return redirect(url_for('order_detail', order_id=order_id))
        
    except Exception as e:
        conn.rollback()
        flash(f'An error occurred: {str(e)}', 'danger')
        return redirect(url_for('checkout'))
    finally:
        conn.close()

@app.route('/about')
def about():
    """About us page"""
    return render_template('about.html')

@app.route('/dashboard')
@login_required
def dashboard():
    """Dashboard page for managing products and orders"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Get all products
    cursor.execute('SELECT * FROM products ORDER BY category, name')
    products = cursor.fetchall()
    
    # Get all orders with user info
    cursor.execute('''
        SELECT o.*, u.username, u.email,
               COUNT(oi.id) as item_count
        FROM orders o
        JOIN users u ON o.user_id = u.id
        LEFT JOIN order_items oi ON o.id = oi.order_id
        GROUP BY o.id
        ORDER BY o.created_at DESC
        LIMIT 50
    ''')
    orders = cursor.fetchall()
    
    # Get statistics
    cursor.execute('SELECT COUNT(*) as total FROM orders')
    total_orders = cursor.fetchone()['total']
    
    cursor.execute('SELECT COUNT(*) as total FROM products WHERE in_stock = 1')
    in_stock_products = cursor.fetchone()['total']
    
    cursor.execute('SELECT COUNT(*) as total FROM products WHERE in_stock = 0')
    out_of_stock_products = cursor.fetchone()['total']
    
    cursor.execute('SELECT SUM(final_amount) as total FROM orders WHERE status = "pending"')
    pending_revenue = cursor.fetchone()['total'] or 0
    
    conn.close()
    
    return render_template('dashboard.html', 
                         products=products, 
                         orders=orders,
                         total_orders=total_orders,
                         in_stock_products=in_stock_products,
                         out_of_stock_products=out_of_stock_products,
                         pending_revenue=pending_revenue)

@app.route('/dashboard/product/update/<int:product_id>', methods=['POST'])
@login_required
def update_product(product_id):
    """Update product details"""
    name = request.form.get('name')
    description = request.form.get('description')
    price = float(request.form.get('price'))
    category = request.form.get('category')
    in_stock = int(request.form.get('in_stock'))
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Handle image upload
    image_url = None
    if 'product_image' in request.files:
        file = request.files['product_image']
        if file and file.filename != '':
            image_url = process_image(file, product_id)
    
    # Use custom URL if provided
    custom_url = request.form.get('image_url')
    if custom_url and custom_url.strip():
        image_url = custom_url.strip()
    
    # Update product
    if image_url:
        cursor.execute('''
            UPDATE products 
            SET name = ?, description = ?, price = ?, category = ?, in_stock = ?, image_url = ?
            WHERE id = ?
        ''', (name, description, price, category, in_stock, image_url, product_id))
    else:
        cursor.execute('''
            UPDATE products 
            SET name = ?, description = ?, price = ?, category = ?, in_stock = ?
            WHERE id = ?
        ''', (name, description, price, category, in_stock, product_id))
    
    conn.commit()
    conn.close()

    flash('Product updated successfully!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/dashboard/product/stock/<int:product_id>/<int:status>')
@login_required
def toggle_stock(product_id, status):
    """Toggle product stock status"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('UPDATE products SET in_stock = ? WHERE id = ?', (status, product_id))
    
    conn.commit()
    conn.close()
    
    flash('Stock status updated!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/dashboard/order/status/<int:order_id>/<status>')
@login_required
def update_order_status(order_id, status):
    """Update order status"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('UPDATE orders SET status = ? WHERE id = ?', (status, order_id))
    
    conn.commit()
    conn.close()
    
    flash('Order status updated!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/dashboard/product/add', methods=['POST'])
@login_required
def add_product():
    """Add new product"""
    name = request.form.get('name')
    description = request.form.get('description')
    price = float(request.form.get('price'))
    category = request.form.get('category')
    in_stock = int(request.form.get('in_stock', 1))
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Create product first to get ID
    cursor.execute('''
        INSERT INTO products (name, description, price, category, in_stock, image_url)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (name, description, price, category, in_stock, 'https://via.placeholder.com/400'))
    
    product_id = cursor.lastrowid
    
    # Handle image upload
    image_url = None
    if 'product_image' in request.files:
        file = request.files['product_image']
        if file and file.filename != '':
            image_url = process_image(file, product_id)
    
    # Use custom URL if provided
    custom_url = request.form.get('image_url')
    if custom_url and custom_url.strip():
        image_url = custom_url.strip()
    
    # Update with actual image URL
    if image_url:
        cursor.execute('UPDATE products SET image_url = ? WHERE id = ?', 
                      (image_url, product_id))
    
    conn.commit()
    conn.close()
    
    flash('Product added successfully!', 'success')
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    if not os.path.exists(DATABASE):
        init_db()
    
    app.run(debug=True, host='0.0.0.0', port=5000)