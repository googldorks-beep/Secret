import os, hashlib, functools
from datetime import datetime
from flask import Flask, render_template, request, session, redirect, url_for, flash, abort

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    pass

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'TOTAL_V220_WAXUES')
DB_URL = os.environ.get('DATABASE_URL')

def get_db():
    if not DB_URL: return None
    try:
        conn = psycopg2.connect(DB_URL, cursor_factory=RealDictCursor, connect_timeout=10)
        return conn
    except: return None

def init_db():
    conn = get_db()
    if not conn: return
    cur = conn.cursor()
    # Обновляем структуру: добавляем avatar_url и таблицу банов
    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url TEXT DEFAULT ''")
    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_banned BOOLEAN DEFAULT FALSE")
    cur.execute("""CREATE TABLE IF NOT EXISTS pastes (
        id SERIAL PRIMARY KEY, sender TEXT, title TEXT, content TEXT, 
        style TEXT DEFAULT 'dark-blue', views INTEGER DEFAULT 0, 
        likes INTEGER DEFAULT 0, dislikes INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS comments (
        id SERIAL PRIMARY KEY, paste_id INTEGER REFERENCES pastes(id) ON DELETE CASCADE,
        sender TEXT, text TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.commit(); cur.close(); conn.close()

@app.route('/')
def index():
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT * FROM pastes ORDER BY created_at DESC")
    p = cur.fetchall(); cur.close(); conn.close()
    return render_template('index.html', pastes=p)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        u, p = request.form.get('u'), request.form.get('p')
        h = hashlib.sha256(p.encode()).hexdigest()
        conn = get_db(); cur = conn.cursor()
        try:
            cur.execute("INSERT INTO users (username, password_hash) VALUES (%s, %s)", (u, h))
            conn.commit()
            return redirect('/login')
        except: flash("User already exists!")
        finally: cur.close(); conn.close()
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u, p = request.form.get('u'), request.form.get('p')
        h = hashlib.sha256(p.encode()).hexdigest()
        conn = get_db(); cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username=%s AND password_hash=%s", (u, h))
        user = cur.fetchone(); cur.close(); conn.close()
        if user:
            if user['is_banned']: return "YOU ARE BANNED"
            session.update({'user':user['username'], 'role':user['role'], 'bg':user['bg_url'], 'music':user['music_url'], 'avatar':user['avatar_url']})
            return redirect('/')
    return render_template('login.html')

@app.route('/profile/<username>')
def profile(username):
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username=%s", (username,))
    u = cur.fetchone()
    if not u: abort(404)
    cur.execute("SELECT * FROM pastes WHERE sender=%s ORDER BY created_at DESC", (username,))
    p = cur.fetchall(); cur.close(); conn.close()
    return render_template('profile.html', u=u, pastes=p)

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if 'user' not in session: return redirect('/login')
    if request.method == 'POST':
        bg, mu, st, av = request.form.get('bg'), request.form.get('mu'), request.form.get('st'), request.form.get('av')
        conn = get_db(); cur = conn.cursor()
        cur.execute("UPDATE users SET bg_url=%s, music_url=%s, status=%s, avatar_url=%s WHERE username=%s", (bg, mu, st, av, session['user']))
        conn.commit(); cur.close(); conn.close()
        session.update({'bg':bg, 'music':mu, 'avatar':av})
    return render_template('settings.html')

@app.route('/admin')
def admin():
    if session.get('role') != 'Owner': abort(403)
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT * FROM users ORDER BY id DESC")
    u = cur.fetchall()
    cur.execute("SELECT * FROM pastes ORDER BY id DESC")
    p = cur.fetchall(); cur.close(); conn.close()
    return render_template('admin.html', users=u, pastes=p)

@app.route('/ban/<username>')
def ban(username):
    if session.get('role') != 'Owner': abort(403)
    conn = get_db(); cur = conn.cursor()
    cur.execute("UPDATE users SET is_banned = NOT is_banned WHERE username=%s", (username,))
    conn.commit(); cur.close(); conn.close()
    return redirect('/admin')

@app.route('/paste/<int:pid>')
def view(pid):
    conn = get_db(); cur = conn.cursor()
    cur.execute("UPDATE pastes SET views = views + 1 WHERE id = %s", (pid,))
    cur.execute("SELECT * FROM pastes WHERE id = %s", (pid,))
    p = cur.fetchone()
    cur.execute("SELECT * FROM comments WHERE paste_id = %s ORDER BY created_at DESC", (pid,))
    c = cur.fetchall(); cur.close(); conn.close()
    if not p: abort(404)
    return render_template('view.html', p=p, comments=c)

@app.route('/add', methods=['GET', 'POST'])
def add():
    if 'user' not in session: return redirect('/login')
    if request.method == 'POST':
        t, c, s = request.form.get('t'), request.form.get('c'), request.form.get('style')
        conn = get_db(); cur = conn.cursor()
        cur.execute("INSERT INTO pastes (sender, title, content, style) VALUES (%s,%s,%s,%s)", (session['user'], t, c, s))
        conn.commit(); cur.close(); conn.close()
        return redirect('/')
    return render_template('add.html')

@app.route('/logout')
def logout(): session.clear(); return redirect('/')

if __name__ == "__main__":
    init_db()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))
