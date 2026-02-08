import os, hashlib, base64, random
from flask import Flask, render_template, request, session, redirect, url_for, abort

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    pass

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'SLIM_V350_STABLE')
DB_URL = os.environ.get('DATABASE_URL')

def get_db():
    if not DB_URL: return None
    try:
        conn = psycopg2.connect(DB_URL, cursor_factory=RealDictCursor, connect_timeout=5)
        return conn
    except: return None

# Функция для получения данных юзера БЕЗ хранения их в сессии (чтобы не раздувать куки)
def get_current_user():
    if 'user' not in session: return None
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username=%s", (session['user'],))
    u = cur.fetchone(); cur.close(); conn.close()
    return u

@app.context_processor
def inject_user():
    return dict(current_user=get_current_user())

@app.route('/')
def index():
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT * FROM pastes ORDER BY created_at DESC")
    p = cur.fetchall(); cur.close(); conn.close()
    return render_template('index.html', pastes=p, online=random.randint(5,15))

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
        return "ACCESS_DENIED"
    return render_template('login.html', online=random.randint(5,15))

@app.route('/update_avatar', methods=['POST'])
def update_avatar():
    if 'user' not in session: return redirect('/login')
    file = request.files.get('avatar_file')
    if file:
        img_data = base64.b64encode(file.read()).decode('utf-8')
        avatar_url = f"data:{file.content_type};base64,{img_data}"
        conn = get_db(); cur = conn.cursor()
        cur.execute("UPDATE users SET avatar_url=%s WHERE username=%s", (avatar_url, session['user']))
        conn.commit(); cur.close(); conn.close()
    return redirect(f"/profile/{session['user']}")

@app.route('/paste/<int:pid>')
def view_paste(pid):
    conn = get_db(); cur = conn.cursor()
    cur.execute("UPDATE pastes SET views = views + 1 WHERE id = %s", (pid,))
    conn.commit()
    cur.execute("SELECT * FROM pastes WHERE id = %s", (pid,))
    p = cur.fetchone()
    cur.execute("SELECT * FROM comments WHERE paste_id = %s ORDER BY created_at DESC", (pid,))
    c = cur.fetchall(); cur.close(); conn.close()
    return render_template('view.html', p=p, comments=c)

@app.route('/logout')
def logout(): session.clear(); return redirect('/')

# Остальные роуты (profile, users, add) теперь должны использовать current_user в шаблонах
@app.route('/profile/<username>')
def profile(username):
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username=%s", (username,))
    u = cur.fetchone()
    cur.execute("SELECT * FROM pastes WHERE sender=%s ORDER BY created_at DESC", (username,))
    p = cur.fetchall(); cur.close(); conn.close()
    return render_template('profile.html', u=u, pastes=p)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
