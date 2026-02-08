import os, hashlib, base64, random
from flask import Flask, render_template, request, session, redirect, url_for, abort

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'FINAL_FIX_V360')
DB_URL = os.environ.get('DATABASE_URL')

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    pass

def get_db():
    if not DB_URL: return None
    try:
        return psycopg2.connect(DB_URL, cursor_factory=RealDictCursor, connect_timeout=5)
    except: return None

@app.context_processor
def inject_user():
    user_data = None
    if 'user' in session:
        conn = get_db()
        if conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE username=%s", (session['user'],))
            user_data = cur.fetchone()
            cur.close(); conn.close()
    return dict(current_user=user_data)

@app.route('/')
def index():
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT * FROM pastes ORDER BY created_at DESC")
    p = cur.fetchall(); cur.close(); conn.close()
    return render_template('index.html', pastes=p, online=random.randint(8,14))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u, p = request.form.get('u').strip(), request.form.get('p').strip()
        h = hashlib.sha256(p.encode()).hexdigest()
        conn = get_db(); cur = conn.cursor()
        cur.execute("SELECT username, role FROM users WHERE username=%s AND password_hash=%s", (u, h))
        user = cur.fetchone(); cur.close(); conn.close()
        if user:
            session.clear()
            session['user'] = user['username']
            session['role'] = user['role']
            return redirect('/')
    return render_template('login.html', online=random.randint(8,14))

@app.route('/paste/<int:pid>')
def view_paste(pid):
    conn = get_db(); cur = conn.cursor()
    cur.execute("UPDATE pastes SET views = views + 1 WHERE id = %s", (pid,))
    conn.commit()
    cur.execute("SELECT * FROM pastes WHERE id = %s", (pid,))
    p = cur.fetchone()
    cur.execute("SELECT * FROM comments WHERE paste_id = %s ORDER BY created_at DESC", (pid,))
    c = cur.fetchall(); cur.close(); conn.close()
    return render_template('view.html', p=p, comments=c, online=random.randint(8,14))

@app.route('/add', methods=['GET', 'POST'])
def add():
    if 'user' not in session: return redirect('/login')
    if request.method == 'POST':
        t, c, s = request.form.get('t'), request.form.get('c'), request.form.get('style')
        conn = get_db(); cur = conn.cursor()
        cur.execute("INSERT INTO pastes (sender, title, content, style, views) VALUES (%s,%s,%s,%s,0)", (session['user'], t, c, s))
        conn.commit(); cur.close(); conn.close()
        return redirect('/')
    return render_template('add.html', online=random.randint(8,14))

@app.route('/profile/<username>')
def profile(username):
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username=%s", (username,))
    u = cur.fetchone()
    cur.execute("SELECT * FROM pastes WHERE sender=%s ORDER BY created_at DESC", (username,))
    p = cur.fetchall(); cur.close(); conn.close()
    return render_template('profile.html', u=u, pastes=p, online=random.randint(8,14))

@app.route('/logout')
def logout(): session.clear(); return redirect('/')

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
