import pkgutil as _pkgutil
import importlib.util as _importlib_util

# Compatibility shim: Python versions newer may not have pkgutil.get_loader
if not hasattr(_pkgutil, 'get_loader'):
    def _get_loader(name):
        # defensive: some runtimes pass '__main__' or relative names; handle safely
        try:
            if not name or name == '__main__':
                return None
            spec = _importlib_util.find_spec(name)
            return spec.loader if spec is not None else None
        except Exception:
            return None
    _pkgutil.get_loader = _get_loader

from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from analysis import recommend, detect_manipulation
import os
import json
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get('SISTEMABACBO_SECRET', 'troque-esta-chave-para-producao')

DB_FILE = 'sistemabacbo.db'

def get_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    db = get_db()
    cur = db.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            timestamp TEXT,
            sequence TEXT,
            result_json TEXT
        )
    ''')
    db.commit()

init_db()

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        cur = db.cursor()
        try:
            cur.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, generate_password_hash(password)))
            db.commit()
            flash('Cadastro realizado, faça login', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Usuário já existe', 'danger')
            return redirect(url_for('register'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        cur = db.cursor()
        cur.execute('SELECT id, username, password FROM users WHERE username = ?', (username,))
        row = cur.fetchone()
        if row and check_password_hash(row['password'], password):
            session['user_id'] = row['id']
            session['username'] = row['username']
            return redirect(url_for('dashboard'))
        flash('Credenciais inválidas', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    result = None
    analysis = None
    if request.method == 'POST':
        seq_text = request.form.get('sequence','')
        seq = [s.strip().upper() for s in seq_text.replace(',', ' ').split() if s.strip()]
        analysis = detect_manipulation(seq)
        result = recommend(seq, lookback=30)
        # persist histórico
        try:
            db = get_db()
            cur = db.cursor()
            cur.execute('INSERT INTO history (user_id, timestamp, sequence, result_json) VALUES (?, ?, ?, ?)', (
                session.get('user_id'), datetime.utcnow().isoformat(), ' '.join(seq), json.dumps(result, ensure_ascii=False)
            ))
            db.commit()
        except Exception:
            pass
    return render_template('dashboard.html', result=result, analysis=analysis)


@app.route('/history')
def history():
    db = get_db()
    cur = db.cursor()
    cur.execute('SELECT timestamp, sequence, result_json FROM history ORDER BY id DESC LIMIT 20')
    rows = []
    for r in cur.fetchall():
        try:
            result = json.loads(r['result_json'])
        except Exception:
            result = {}
        rows.append({'timestamp': r['timestamp'], 'sequence': r['sequence'], 'result': result})
    return app.response_class(response=json.dumps(rows, ensure_ascii=False), mimetype='application/json')


@app.route('/export_history')
def export_history():
    db = get_db()
    cur = db.cursor()
    cur.execute('SELECT timestamp, sequence, result_json FROM history ORDER BY id DESC LIMIT 100')
    import csv
    from io import StringIO
    si = StringIO()
    writer = csv.writer(si)
    writer.writerow(['timestamp', 'sequence', 'recommendation_aggressive', 'confidence_aggressive', 'recommendation_conservative', 'confidence_conservative', 'notes'])
    for r in cur.fetchall():
        try:
            res = json.loads(r['result_json'])
            m = res.get('modes', {})
            a = m.get('aggressive', {})
            c = m.get('conservative', {})
            notes = '; '.join(res.get('notes', [])) if res.get('notes') else ''
        except Exception:
            a = c = {}
            notes = ''
        writer.writerow([r['timestamp'], r['sequence'], a.get('recommendation',''), a.get('confidence',''), c.get('recommendation',''), c.get('confidence',''), notes])
    output = si.getvalue()
    return app.response_class(output, mimetype='text/csv', headers={'Content-Disposition':'attachment; filename=history.csv'})

if __name__ == '__main__':
    app.run(debug=True)
