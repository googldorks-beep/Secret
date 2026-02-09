import sqlite3, hashlib, base64, random, os
from datetime import datetime
from flask import Flask, render_template, request, session, redirect, abort

app = Flask(__name__)
# Секретный ключ сессии
app.secret_key = os.environ.get('SECRET_KEY', 'DEBIAN_ELITE_V24_SECURE')

def get_db():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with sqlite3.connect('database.db') as conn:
        db = conn.cursor()
        db.execute('''CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY, password TEXT, role TEXT, 
            status TEXT, avatar TEXT, xp INTEGER, color TEXT)''')
        db.execute('''CREATE TABLE IF NOT EXISTS pastes (
            id INTEGER PRIMARY KEY AUTOINCREMENT, sender TEXT, title TEXT, 
            content TEXT, style TEXT, likes INTEGER DEFAULT 0, 
            dislikes INTEGER DEFAULT 0, date TEXT)''')
        db.execute('''CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT, paste_id INTEGER, 
            user TEXT, text TEXT, time TEXT)''')
        conn.commit()

init_db()

@app.context_processor
def inject():
    u = None
    if 'user' in session:
        db = get_db()
        u = db.execute('SELECT * FROM users WHERE username = ?', (session['user'],)).fetchone()
    return dict(current_user=u)

@app.route('/')
def index():
    db = get_db()
    pastes = db.execute('SELECT * FROM pastes ORDER BY id DESC').fetchall()
    return render_template('index.html', pastes=pastes)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        u = request.form.get('u', '').lower().strip()
        p = request.form.get('p', '')
        if not u or not p: return "Empty fields!"
        
        hashed = hashlib.sha256(p.encode()).hexdigest()
        muted_color = random.choice(['#556b2f', '#483d8b', '#2f4f4f', '#8b4513', '#4682b4'])
        
        # ЖЕСТКАЯ ПРОВЕРКА РОЛИ ПРИ РЕГИСТРАЦИИ
        # Только ник waxues получает OWNER, остальные строго NEWBIE
        role = 'OWNER' if u == 'waxues' else 'NEWBIE'
        status = 'OS_FOUNDER' if u == 'waxues' else 'Node'
        xp = 99999 if u == 'waxues' else 0

        db = get_db()
        try:
            db.execute('INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, ?)', 
                       (u, hashed, role, status, '', xp, muted_color))
            db.commit()
            return redirect('/login')
        except sqlite3.IntegrityError:
            return "Error: User already exists!"
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = request.form.get('u', '').lower().strip()
        p = request.form.get('p', '')
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE username = ?', (u,)).fetchone()
        if user and user['password'] == hashlib.sha256(p.encode()).hexdigest():
            session['user'] = u
            session['role'] = user['role']
            return redirect('/')
    return render_template('login.html')

@app.route('/add', methods=['GET', 'POST'])
def add():
    if 'user' not in session: return redirect('/login')
    if request.method == 'POST':
        style = request.form.get('style')
        # Запрет радужного стиля для всех, кроме тебя
        if style == 'glow-rainbow' and session.get('user') != 'waxues':
            style = 'glow-red'
        
        db = get_db()
        db.execute('INSERT INTO pastes (sender, title, content, style, date) VALUES (?,?,?,?,?)',
                   (session['user'], request.form.get('t'), request.form.get('c'), 
                    style, datetime.now().strftime("%H:%M")))
        db.commit()
        return redirect('/')
    return render_template('add.html')

@app.route('/paste/<int:pid>')
def view_paste(pid):
    db = get_db()
    p = db.execute('SELECT * FROM pastes WHERE id = ?', (pid,)).fetchone()
    if not p: abort(404)
    coms = db.execute('SELECT * FROM comments WHERE paste_id = ?', (pid,)).fetchall()
    return render_template('view.html', p=p, comments=coms)

@app.route('/admin')
def admin():
    # Проверка по сессии и по БД для безопасности
    if session.get('user') != 'waxues': abort(403)
    db = get_db()
    users = db.execute('SELECT * FROM users').fetchall()
    return render_template('admin.html', users=users)

@app.route('/set_role', methods=['POST'])
def set_role():
    if session.get('user') != 'waxues': abort(403)
    u, r = request.form.get('username'), request.form.get('role')
    if u == 'waxues': return redirect('/admin') # Запрет менять роль самому себе
    db = get_db()
    db.execute('UPDATE users SET role = ? WHERE username = ?', (r, u))
    db.commit()
    return redirect('/admin')

@app.route('/upload_avatar', methods=['POST'])
def upload_avatar():
    if 'user' not in session: return redirect('/login')
    file = request.files.get('avatar')
    if file:
        img_b64 = f"data:{file.content_type};base64,{base64.b64encode(file.read()).decode()}"
        db = get_db()
        db.execute('UPDATE users SET avatar = ? WHERE username = ?', (img_b64, session['user']))
        db.commit()
    return redirect(f"/profile/{session['user']}")

@app.route('/profile/<username>')
def profile(username):
    db = get_db()
    u = db.execute('SELECT * FROM users WHERE username = ?', (username.lower(),)).fetchone()
    if not u: abort(404)
    p = db.execute('SELECT * FROM pastes WHERE sender = ?', (username.lower(),)).fetchall()
    return render_template('profile.html', u=u, pastes=p)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=10000)
