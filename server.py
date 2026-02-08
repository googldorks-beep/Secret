import os, hashlib, base64
from flask import Flask, render_template, request, session, redirect, url_for, abort

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    pass

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'STABLE_V330_FINAL')
DB_URL = os.environ.get('DATABASE_URL')

def get_db():
    if not DB_URL: return None
    try:
        # Добавляем таймаут, чтобы запросы не висели вечно
        conn = psycopg2.connect(DB_URL, cursor_factory=RealDictCursor, connect_timeout=5)
        return conn
    except Exception as e:
        print(f"DB_ERROR: {e}")
        return None

@app.route('/')
def index():
    conn = get_db()
    if not conn: return "Database connection failed"
    cur = conn.cursor()
    cur.execute("SELECT * FROM pastes ORDER BY created_at DESC")
    p = cur.fetchall()
    cur.close(); conn.close()
    return render_template('index.html', pastes=p)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = request.form.get('u').strip()
        p = request.form.get('p').strip()
        h = hashlib.sha256(p.encode()).hexdigest()
        
        conn = get_db()
        if not conn: return "Database Error"
        
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username=%s AND password_hash=%s", (u, h))
        user = cur.fetchone()
        cur.close(); conn.close()
        
        if user:
            session.clear() # Полная очистка перед созданием новой сессии
            session['user'] = user['username']
            session['role'] = user['role']
            session['bg'] = user['bg_url']
            session['avatar'] = user['avatar_url']
            session.permanent = True # Делаем сессию устойчивой
            print(f"User {u} logged in successfully")
            return redirect('/') # Прямой редирект на главную
        else:
            return "Invalid login or password. <a href='/login'>Try again</a>"
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/profile/<username>')
def profile(username):
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username=%s", (username,))
    u = cur.fetchone()
    if not u: abort(404)
    cur.execute("SELECT * FROM pastes WHERE sender=%s ORDER BY created_at DESC", (username,))
    p = cur.fetchall(); cur.close(); conn.close()
    return render_template('profile.html', u=u, pastes=p)

# Остальные маршруты (add, users, vote) подхватятся автоматически
@app.route('/users')
def users_list():
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT username, avatar_url, status, role FROM users ORDER BY reg_date DESC")
    u = cur.fetchall(); cur.close(); conn.close()
    return render_template('users.html', users=u)

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

@app.route('/paste/<int:pid>', methods=['GET', 'POST'])
def view_paste(pid):
    conn = get_db(); cur = conn.cursor()
    cur.execute("UPDATE pastes SET views = views + 1 WHERE id = %s", (pid,))
    cur.execute("SELECT * FROM pastes WHERE id = %s", (pid,))
    p = cur.fetchone()
    if not p: abort(404)
    cur.execute("SELECT * FROM comments WHERE paste_id = %s ORDER BY created_at DESC", (pid,))
    c = cur.fetchall(); cur.close(); conn.close()
    return render_template('view.html', p=p, comments=c)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))
