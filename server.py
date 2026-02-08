import os, hashlib, base64, random
from flask import Flask, render_template, request, session, redirect, url_for, abort

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    pass

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'SUPER_STABLE_V340')
DB_URL = os.environ.get('DATABASE_URL')

def get_db():
    if not DB_URL: return None
    try:
        conn = psycopg2.connect(DB_URL, cursor_factory=RealDictCursor, connect_timeout=5)
        return conn
    except: return None

# Имитация онлайна (для красоты и функционала)
def get_online_count():
    return random.randint(3, 12) # Можно позже привязать к реальной таблице активностей

@app.route('/')
def index():
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT * FROM pastes ORDER BY created_at DESC")
    p = cur.fetchall(); cur.close(); conn.close()
    return render_template('index.html', pastes=p, online=get_online_count())

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = request.form.get('u').strip()
        p = request.form.get('p').strip()
        h = hashlib.sha256(p.encode()).hexdigest()
        
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username=%s AND password_hash=%s", (u, h))
        user = cur.fetchone()
        cur.close(); conn.close()
        
        if user:
            session.clear()
            session['user'] = user['username']
            session['role'] = user['role']
            session['avatar'] = user['avatar_url']
            session['bg'] = user['bg_url']
            return redirect('/')
        else:
            return "ОШИБКА ДОСТУПА. <a href='/login'>ПОВТОР</a>"
    return render_template('login.html', online=get_online_count())

@app.route('/paste/<int:pid>')
def view_paste(pid):
    conn = get_db(); cur = conn.cursor()
    # Увеличиваем просмотры ПРИ КАЖДОМ заходя на страницу
    cur.execute("UPDATE pastes SET views = views + 1 WHERE id = %s", (pid,))
    conn.commit()
    
    cur.execute("SELECT * FROM pastes WHERE id = %s", (pid,))
    p = cur.fetchone()
    if not p: abort(404)
    
    cur.execute("SELECT * FROM comments WHERE paste_id = %s ORDER BY created_at DESC", (pid,))
    c = cur.fetchall(); cur.close(); conn.close()
    return render_template('view.html', p=p, comments=c, online=get_online_count())

@app.route('/add', methods=['GET', 'POST'])
def add():
    if 'user' not in session: return redirect('/login')
    if request.method == 'POST':
        t, c, s = request.form.get('t'), request.form.get('c'), request.form.get('style')
        conn = get_db(); cur = conn.cursor()
        cur.execute("INSERT INTO pastes (sender, title, content, style, views) VALUES (%s,%s,%s,%s,0)", (session['user'], t, c, s))
        conn.commit(); cur.close(); conn.close()
        return redirect('/')
    return render_template('add.html', online=get_online_count())

@app.route('/users')
def users_list():
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT * FROM users ORDER BY reg_date DESC")
    u = cur.fetchall(); cur.close(); conn.close()
    return render_template('users.html', users=u, online=get_online_count())

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))
