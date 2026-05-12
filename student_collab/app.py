from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import os

from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

# ---------- App Config ----------
app = Flask(__name__)
app.secret_key = 'subhi123'

# ---------- Paths ----------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.path.join(BASE_DIR, 'users.db')

UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'docs')

ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'txt'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB

# Create upload folder if not exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ---------- Database ----------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        cursor = conn.cursor()

        # Users Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        ''')

        # Posts Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                category TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                link TEXT,
                doc_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.commit()

# Initialize DB immediately
init_db()

# ---------- Helpers ----------
def allowed_file(filename):
    return (
        '.' in filename and
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
    )

# ---------- Routes ----------
@app.route('/')
def home():
    if 'username' in session:
        return redirect(url_for('dashboard'))

    return render_template('login.html')

# ---------- Register Page ----------
@app.route('/register')
def register_page():
    return render_template('register.html')

# ---------- Register ----------
@app.route('/register', methods=['POST'])
def register():

    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    confirm = request.form.get('confirm_password', '')

    # Validation
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

    try:
        with get_db() as conn:
            cursor = conn.cursor()

            # Check existing user
            cursor.execute(
                "SELECT id FROM users WHERE username=?",
                (username,)
            )

            if cursor.fetchone():
                flash("Username already exists.", "error")
                return redirect(url_for('register_page'))

            # Insert new user
            cursor.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)",
                (username, hashed_password)
            )

            conn.commit()

        flash("Registration successful!", "success")
        return redirect(url_for('home'))

    except Exception as e:
        print("REGISTER ERROR:", e)
        flash("Something went wrong.", "error")
        return redirect(url_for('register_page'))

# ---------- Login ----------
@app.route('/login', methods=['POST'])
def login():

    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')

    if not username or not password:
        flash("Please fill in all fields.", "error")
        return redirect(url_for('home'))

    try:
        with get_db() as conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT password FROM users WHERE username=?",
                (username,)
            )

            record = cursor.fetchone()

        if record and check_password_hash(record['password'], password):

            session['username'] = username

            flash(f"Welcome back, {username}!", "success")

            return redirect(url_for('dashboard'))

        else:
            flash("Invalid username or password.", "error")
            return redirect(url_for('home'))

    except Exception as e:
        print("LOGIN ERROR:", e)
        flash("Something went wrong.", "error")
        return redirect(url_for('home'))

# ---------- Dashboard ----------
@app.route('/dashboard')
def dashboard():

    if 'username' not in session:
        return redirect(url_for('home'))

    search = request.args.get('search', '').strip()
    category = request.args.get('category', '').strip()

    query = "SELECT * FROM posts WHERE 1=1"
    params = []

    if category:
        query += " AND category = ?"
        params.append(category)

    if search:
        query += """
            AND (
                LOWER(username) LIKE ?
                OR LOWER(title) LIKE ?
                OR LOWER(content) LIKE ?
            )
        """

        term = f"%{search.lower()}%"

        params.extend([term, term, term])

    query += " ORDER BY created_at DESC"

    try:
        with get_db() as conn:
            cursor = conn.cursor()

            cursor.execute(query, params)

            posts = cursor.fetchall()

        return render_template(
            'dashboard.html',
            posts=posts,
            search=search,
            category=category
        )

    except Exception as e:
        print("DASHBOARD ERROR:", e)
        flash("Unable to load dashboard.", "error")
        return redirect(url_for('home'))

# ---------- Add Post ----------
@app.route('/add_post', methods=['POST'])
def add_post():

    if 'username' not in session:
        return redirect(url_for('home'))

    title = request.form.get('title', '').strip()
    category = request.form.get('category', '').strip()
    content = request.form.get('content', '').strip()
    link = request.form.get('link', '').strip()

    doc_file = request.files.get('doc')

    doc_path = ''

    if not title or not category or not content:
        flash("Title, category and content are required.", "error")
        return redirect(url_for('dashboard'))

    try:

        # File Upload
        if doc_file and doc_file.filename:

            if allowed_file(doc_file.filename):

                filename = secure_filename(doc_file.filename)

                save_path = os.path.join(
                    app.config['UPLOAD_FOLDER'],
                    filename
                )

                doc_file.save(save_path)

                doc_path = f"static/docs/{filename}"

            else:
                flash(
                    "Invalid file type. Allowed: pdf, doc, docx, txt",
                    "error"
                )
                return redirect(url_for('dashboard'))

        with get_db() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                INSERT INTO posts
                (username, category, title, content, link, doc_path)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                session['username'],
                category,
                title,
                content,
                link,
                doc_path
            ))

            conn.commit()

        flash("Post shared successfully!", "success")

    except Exception as e:
        print("ADD POST ERROR:", e)
        flash("Failed to add post.", "error")

    return redirect(url_for('dashboard'))

# ---------- Delete Post ----------
@app.route('/delete_post/<int:post_id>', methods=['POST'])
def delete_post(post_id):

    if 'username' not in session:
        return redirect(url_for('home'))

    try:
        with get_db() as conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT username, doc_path FROM posts WHERE id=?",
                (post_id,)
            )

            post = cursor.fetchone()

            if not post:
                flash("Post not found.", "error")
                return redirect(url_for('dashboard'))

            # Only owner can delete
            if post['username'] != session['username']:
                flash("You can only delete your own posts.", "error")
                return redirect(url_for('dashboard'))

            # Delete uploaded file
            if post['doc_path']:

                file_path = os.path.join(BASE_DIR, post['doc_path'])

                if os.path.exists(file_path):
                    os.remove(file_path)

            # Delete DB row
            cursor.execute(
                "DELETE FROM posts WHERE id=?",
                (post_id,)
            )

            conn.commit()

        flash("Post deleted successfully.", "success")

    except Exception as e:
        print("DELETE ERROR:", e)
        flash("Failed to delete post.", "error")

    return redirect(url_for('dashboard'))

# ---------- Logout ----------
@app.route('/logout')
def logout():

    session.pop('username', None)

    flash("Logged out successfully.", "success")

    return redirect(url_for('home'))

# ---------- Main ----------
if __name__ == '__main__':

    port = int(os.environ.get('PORT', 5000))

    app.run(
        debug=True,
        host='0.0.0.0',
        port=port
    )
