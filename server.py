import os, hashlib, functools
from datetime import datetime
from flask import Flask, render_template, request, session, redirect, url_for, flash, abort

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    pass

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'GENESIS_V280_STABLE')
DB_URL = os.environ.get('DATABASE_URL')

def get_db():
    if not DB_URL: return None
    try:
        conn = psycopg2.connect(DB_URL, cursor_factory=RealDictCursor, connect_timeout=10)
        return conn
    except: return None

@app.route('/')
def index():
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT * FROM pastes ORDER BY created_at DESC")
    p = cur.fetchall(); cur.close(); conn.close()
    return render_template('index.html', pastes=p)

@app.route('/users')
def users_list():
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT username, avatar_url, status, role FROM users ORDER BY reg_date DESC")
    u = cur.fetchall(); cur.close(); conn.close()
    return render_template('users.html', users=u)

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
        except: return "User exists"
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

@app.route('/update_avatar', methods=['POST'])
def update_avatar():
    if 'user' not in session: return redirect('/login')
    new_av = request.form.get('avatar_url')
    conn = get_db(); cur = conn.cursor()
    cur.execute("UPDATE users SET avatar_url=%s WHERE username=%s", (new_av, session['user']))
    conn.commit(); cur.close(); conn.close()
    session['avatar'] = new_av
    return redirect(f"/profile/{session['user']}")

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

@app.route('/admin')
def admin():
    if session.get('role') != 'Owner': abort(403)
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT * FROM pastes ORDER BY id DESC")
    p = cur.fetchall()
    cur.execute("SELECT * FROM users ORDER BY reg_date DESC")
    u = cur.fetchall(); cur.close(); conn.close()
    return render_template('admin.html', pastes=p, users=u)

@app.route('/delete_paste/<int:pid>')
def delete_paste(pid):
    if session.get('role') not in ['Owner', 'Admin']: abort(403)
    conn = get_db(); cur = conn.cursor()
    cur.execute("DELETE FROM pastes WHERE id = %s", (pid,))
    conn.commit(); cur.close(); conn.close()
    return redirect('/admin')

@app.route('/logout')
def logout(): session.clear(); return redirect('/')

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))
