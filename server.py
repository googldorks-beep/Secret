# -*- coding: utf-8 -*-
import os
import hashlib
import uuid
import functools
from datetime import datetime
from flask import Flask, render_template, request, session, redirect, url_for, flash, abort, make_response

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    print("[!] Error: psycopg2 is not installed. Use 'pip install psycopg2-binary'")

# --- КОНФИГУРАЦИЯ СИСТЕМЫ ---
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'BYTEBIN_CORE_SECURE_TOKEN_V160_FULL_BUILD_2026')
app.config['PERMANENT_SESSION_LIFETIME'] = 86400  # Сессия на 24 часа

# URL Базы данных из переменных окружения Render
DATABASE_URL = os.environ.get('DATABASE_URL')

def db_interaction(func):
    """Декоратор для автоматического управления соединением с БД"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        conn = None
        try:
            conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
            result = func(conn, *args, **kwargs)
            conn.commit()
            return result
        except Exception as e:
            if conn: conn.rollback()
            print(f"[SYSTEM ERROR] Database failure in {func.__name__}: {e}")
            return None
        finally:
            if conn: conn.close()
    return wrapper

@db_interaction
def init_db(conn):
    """Инициализация структуры таблиц с проверкой целостности"""
    cur = conn.cursor()
    # Таблица пользователей
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'User',
            bg_url TEXT DEFAULT 'https://i.imgur.com/8QWvX9G.jpeg',
            music_url TEXT DEFAULT '',
            status_message TEXT DEFAULT 'System Operator',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Таблица паст
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pastes (
            id SERIAL PRIMARY KEY,
            sender TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            style TEXT DEFAULT 'dark-blue',
            views INTEGER DEFAULT 0,
            is_private BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Таблица логов доступа
    cur.execute("""
        CREATE TABLE IF NOT EXISTS access_logs (
            id SERIAL PRIMARY KEY,
            ip_address TEXT,
            user_agent TEXT,
            access_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Создание элитного аккаунта waxues (password: root)
    root_h = hashlib.sha256("root".encode()).hexdigest()
    cur.execute("""
        INSERT INTO users (username, password_hash, role) 
        VALUES ('waxues', %s, 'Owner') 
        ON CONFLICT (username) DO NOTHING
    """, (root_h,))
    print("[+] Database Core V160 Initialized Successfully")

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def login_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- ОБРАБОТЧИКИ МАРШРУТОВ ---
@app.route('/')
@db_interaction
def index(conn):
    cur = conn.cursor()
    cur.execute("SELECT * FROM pastes ORDER BY created_at DESC LIMIT 50")
    pastes = cur.fetchall()
    
    # Логирование визита
    cur.execute("INSERT INTO access_logs (ip_address, user_agent) VALUES (%s, %s)", 
                (request.remote_addr, request.user_agent.string))
    
    return render_template('index.html', pastes=pastes)

@app.route('/login', methods=['GET', 'POST'])
@db_interaction
def login(conn):
    if request.method == 'POST':
        username = request.form.get('u', '').strip()
        password = request.form.get('p', '')
        pw_hash = hashlib.sha256(password.encode()).hexdigest()
        
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username=%s AND password_hash=%s", (username, pw_hash))
        user = cur.fetchone()
        
        if user:
            session.permanent = True
            session['user'] = user['username']
            session['role'] = user['role']
            session['bg'] = user['bg_url']
            session['music'] = user['music_url']
            flash(f"Welcome back, {username}", "success")
            return redirect(url_for('index'))
        flash("CRITICAL ERROR: ACCESS DENIED", "danger")
    return render_template('login.html')

@app.route('/add', methods=['GET', 'POST'])
@login_required
@db_interaction
def add_paste(conn):
    if request.method == 'POST':
        title = request.form.get('t', 'Untitled').strip()
        content = request.form.get('c', '').strip()
        style = request.form.get('style', 'dark-blue')
        
        # Валидация прав на элитные стили
        if style == 'rainbow' and session.get('role') != 'Owner':
            style = 'dark-blue'
            
        cur = conn.cursor()
        cur.execute("INSERT INTO pastes (sender, title, content, style) VALUES (%s, %s, %s, %s)",
                    (session['user'], title, content, style))
        return redirect(url_for('index'))
    return render_template('add.html')

@app.route('/paste/<int:pid>')
@db_interaction
def view_paste(conn, pid):
    cur = conn.cursor()
    cur.execute("UPDATE pastes SET views = views + 1 WHERE id = %s", (pid,))
    cur.execute("SELECT * FROM pastes WHERE id = %s", (pid,))
    paste = cur.fetchone()
    if not paste:
        abort(404)
    return render_template('view.html', p=paste)

@app.route('/settings', methods=['GET', 'POST'])
@login_required
@db_interaction
def settings(conn):
    if request.method == 'POST':
        bg = request.form.get('bg', '')
        music = request.form.get('mu', '')
        cur = conn.cursor()
        cur.execute("UPDATE users SET bg_url=%s, music_url=%s WHERE username=%s", 
                    (bg, music, session['user']))
        session['bg'] = bg
        session['music'] = music
        flash("SYSTEM CONFIGURATION UPDATED")
        return redirect(url_for('settings'))
    return render_template('settings.html')

@app.errorhandler(404)
def page_not_found(e):
    return "<h1>404: DATA NOT FOUND</h1>", 404

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
