from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_pymongo import PyMongo
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message
from bson.objectid import ObjectId
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# MongoDB Configuration
from urllib.parse import quote_plus

password = quote_plus("urRyYL1SErGznClw")
app.config['MONGO_URI'] = f'mongodb+srv://medicare0sd:{password}@medikazecluster.ge3moca.mongodb.net/medikaze?retryWrites=true&w=majority'
mongo = PyMongo(app)

# Flask-Mail Configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'medicare0sd@gmail.com'
app.config['MAIL_PASSWORD'] = 'ehnt seax eoin avbj'
mail = Mail(app)

ADMIN_EMAIL = 'a.tech.chd@gmail.com'

# Upload folder for medicine images
app.config['UPLOAD_FOLDER'] = 'static/uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/index')
def index():
    medicines = mongo.db.medicines.find()  # ✅ Store it in a variable
    return render_template('index.html', medicines=medicines)


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        is_admin = 'admin' in request.form

        if mongo.db.users.find_one({'email': email}):
            flash('Email already exists.')
            return redirect('/signup')

        user = {
            'email': email,
            'password': generate_password_hash(password),
            'is_admin': is_admin
        }
        mongo.db.users.insert_one(user)

        msg = Message('Welcome to Medikaze!', sender='medicare0sd@gmail.com', recipients=[email])
        msg.body = f"Hi {email},\n\nWelcome to Medikaze! Your account has been successfully created.\n\nThank you!"
        mail.send(msg)

        flash('Account created! Please log in.')
        return redirect('/login')
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = mongo.db.users.find_one({'email': email})
        if user and check_password_hash(user['password'], password):
            session['user'] = user['email']
            session['is_admin'] = user['is_admin']
            flash('Login successful!')
            return redirect('/')
        else:
            flash('Invalid credentials.')
            return redirect('/login')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out.")
    return redirect('/')

@app.route('/add-to-cart/<med_id>', methods=['POST'])
def add_to_cart(med_id):
    medicine = mongo.db.medicines.find_one({'_id': ObjectId(med_id)})
    if 'cart' not in session:
        session['cart'] = []
    session['cart'].append({
        'id': str(medicine['_id']),
        'name': medicine['name'],
        'price': medicine['price']
    })
    flash("Added to cart!")
    return redirect('/')

@app.route('/cart')
def cart():
    return render_template('cart.html', cart=session.get('cart', []))

@app.route('/admin/delete-all', methods=['POST'])
def delete_all_medicines():
    if not session.get('is_admin'):
        flash("Unauthorized access.")
        return redirect('/')
    
    mongo.db.medicines.delete_many({})
    flash("All medicines have been removed.")
    return redirect('/admin')


@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if not session.get('is_admin'):
        flash("Unauthorized access.")
        return redirect('/')

    if request.method == 'POST':
        # 🟢 Manual Medicine Upload
        if request.form.get('manual') == '1':
            name = request.form['name']
            price = float(request.form['price'])
            stock = int(request.form['stock'])
            description = request.form['description']
            
            image_file = request.files['image']
            image_url = request.form.get('image_url')

            if image_file and image_file.filename != '':
                filename = secure_filename(image_file.filename)
                image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                image_file.save(image_path)
                image = f'uploads/{filename}'  # Local static path
            elif image_url:
                image = image_url.strip()  # External URL (e.g. https://...)
            else:
                image = 'uploads/default.jpg'  # fallback if nothing provided

            medicine = {
                'name': name,
                'price': price,
                'stock': stock,
                'description': description,
                'image': image
            }
            mongo.db.medicines.insert_one(medicine)
            flash("Medicine added successfully!")

        # 📦 CSV Upload
        elif 'csv' in request.files:
            import pandas as pd
            file = request.files['csv']
            if file.filename.endswith('.csv'):
                df = pd.read_csv(file)
                for _, row in df.iterrows():
                    mongo.db.medicines.insert_one({
                        'name': row['name'],
                        'price': float(row['price']),
                        'stock': int(row['stock']),
                        'description': row.get('description', 'No description'),
                        'image': 'uploads/default.jpg'  # fallback image
                    })
                flash("Medicines uploaded from CSV!")

    # Load all medicines to display in admin panel
    medicines = mongo.db.medicines.find()
    return render_template('admin.html', medicines=medicines)



@app.route('/place-order', methods=['POST'])
def place_order():
    if 'user' not in session:
        flash("Please login to place order.")
        return redirect('/login')

    cart = session.get('cart', [])
    if not cart:
        flash("Cart is empty!")
        return redirect('/cart')

    order = {
        'user': session['user'],
        'timestamp': datetime.utcnow(),
        'items': cart
    }
    mongo.db.orders.insert_one(order)
    email_body = "\U0001f6d2 Your Order Summary:\n\n"
    for item in cart:
        email_body += f"- {item['name']} — ₹{item['price']}\n"

    session['cart'] = []

    msg = Message('Medikaze Order Confirmation', sender='medicare0sd@gmail.com', recipients=[session['user']])
    msg.body = f"Hi {session['user']},\n\nYour order has been placed!\n\n{email_body}\n\nThank you for choosing Medikaze!"
    mail.send(msg)

    admin_msg = Message('🛎️ New Order on Medikaze', sender='medicare0sd@gmail.com', recipients=[ADMIN_EMAIL])
    admin_msg.body = f"New order received from {session['user']}:\n\n{email_body}\nPlaced at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    mail.send(admin_msg)

    flash("Order placed and email sent!")
    return redirect('/order-confirmation')

@app.route('/order-confirmation')
def order_confirmation():
    return render_template('order_confirmation.html')

@app.route('/remove/<med_id>')
def remove(med_id):
    mongo.db.medicines.delete_one({'_id': ObjectId(med_id)})
    flash("Medicine removed!")
    return redirect('/admin')

if __name__ == '__main__':
<<<<<<< HEAD
    app.run(debug=True)
=======
    app.run(host='0.0.0.0', port=10000)
>>>>>>> 2ac21e2d6f594d947326109a378e8ede047c2e17
