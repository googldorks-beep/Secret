import os, hashlib, functools
from datetime import datetime
from flask import Flask, render_template, request, session, redirect, url_for, flash, abort

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    pass

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'STABLE_V170_ULTRA_KEY')
DB_URL = os.environ.get('DATABASE_URL')

def get_db():
    try:
        conn = psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)
        return conn
    except Exception as e:
        print(f"DATABASE CONNECTION ERROR: {e}")
        return None

def init_db():
    conn = get_db()
    if not conn: return
    cur = conn.cursor()
    # Пользователи: роли, фоны, музыка
    cur.execute("""CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY, username TEXT UNIQUE, password_hash TEXT, 
        role TEXT DEFAULT 'User', bg_url TEXT DEFAULT '', music_url TEXT DEFAULT ''
    )""")
    # Пасты: стили, просмотры, даты
    cur.execute("""CREATE TABLE IF NOT EXISTS pastes (
        id SERIAL PRIMARY KEY, sender TEXT, title TEXT, content TEXT, 
        style TEXT DEFAULT 'dark-blue', views INTEGER DEFAULT 0, 
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    # Твой аккаунт (Пароль: root)
    h = hashlib.sha256("root".encode()).hexdigest()
    cur.execute("INSERT INTO users (username, password_hash, role) VALUES ('waxues', %s, 'Owner') ON CONFLICT DO NOTHING", (h,))
    conn.commit(); cur.close(); conn.close()

@app.route('/')
def index():
    conn = get_db()
    if not conn: return "Database connection failed (500 Error)", 500
    cur = conn.cursor()
    cur.execute("SELECT * FROM pastes ORDER BY created_at DESC")
    pastes = cur.fetchall()
    cur.close(); conn.close()
    return render_template('index.html', pastes=pastes)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u, p = request.form.get('u'), request.form.get('p')
        h = hashlib.sha256(p.encode()).hexdigest()
        conn = get_db(); cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username=%s AND password_hash=%s", (u, h))
        user = cur.fetchone(); cur.close(); conn.close()
        if user:
            session.update({'user':user['username'], 'role':user['role'], 'bg':user['bg_url'], 'music':user['music_url']})
            return redirect('/')
    return render_template('login.html')

@app.route('/add', methods=['GET', 'POST'])
def add():
    if 'user' not in session: return redirect('/login')
    if request.method == 'POST':
        t, c, s = request.form.get('t'), request.form.get('c'), request.form.get('style')
        if s == 'rainbow' and session.get('role') != 'Owner': s = 'dark-blue'
        conn = get_db(); cur = conn.cursor()
        cur.execute("INSERT INTO pastes (sender, title, content, style) VALUES (%s,%s,%s,%s)", (session['user'], t, c, s))
        conn.commit(); cur.close(); conn.close()
        return redirect('/')
    return render_template('add.html')

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if 'user' not in session: return redirect('/login')
    if request.method == 'POST':
        bg, mu = request.form.get('bg'), request.form.get('mu')
        conn = get_db(); cur = conn.cursor()
        cur.execute("UPDATE users SET bg_url=%s, music_url=%s WHERE username=%s", (bg, mu, session['user']))
        conn.commit(); cur.close(); conn.close()
        session['bg'], session['music'] = bg, mu
        return redirect('/settings')
    return render_template('settings.html')

@app.route('/paste/<int:pid>')
def view(pid):
    conn = get_db(); cur = conn.cursor()
    cur.execute("UPDATE pastes SET views = views + 1 WHERE id = %s", (pid,))
    cur.execute("SELECT * FROM pastes WHERE id = %s", (pid,))
    p = cur.fetchone(); cur.close(); conn.close()
    if not p: abort(404)
    return render_template('view.html', p=p)

@app.route('/logout')
def logout(): session.clear(); return redirect('/')

if __name__ == "__main__":
    init_db()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))
