from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3, os
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

# ---------- App Config ----------
app = Flask(__name__)
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
                            doc_path TEXT,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        conn.commit()

# ---------- Helpers ----------
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db():
    return sqlite3.connect('users.db')

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

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT password FROM users WHERE username=?", (username,))
        record = cursor.fetchone()

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

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username=?", (username,))
        if cursor.fetchone():
            flash("Username already exists. Try a different one.", "error")
            return redirect(url_for('register_page'))
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)",
                       (username, hashed_password))
        conn.commit()

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
        query += " AND category = ?"
        params.append(category)
    if search:
        query += " AND (LOWER(username) LIKE ? OR LOWER(title) LIKE ? OR LOWER(content) LIKE ?)"
        term = f"%{search.lower()}%"
        params += [term, term, term]

    query += " ORDER BY created_at DESC"

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        posts = cursor.fetchall()

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
    doc_file = request.files.get('doc')
    doc_path = ''

    if not title or not content or not category:
        flash("Title, category and content are required.", "error")
        return redirect(url_for('dashboard'))

    if doc_file and doc_file.filename:
        if allowed_file(doc_file.filename):
            filename = secure_filename(doc_file.filename)
            doc_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            doc_file.save(doc_path)
        else:
            flash("Invalid file type. Allowed: pdf, doc, docx, txt", "error")
            return redirect(url_for('dashboard'))

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO posts (username, category, title, content, link, doc_path) VALUES (?, ?, ?, ?, ?, ?)",
            (session['username'], category, title, content, link, doc_path)
        )
        conn.commit()

    flash("Post shared successfully!", "success")
    return redirect(url_for('dashboard'))

@app.route('/delete_post/<int:post_id>', methods=['POST'])
def delete_post(post_id):
    if 'username' not in session:
        return redirect(url_for('home'))

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT username, doc_path FROM posts WHERE id=?", (post_id,))
        post = cursor.fetchone()

        if not post:
            flash("Post not found.", "error")
            return redirect(url_for('dashboard'))

        if post[0] != session['username']:
            flash("You can only delete your own posts.", "error")
            return redirect(url_for('dashboard'))

        # Remove uploaded file if it exists
        if post[1] and os.path.exists(post[1]):
            os.remove(post[1])

        cursor.execute("DELETE FROM posts WHERE id=?", (post_id,))
        conn.commit()

    flash("Post deleted.", "success")
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    username = session.pop('username', None)
    if username:
        flash("Logged out successfully. See you soon!", "success")
    return redirect(url_for('home'))

# ---------- Main ----------
if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
