import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3, string, random

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret')


# -----------------------------
# Database Initialization
# -----------------------------
def init_db():
    DB_PATH = os.path.join(os.path.dirname(__file__), "database.db")
    conn = sqlite3.connect(DB_PATH)   # ✅ connect to DB
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS urls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            original TEXT NOT NULL,
            short TEXT UNIQUE NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')
    conn.commit()
    conn.close()

# Call initialization once at startup
init_db()


# -----------------------------
# URL Shortener Logic
# -----------------------------
def generate_short_code(length=6):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def generate_unique_short_code():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    while True:
        code = generate_short_code()
        c.execute('SELECT 1 FROM urls WHERE short = ?', (code,))
        if not c.fetchone():
            conn.close()
            return code


# -----------------------------
# Routes
# -----------------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    short_url = None

    # Handle URL shortening
    if request.method == 'POST' and 'shorten' in request.form:
        original_url = request.form['url_to_shorten']
        short_code = generate_unique_short_code()
        # Save URL with no user (or user_id=None)
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute('INSERT INTO urls (user_id, original, short) VALUES (?, ?, ?)',
                  (None, original_url, short_code))
        conn.commit()
        conn.close()
        short_url = request.host_url + short_code

    # Handle login
    if request.method == 'POST' and 'login' in request.form:
        uname = request.form['username']
        pwd = request.form['password']

        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute('SELECT id, password FROM users WHERE username = ?', (uname,))
        user = c.fetchone()
        conn.close()

        if user and check_password_hash(user[1], pwd):
            session['user_id'] = user[0]
            session['username'] = uname
            flash('Login successful', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid credentials', 'error')

    return render_template('login.html', short_url=short_url)



@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT original, short FROM urls WHERE user_id = ?', (session['user_id'],))
    urls = c.fetchall()
    conn.close()

    return render_template('index.html', urls=urls)


@app.route('/shorten', methods=['POST'])
def shorten():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    original_url = request.form['url']
    short_code = generate_unique_short_code()

    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('INSERT INTO urls (user_id, original, short) VALUES (?, ?, ?)',
              (session['user_id'], original_url, short_code))
    conn.commit()
    conn.close()

    short_url = request.host_url + short_code
    return render_template('shortened.html', short_url=short_url)
    return render_template('login.html', short_url=short_url)



@app.route('/<short_code>')
def redirect_url(short_code):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT original FROM urls WHERE short=?", (short_code,))
    result = c.fetchone()
    conn.close()
    if result:
        return redirect(result[0])
    else:
        return render_template('404.html'), 404


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        uname = request.form['username']
        pwd = request.form['password']
        hashed = generate_password_hash(pwd)

        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        try:
            c.execute('INSERT INTO users (username, password) VALUES (?, ?)', (uname, hashed))
            conn.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username already exists.', 'error')
        finally:
            conn.close()
    return render_template('register.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out.', 'info')
    return redirect(url_for('login'))


@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404


@app.route("/healthz")
def health_check():
    return "OK", 200


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
