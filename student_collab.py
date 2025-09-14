from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3, os
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

# ---------- App Config ----------
app = Flask(_name_)
app.secret_key = 'subhi123'

UPLOAD_FOLDER = 'static/docs'
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'txt'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB file size limit
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ---------- DB Initialization ----------
def init_db():
    with sqlite3.connect('users.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            username TEXT UNIQUE,
                            password TEXT)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS posts (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            username TEXT,
                            category TEXT,
                            title TEXT,
                            content TEXT,
                            link TEXT,
                            doc_path TEXT)''')
        conn.commit()

# ---------- Helpers ----------
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ---------- Routes ----------
@app.route('/')
def home():
    return render_template('login.html')

@app.route('/register')
def register_page():
    return render_template('register.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']
    with sqlite3.connect('users.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT password FROM users WHERE username=?", (username,))
        record = cursor.fetchone()

    if record and check_password_hash(record[0], password):
        session['username'] = username
        return redirect(url_for('dashboard'))
    else:
        flash("Invalid username or password")
        return redirect(url_for('home'))

@app.route('/register', methods=['POST'])
def register():
    username = request.form['username']
    password = request.form['password']
    hashed_password = generate_password_hash(password)

    with sqlite3.connect('users.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username=?", (username,))
        if cursor.fetchone():
            flash("Username already exists")
            return redirect(url_for('register_page'))
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_password))
        conn.commit()
    flash("Registration successful. Please log in.")
    return redirect(url_for('home'))

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('home'))

    search = request.args.get('search', '').lower()
    category = request.args.get('category', '')
    query = "SELECT * FROM posts WHERE 1=1"
    params = []

    if category:
        query += " AND category = ?"
        params.append(category)
    if search:
        query += " AND (LOWER(username) LIKE ? OR LOWER(title) LIKE ? OR LOWER(content) LIKE ?)"
        term = f"%{search}%"
        params += [term, term, term]

    with sqlite3.connect('users.db') as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        posts = cursor.fetchall()

    return render_template('dashboard.html', posts=posts)

@app.route('/add_post', methods=['POST'])
def add_post():
    if 'username' not in session:
        return redirect(url_for('home'))

    title = request.form['title']
    category = request.form['category']
    content = request.form['content']
    link = request.form['link']
    doc_file = request.files['doc']
    doc_path = ''

    if doc_file and doc_file.filename:
        if allowed_file(doc_file.filename):
            filename = secure_filename(doc_file.filename)
            doc_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            doc_file.save(doc_path)
        else:
            flash("Invalid file type")
            return redirect(url_for('dashboard'))

    with sqlite3.connect('users.db') as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO posts (username, category, title, content, link, doc_path) VALUES (?, ?, ?, ?, ?, ?)",
                       (session['username'], category, title, content, link, doc_path))
        conn.commit()

    flash("Post added successfully")
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.pop('username', None)
    flash("Logged out successfully")
    return redirect(url_for('home'))

# ---------- Main ----------
if _name_ == '_main_':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
