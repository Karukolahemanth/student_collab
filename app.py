from flask import Flask, render_template, request, redirect, url_for, session, flash
import os
import psycopg2
from werkzeug.security import generate_password_hash, check_password_hash

# ---------- App Config ----------
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'subhi123')

DATABASE_URL = os.environ.get('DATABASE_URL')

# ---------- DB Helpers ----------
def get_db():
    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL environment variable is not set. "
            "Add it in your Vercel project settings → Environment Variables."
        )
    conn = psycopg2.connect(DATABASE_URL)
    return conn

def init_db():
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                            id SERIAL PRIMARY KEY,
                            username TEXT UNIQUE,
                            password TEXT)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS posts (
                            id SERIAL PRIMARY KEY,
                            username TEXT,
                            category TEXT,
                            title TEXT,
                            content TEXT,
                            link TEXT,
                            doc_path TEXT,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        conn.commit()
    finally:
        conn.close()

# Auto-init DB tables on cold start (idempotent — safe to run every time)
if DATABASE_URL:
    try:
        init_db()
        print("[Info] DB initialised successfully.")
    except Exception as e:
        # Log but do NOT crash — routes will return 500 with a clear message
        print(f"[Warning] DB init failed: {e}")
else:
    print("[Warning] DATABASE_URL not set — DB features will be unavailable.")

# ---------- Routes ----------
@app.route('/')
def home():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/register')
def register_page():
    return render_template('register.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username'].strip()
    password = request.form['password']

    if not username or not password:
        flash("Please fill in all fields.", "error")
        return redirect(url_for('home'))

    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT password FROM users WHERE username=%s", (username,))
        record = cursor.fetchone()
    finally:
        conn.close()

    if record and check_password_hash(record[0], password):
        session['username'] = username
        flash(f"Welcome back, {username}!", "success")
        return redirect(url_for('dashboard'))
    else:
        flash("Invalid username or password.", "error")
        return redirect(url_for('home'))

@app.route('/register', methods=['POST'])
def register():
    username = request.form['username'].strip()
    password = request.form['password']
    confirm  = request.form['confirm_password']

    if not username or not password:
        flash("Please fill in all fields.", "error")
        return redirect(url_for('register_page'))

    if password != confirm:
        flash("Passwords do not match.", "error")
        return redirect(url_for('register_page'))

    if len(password) < 6:
        flash("Password must be at least 6 characters.", "error")
        return redirect(url_for('register_page'))

    hashed_password = generate_password_hash(password)

    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username=%s", (username,))
        if cursor.fetchone():
            flash("Username already exists. Try a different one.", "error")
            return redirect(url_for('register_page'))
        cursor.execute(
            "INSERT INTO users (username, password) VALUES (%s, %s)",
            (username, hashed_password)
        )
        conn.commit()
    finally:
        conn.close()

    flash("Registration successful! Please log in.", "success")
    return redirect(url_for('home'))

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('home'))

    search   = request.args.get('search', '').strip()
    category = request.args.get('category', '')
    query    = "SELECT * FROM posts WHERE 1=1"
    params   = []

    if category:
        query += " AND category = %s"
        params.append(category)
    if search:
        query += " AND (LOWER(username) LIKE %s OR LOWER(title) LIKE %s OR LOWER(content) LIKE %s)"
        term = f"%{search.lower()}%"
        params += [term, term, term]

    query += " ORDER BY created_at DESC"

    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        posts = cursor.fetchall()
    finally:
        conn.close()

    return render_template('dashboard.html', posts=posts,
                           search=search, category=category)

@app.route('/add_post', methods=['POST'])
def add_post():
    if 'username' not in session:
        return redirect(url_for('home'))

    title    = request.form['title'].strip()
    category = request.form['category']
    content  = request.form['content'].strip()
    link     = request.form.get('link', '').strip()

    if not title or not content or not category:
        flash("Title, category and content are required.", "error")
        return redirect(url_for('dashboard'))

    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO posts (username, category, title, content, link, doc_path) VALUES (%s, %s, %s, %s, %s, %s)",
            (session['username'], category, title, content, link, '')
        )
        conn.commit()
    finally:
        conn.close()

    flash("Post shared successfully!", "success")
    return redirect(url_for('dashboard'))

@app.route('/delete_post/<int:post_id>', methods=['POST'])
def delete_post(post_id):
    if 'username' not in session:
        return redirect(url_for('home'))

    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM posts WHERE id=%s", (post_id,))
        post = cursor.fetchone()

        if not post:
            flash("Post not found.", "error")
            return redirect(url_for('dashboard'))

        if post[0] != session['username']:
            flash("You can only delete your own posts.", "error")
            return redirect(url_for('dashboard'))

        cursor.execute("DELETE FROM posts WHERE id=%s", (post_id,))
        conn.commit()
    finally:
        conn.close()

    flash("Post deleted.", "success")
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    username = session.pop('username', None)
    if username:
        flash("Logged out successfully. See you soon!", "success")
    return redirect(url_for('home'))

# ---------- Main (local dev only) ----------
if __name__ == '__main__':
    if not DATABASE_URL:
        print("ERROR: DATABASE_URL environment variable is not set.")
        print("Set it to your Neon PostgreSQL connection string.")
        exit(1)
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
