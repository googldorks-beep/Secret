import os
import sqlite3
import hashlib
import base64
import random
from datetime import datetime
from flask import Flask, render_template, request, session, redirect, abort

app = Flask(__name__)
# Секретный ключ для сессий на Render
app.secret_key = os.environ.get('SECRET_KEY', 'DEBIAN_ELITE_ULTIMATE_2026')

# --- НАСТРОЙКА ПУТЕЙ БД ДЛЯ RENDER ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'database.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        db = conn.cursor()
        # Таблица пользователей
        db.execute('''CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY, 
            password TEXT, 
            role TEXT, 
            status TEXT, 
            avatar TEXT, 
            xp INTEGER, 
            color TEXT)''')
        # Таблица паст
        db.execute('''CREATE TABLE IF NOT EXISTS pastes (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            sender TEXT, 
            title TEXT, 
            content TEXT, 
            style TEXT, 
            likes INTEGER DEFAULT 0, 
            dislikes INTEGER DEFAULT 0, 
            date TEXT)''')
        # Таблица комментариев
        db.execute('''CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            paste_id INTEGER, 
            user TEXT, 
            text TEXT, 
            time TEXT)''')
        conn.commit()

# Запускаем инициализацию при старте
init_db()

@app.context_processor
def inject():
    u = None
    if 'user' in session:
        db = get_db()
        u = db.execute('SELECT * FROM users WHERE username = ?', (session['user'],)).fetchone()
    return dict(current_user=u)

# --- ОСНОВНЫЕ РОУТЫ ---

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
        if not u or not p: return "FIELDS_EMPTY"
        
        hashed = hashlib.sha256(p.encode()).hexdigest()
        # Мутные цвета для обычных юзеров
        muted_color = random.choice(['#556b2f', '#483d8b', '#2f4f4f', '#8b4513', '#4682b4'])
        
        # Авто-назначение OWNER только для твоего ника
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
            return "USER_EXISTS"
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
        # Защита: радужный стиль только для тебя
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

# Исправленный роут лайков (устраняет 404)
@app.route('/action/<int:pid>/<act>')
def action(pid, act):
    db = get_db()
    field = 'likes' if act == 'like' else 'dislikes'
    db.execute(f'UPDATE pastes SET {field} = {field} + 1 WHERE id = ?', (pid,))
    db.commit()
    return redirect(f'/paste/{pid}')

@app.route('/comment/<int:pid>', methods=['POST'])
def comment(pid):
    if 'user' not in session: return redirect('/login')
    txt = request.form.get('txt')
    if txt:
        db = get_db()
        db.execute('INSERT INTO comments (paste_id, user, text, time) VALUES (?,?,?,?)',
                   (pid, session['user'], txt, datetime.now().strftime("%H:%M")))
        db.commit()
    return redirect(f'/paste/{pid}')

@app.route('/profile/<username>')
def profile(username):
    db = get_db()
    u = db.execute('SELECT * FROM users WHERE username = ?', (username.lower(),)).fetchone()
    if not u: abort(404)
    p = db.execute('SELECT * FROM pastes WHERE sender = ?', (username.lower(),)).fetchall()
    return render_template('profile.html', u=u, pastes=p)

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

@app.route('/admin')
def admin():
    if session.get('user') != 'waxues': abort(403)
    db = get_db()
    users = db.execute('SELECT * FROM users').fetchall()
    return render_template('admin.html', users=users)

@app.route('/set_role', methods=['POST'])
def set_role():
    if session.get('user') != 'waxues': abort(403)
    u, r = request.form.get('username'), request.form.get('role')
    if u != 'waxues': # Запрет менять роль самому себе
        db = get_db()
        db.execute('UPDATE users SET role = ? WHERE username = ?', (r, u))
        db.commit()
    return redirect('/admin')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

if __name__ == "__main__":
    # Порт 10000 для Render
    app.run(host='0.0.0.0', port=10000)
