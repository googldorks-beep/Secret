import os, hashlib, base64
from flask import Flask, render_template, request, session, redirect, url_for, abort

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    pass

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'ABSOLUTE_V300')
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

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u, p = request.form.get('u'), request.form.get('p')
        h = hashlib.sha256(p.encode()).hexdigest()
        conn = get_db(); cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username=%s AND password_hash=%s", (u, h))
        user = cur.fetchone(); cur.close(); conn.close()
        if user:
            session.update({'user':user['username'], 'role':user['role'], 'bg':user['bg_url'], 'avatar':user['avatar_url']})
            return redirect('/')
    return render_template('login.html')

@app.route('/admin')
def admin():
    # Жесткая проверка: роль должна быть Owner
    if session.get('role') != 'Owner': 
        return "ACCESS_DENIED: REQUIRED_ROLE_OWNER", 403
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT * FROM pastes ORDER BY id DESC")
    p = cur.fetchall()
    cur.execute("SELECT * FROM users ORDER BY reg_date DESC")
    u = cur.fetchall(); cur.close(); conn.close()
    return render_template('admin.html', pastes=p, users=u)

@app.route('/paste/<int:pid>', methods=['GET', 'POST'])
def view_paste(pid):
    conn = get_db(); cur = conn.cursor()
    if request.method == 'POST' and 'user' in session:
        txt = request.form.get('comment')
        cur.execute("INSERT INTO comments (paste_id, sender, text) VALUES (%s,%s,%s)", (pid, session['user'], txt))
        conn.commit()
    cur.execute("UPDATE pastes SET views = views + 1 WHERE id = %s", (pid,))
    cur.execute("SELECT * FROM pastes WHERE id = %s", (pid,))
    p = cur.fetchone()
    if not p: abort(404)
    cur.execute("SELECT * FROM comments WHERE paste_id = %s ORDER BY created_at DESC", (pid,))
    c = cur.fetchall(); cur.close(); conn.close()
    return render_template('view.html', p=p, comments=c)

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
        session['avatar'] = avatar_url
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

# Остальные маршруты (users, profile, logout) оставляем без изменений
@app.route('/users')
def users_list():
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT username, avatar_url, status, role FROM users ORDER BY reg_date DESC")
    u = cur.fetchall(); cur.close(); conn.close()
    return render_template('users.html', users=u)

@app.route('/profile/<username>')
def profile(username):
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username=%s", (username,))
    u = cur.fetchone()
    if not u: abort(404)
    cur.execute("SELECT * FROM pastes WHERE sender=%s ORDER BY created_at DESC", (username,))
    p = cur.fetchall(); cur.close(); conn.close()
    return render_template('profile.html', u=u, pastes=p)

@app.route('/logout')
def logout(): session.clear(); return redirect('/')

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))
