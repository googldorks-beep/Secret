import os, hashlib, functools
from datetime import datetime
from flask import Flask, render_template, request, session, redirect, url_for, flash, abort

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    pass

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'ULTRA_STABLE_V190_FIXED')
DB_URL = os.environ.get('DATABASE_URL')

def get_db():
    if not DB_URL: return None
    try:
        conn = psycopg2.connect(DB_URL, cursor_factory=RealDictCursor, connect_timeout=10)
        return conn
    except Exception as e:
        print(f"DB CONNECTION ERROR: {e}")
        return None

def init_db():
    """Сносим старое и ставим правильное"""
    conn = get_db()
    if not conn: return
    cur = conn.cursor()
    
    # ВНИМАНИЕ: Если нужно сохранить старые пасты, удали следуюбую строку.
    # Но для исправления ошибки 500 лучше очистить структуру:
    cur.execute("DROP TABLE IF EXISTS pastes CASCADE;")
    cur.execute("DROP TABLE IF EXISTS users CASCADE;")

    # Создаем таблицу пользователей заново
    cur.execute("""CREATE TABLE users (
        id SERIAL PRIMARY KEY, 
        username TEXT UNIQUE NOT NULL, 
        password_hash TEXT NOT NULL, 
        role TEXT DEFAULT 'User', 
        bg_url TEXT DEFAULT '', 
        music_url TEXT DEFAULT '',
        reg_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    # Создаем таблицу паст с той самой колонкой created_at
    cur.execute("""CREATE TABLE pastes (
        id SERIAL PRIMARY KEY, 
        sender TEXT NOT NULL, 
        title TEXT NOT NULL, 
        content TEXT NOT NULL, 
        style TEXT DEFAULT 'dark-blue', 
        views INTEGER DEFAULT 0, 
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    # Твой аккаунт waxues (Пароль: root)
    h = hashlib.sha256("root".encode()).hexdigest()
    cur.execute("INSERT INTO users (username, password_hash, role) VALUES ('waxues', %s, 'Owner') ON CONFLICT DO NOTHING", (h,))
    
    conn.commit()
    cur.close()
    conn.close()
    print("[SYSTEM] Database Rebuilt V190 Successfully")

@app.route('/')
def index():
    conn = get_db()
    if not conn: return "Database Offline", 503
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM pastes ORDER BY created_at DESC")
        pastes = cur.fetchall()
        return render_template('index.html', pastes=pastes)
    except Exception as e:
        return f"<h1>DB Error</h1><p>{str(e)}</p>", 500
    finally:
        cur.close(); conn.close()

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
