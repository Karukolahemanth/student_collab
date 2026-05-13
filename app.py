"""
Main Flask application — used by Vercel as the WSGI entry point.
api/index.py imports this app object.
"""
from flask import Flask, render_template, request, redirect, url_for, session, flash
import os, json, psycopg2
from werkzeug.security import generate_password_hash, check_password_hash

# ── app.py is at the project root, so templates/ and static/ are siblings ──
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, 'templates')
STATIC_DIR   = os.path.join(BASE_DIR, 'static')

# ---------- App Config ----------
app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)
app.secret_key = os.environ.get('SECRET_KEY', 'collabhub_fallback_key')

DATABASE_URL = os.environ.get('DATABASE_URL')

# ---------- DB Helpers ----------
def get_db():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set in Environment Variables.")
    conn = psycopg2.connect(DATABASE_URL)
    return conn

def init_db():
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute('''CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY, username TEXT UNIQUE, password TEXT)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS posts (
            id SERIAL PRIMARY KEY, username TEXT, category TEXT,
            title TEXT, content TEXT, link TEXT, doc_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS assessments (
            id SERIAL PRIMARY KEY, creator TEXT, title TEXT,
            description TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS questions (
            id SERIAL PRIMARY KEY,
            assessment_id INTEGER REFERENCES assessments(id) ON DELETE CASCADE,
            question_text TEXT, option_a TEXT, option_b TEXT,
            option_c TEXT, option_d TEXT, correct_answer TEXT)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS assessment_results (
            id SERIAL PRIMARY KEY, username TEXT,
            assessment_id INTEGER REFERENCES assessments(id) ON DELETE CASCADE,
            score INTEGER, total INTEGER,
            attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        conn.commit()
    finally:
        conn.close()

if DATABASE_URL:
    try:
        init_db()
        print("[Info] DB initialised successfully.")
    except Exception as e:
        print(f"[Warning] DB init failed: {e}")
else:
    print("[Warning] DATABASE_URL not set.")

# ---------- Error Handlers ----------
import traceback as _tb

@app.errorhandler(500)
def internal_error(e):
    full_tb = _tb.format_exc()
    return render_template('error.html', code=500,
        message=f"<pre style='text-align:left;font-size:12px;white-space:pre-wrap'>{full_tb}</pre>"), 500

@app.errorhandler(404)
def not_found(e):
    return render_template('error.html', code=404,
        message="The page you're looking for doesn't exist."), 404

@app.route('/debug')
def debug():
    import sys
    lines = [
        f"Python: {sys.version}",
        f"Running from: {__file__}",
        f"BASE_DIR: {BASE_DIR}",
        f"TEMPLATE_DIR exists: {os.path.exists(TEMPLATE_DIR)}",
        f"STATIC_DIR exists: {os.path.exists(STATIC_DIR)}",
        f"DATABASE_URL set: {bool(DATABASE_URL)}",
        f"SECRET_KEY set: {bool(os.environ.get('SECRET_KEY'))}",
    ]
    if os.path.exists(TEMPLATE_DIR):
        lines.append(f"Templates: {os.listdir(TEMPLATE_DIR)}")
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM posts")
        cnt = cur.fetchone()[0]
        conn.close()
        lines.append(f"DB OK — posts count: {cnt}")
    except Exception as e:
        lines.append(f"DB ERROR: {e}")
    return "<br>".join(lines)

# ═══════════════════════════════════════════
# AUTH
# ═══════════════════════════════════════════
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
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    if not username or not password:
        flash("Please fill in all fields.", "error")
        return redirect(url_for('home'))
    try:
        conn = get_db()
        try:
            cur = conn.cursor()
            cur.execute("SELECT password FROM users WHERE username=%s", (username,))
            record = cur.fetchone()
        finally:
            conn.close()
        if record and check_password_hash(record[0], password):
            session['username'] = username
            flash(f"Welcome back, {username}!", "success")
            return redirect(url_for('dashboard'))
        flash("Invalid username or password.", "error")
        return redirect(url_for('home'))
    except Exception as e:
        flash(f"Login error: {e}", "error")
        return redirect(url_for('home'))

@app.route('/register', methods=['POST'])
def register():
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    confirm  = request.form.get('confirm_password', '')
    if not username or not password:
        flash("Please fill in all fields.", "error")
        return redirect(url_for('register_page'))
    if password != confirm:
        flash("Passwords do not match.", "error")
        return redirect(url_for('register_page'))
    if len(password) < 6:
        flash("Password must be at least 6 characters.", "error")
        return redirect(url_for('register_page'))
    try:
        conn = get_db()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM users WHERE username=%s", (username,))
            if cur.fetchone():
                flash("Username already taken. Try another.", "error")
                return redirect(url_for('register_page'))
            cur.execute("INSERT INTO users (username, password) VALUES (%s, %s)",
                        (username, generate_password_hash(password)))
            conn.commit()
        finally:
            conn.close()
        flash("Account created! Please log in.", "success")
        return redirect(url_for('home'))
    except Exception as e:
        flash(f"Registration error: {e}", "error")
        return redirect(url_for('register_page'))

@app.route('/logout')
def logout():
    session.pop('username', None)
    flash("Logged out successfully.", "success")
    return redirect(url_for('home'))

# ═══════════════════════════════════════════
# DASHBOARD / POSTS
# ═══════════════════════════════════════════
@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('home'))
    search   = request.args.get('search', '').strip()
    category = request.args.get('category', '')
    posts    = []
    try:
        query  = "SELECT * FROM posts WHERE 1=1"
        params = []
        if category:
            query += " AND category = %s"; params.append(category)
        if search:
            query += " AND (LOWER(username) LIKE %s OR LOWER(title) LIKE %s OR LOWER(content) LIKE %s)"
            t = f"%{search.lower()}%"; params += [t, t, t]
        query += " ORDER BY created_at DESC"
        conn = get_db()
        try:
            cur = conn.cursor(); cur.execute(query, params)
            posts = cur.fetchall()
        finally:
            conn.close()
    except Exception as e:
        flash(f"Could not load posts: {e}", "error")
    return render_template('dashboard.html', posts=posts, search=search, category=category)

@app.route('/add_post', methods=['POST'])
def add_post():
    if 'username' not in session:
        return redirect(url_for('home'))
    title    = request.form.get('title', '').strip()
    category = request.form.get('category', '')
    content  = request.form.get('content', '').strip()
    link     = request.form.get('link', '').strip()
    if not title or not content or not category:
        flash("Title, category and content are required.", "error")
        return redirect(url_for('dashboard'))
    try:
        conn = get_db()
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO posts (username, category, title, content, link, doc_path) VALUES (%s,%s,%s,%s,%s,%s)",
                (session['username'], category, title, content, link, ''))
            conn.commit()
        finally:
            conn.close()
        flash("Post shared successfully!", "success")
    except Exception as e:
        flash(f"Could not create post: {e}", "error")
    return redirect(url_for('dashboard'))

@app.route('/delete_post/<int:post_id>', methods=['POST'])
def delete_post(post_id):
    if 'username' not in session:
        return redirect(url_for('home'))
    try:
        conn = get_db()
        try:
            cur = conn.cursor()
            cur.execute("SELECT username FROM posts WHERE id=%s", (post_id,))
            post = cur.fetchone()
            if not post:
                flash("Post not found.", "error")
            elif post[0] != session['username']:
                flash("You can only delete your own posts.", "error")
            else:
                cur.execute("DELETE FROM posts WHERE id=%s", (post_id,))
                conn.commit()
                flash("Post deleted.", "success")
        finally:
            conn.close()
    except Exception as e:
        flash(f"Could not delete post: {e}", "error")
    return redirect(url_for('dashboard'))

# ═══════════════════════════════════════════
# ASSESSMENTS
# ═══════════════════════════════════════════
@app.route('/assessments')
def assessments():
    if 'username' not in session:
        return redirect(url_for('home'))
    try:
        conn = get_db()
        try:
            cur = conn.cursor()
            cur.execute('''
                SELECT a.id, a.creator, a.title, a.description, a.created_at,
                       COUNT(DISTINCT q.id) AS qcount,
                       COUNT(DISTINCT r.id) AS attempts
                FROM assessments a
                LEFT JOIN questions q ON q.assessment_id = a.id
                LEFT JOIN assessment_results r ON r.assessment_id = a.id
                GROUP BY a.id ORDER BY a.created_at DESC
            ''')
            alist = cur.fetchall()
            cur.execute("SELECT DISTINCT assessment_id FROM assessment_results WHERE username=%s",
                        (session['username'],))
            attempted = {r[0] for r in cur.fetchall()}
        finally:
            conn.close()
        return render_template('assessments.html', assessments=alist, attempted=attempted)
    except Exception as e:
        flash(f"Could not load assessments: {e}", "error")
        return render_template('assessments.html', assessments=[], attempted=set())

@app.route('/assessments/create', methods=['GET', 'POST'])
def create_assessment():
    if 'username' not in session:
        return redirect(url_for('home'))
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        desc  = request.form.get('description', '').strip()
        if not title:
            flash("Assessment title is required.", "error")
            return redirect(url_for('create_assessment'))
        questions = []
        i = 1
        while request.form.get(f'question_{i}'):
            qt  = request.form.get(f'question_{i}', '').strip()
            oa  = request.form.get(f'opt_{i}_a', '').strip()
            ob  = request.form.get(f'opt_{i}_b', '').strip()
            oc  = request.form.get(f'opt_{i}_c', '').strip()
            od  = request.form.get(f'opt_{i}_d', '').strip()
            ans = request.form.get(f'correct_{i}', '').upper()
            if qt and oa and ob and ans in ['A','B','C','D']:
                questions.append((qt, oa, ob, oc, od, ans))
            i += 1
        if not questions:
            flash("Add at least one complete question.", "error")
            return redirect(url_for('create_assessment'))
        try:
            conn = get_db()
            try:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO assessments (creator, title, description) VALUES (%s,%s,%s) RETURNING id",
                    (session['username'], title, desc))
                aid = cur.fetchone()[0]
                for q in questions:
                    cur.execute(
                        "INSERT INTO questions (assessment_id,question_text,option_a,option_b,option_c,option_d,correct_answer) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                        (aid, *q))
                conn.commit()
            finally:
                conn.close()
            flash("Assessment created!", "success")
            return redirect(url_for('assessments'))
        except Exception as e:
            flash(f"Could not save assessment: {e}", "error")
            return redirect(url_for('create_assessment'))
    return render_template('create_assessment.html')

@app.route('/assessments/<int:aid>')
def take_assessment(aid):
    if 'username' not in session:
        return redirect(url_for('home'))
    try:
        conn = get_db()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM assessments WHERE id=%s", (aid,))
            assessment = cur.fetchone()
            if not assessment:
                flash("Assessment not found.", "error")
                return redirect(url_for('assessments'))
            cur.execute("SELECT * FROM questions WHERE assessment_id=%s ORDER BY id", (aid,))
            questions = cur.fetchall()
            cur.execute(
                "SELECT score, total, attempted_at FROM assessment_results WHERE username=%s AND assessment_id=%s ORDER BY attempted_at DESC LIMIT 1",
                (session['username'], aid))
            prev = cur.fetchone()
        finally:
            conn.close()
        return render_template('take_assessment.html', assessment=assessment, questions=questions, prev=prev)
    except Exception as e:
        flash(f"Could not load assessment: {e}", "error")
        return redirect(url_for('assessments'))

@app.route('/assessments/<int:aid>/submit', methods=['POST'])
def submit_assessment(aid):
    if 'username' not in session:
        return redirect(url_for('home'))
    try:
        conn = get_db()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, correct_answer FROM questions WHERE assessment_id=%s ORDER BY id", (aid,))
            questions = cur.fetchall()
            score = sum(
                1 for qid, correct in questions
                if request.form.get(f'answer_{qid}', '').upper() == correct
            )
            total = len(questions)
            cur.execute(
                "INSERT INTO assessment_results (username,assessment_id,score,total) VALUES (%s,%s,%s,%s)",
                (session['username'], aid, score, total))
            conn.commit()
        finally:
            conn.close()
        pct = round(score / total * 100) if total else 0
        flash(f"Submitted! Score: {score}/{total} ({pct}%)", "success" if pct >= 50 else "error")
        return redirect(url_for('take_assessment', aid=aid))
    except Exception as e:
        flash(f"Could not submit: {e}", "error")
        return redirect(url_for('assessments'))

# ═══════════════════════════════════════════
# DAILY LEARNING PROGRESS
# ═══════════════════════════════════════════
@app.route('/progress')
def progress():
    if 'username' not in session:
        return redirect(url_for('home'))
    try:
        conn = get_db()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT DATE(created_at)::text, COUNT(*) FROM posts WHERE username=%s AND created_at >= NOW()-INTERVAL '365 days' GROUP BY 1",
                (session['username'],))
            post_days = {r[0]: r[1] for r in cur.fetchall()}
            cur.execute(
                "SELECT DATE(attempted_at)::text, COUNT(*) FROM assessment_results WHERE username=%s AND attempted_at >= NOW()-INTERVAL '365 days' GROUP BY 1",
                (session['username'],))
            assess_days = {r[0]: r[1] for r in cur.fetchall()}
            cur.execute("SELECT COUNT(*) FROM posts WHERE username=%s", (session['username'],))
            total_posts = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*), COALESCE(SUM(score),0), COALESCE(SUM(total),0) FROM assessment_results WHERE username=%s", (session['username'],))
            ta, ts, tt = cur.fetchone()
        finally:
            conn.close()
        activity = {}
        for d, c in post_days.items():
            activity[d] = activity.get(d, 0) + c
        for d, c in assess_days.items():
            activity[d] = activity.get(d, 0) + c
        stats = {
            'total_posts': total_posts,
            'total_assessments': ta or 0,
            'avg_score': round(ts / tt * 100, 1) if tt else 0,
            'active_days': len(activity),
        }
        return render_template('progress.html',
                               activity_data=json.dumps(activity), stats=stats)
    except Exception as e:
        flash(f"Could not load progress: {e}", "error")
        return render_template('progress.html', activity_data='{}', stats={})

# ---------- Local dev only ----------
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
