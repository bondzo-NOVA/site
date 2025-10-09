from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import sqlite3
import jwt
import datetime
import bleach
from functools import wraps

app = Flask(__name__)
app.secret_key = 'your-secret-key'
DATABASE = 'bluecat.db'
JWT_SECRET = 'your-jwt-secret'

def init_db():
    with sqlite3.connect(DATABASE) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users 
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                     name TEXT NOT NULL, 
                     email TEXT UNIQUE NOT NULL, 
                     password TEXT NOT NULL)''')
        c.execute('''CREATE TABLE IF NOT EXISTS scripts 
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                     title TEXT NOT NULL, 
                     content TEXT NOT NULL, 
                     tags TEXT, 
                     author_id INTEGER, 
                     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                     FOREIGN KEY(author_id) REFERENCES users(id))''')
        conn.commit()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def get_current_user():
    token = session.get('token')
    if token:
        try:
            return jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
        except:
            return None
    return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    name = bleach.clean(data.get('name', ''))
    email = bleach.clean(data.get('email', ''))
    password = data.get('password', '')
    
    if not all([name, email, password]):
        return jsonify({'success': False, 'message': 'All fields required'}), 400
        
    with sqlite3.connect(DATABASE) as conn:
        c = conn.cursor()
        try:
            c.execute('INSERT INTO users (name, email, password) VALUES (?, ?, ?)',
                     (name, email, password))
            conn.commit()
            user_id = c.lastrowid
            token = jwt.encode({
                'user_id': user_id,
                'name': name,
                'email': email,
                'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
            }, JWT_SECRET)
            return jsonify({
                'success': True,
                'user': {'id': user_id, 'name': name, 'email': email},
                'token': token
            })
        except sqlite3.IntegrityError:
            return jsonify({'success': False, 'message': 'Email already exists'}), 400

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    email = bleach.clean(data.get('email', ''))
    password = data.get('password', '')
    
    with sqlite3.connect(DATABASE) as conn:
        c = conn.cursor()
        c.execute('SELECT id, name, email FROM users WHERE email = ? AND password = ?',
                 (email, password))
        user = c.fetchone()
        if user:
            user_id, name, email = user
            token = jwt.encode({
                'user_id': user_id,
                'name': name,
                'email': email,
                'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
            }, JWT_SECRET)
            session['token'] = token
            session['user_id'] = user_id
            return jsonify({
                'success': True,
                'user': {'id': user_id, 'name': name, 'email': email},
                'token': token
            })
        return jsonify({'success': False, 'message': 'Invalid credentials'}), 401

@app.route('/api/scripts', methods=['GET'])
def get_scripts():
    with sqlite3.connect(DATABASE) as conn:
        c = conn.cursor()
        c.execute('''SELECT s.id, s.title, s.content, s.tags, s.created_at, 
                           u.id as author_id, u.name as author_name
                    FROM scripts s JOIN users u ON s.author_id = u.id
                    ORDER BY s.created_at DESC''')
        scripts = []
        for row in c.fetchall():
            scripts.append({
                'id': row[0],
                'title': row[1],
                'content': row[2],
                'tags': row[3].split(',') if row[3] else [],
                'created_at': row[4],
                'author': {'id': row[5], 'name': row[6], 'is_me': row[5] == session.get('user_id')}
            })
        return jsonify({'success': True, 'scripts': scripts})

@app.route('/api/scripts', methods=['POST'])
@login_required
def post_script():
    data = request.get_json()
    title = bleach.clean(data.get('title', ''))
    content = bleach.clean(data.get('content', ''))
    tags = ','.join([bleach.clean(t) for t in data.get('tags', [])])
    
    if not title or not content:
        return jsonify({'success': False, 'message': 'Title and content required'}), 400
        
    user = get_current_user()
    with sqlite3.connect(DATABASE) as conn:
        c = conn.cursor()
        c.execute('INSERT INTO scripts (title, content, tags, author_id) VALUES (?, ?, ?, ?)',
                 (title, content, tags, user['user_id']))
        conn.commit()
        script_id = c.lastrowid
        return jsonify({
            'success': True,
            'script': {
                'id': script_id,
                'title': title,
                'content': content,
                'tags': tags.split(',') if tags else [],
                'author': {'id': user['user_id'], 'name': user['name']}
            }
        })

@app.route('/api/my-scripts')
@login_required
def my_scripts():
    user = get_current_user()
    with sqlite3.connect(DATABASE) as conn:
        c = conn.cursor()
        c.execute('''SELECT id, title, content, tags, created_at 
                    FROM scripts WHERE author_id = ? 
                    ORDER BY created_at DESC''', 
                 (user['user_id'],))
        scripts = []
        for row in c.fetchall():
            scripts.append({
                'id': row[0],
                'title': row[1],
                'content': row[2],
                'tags': row[3].split(',') if row[3] else [],
                'created_at': row[4],
                'author': {'id': user['user_id'], 'name': user['name'], 'is_me': True}
            })
        return jsonify({'success': True, 'scripts': scripts})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/static/style.css')
def serve_css():
    return """
:root {
    --bg: #eaf7ff;
    --card: #fff;
    --accent: #79c9ff;
    --accent-2: #3399ff;
    --text: #0b2633;
    --muted: #6b7c86;
    --border: #e3f6ff;
    --mono: ui-monospace, Menlo, Monaco, "Roboto Mono", "Courier New", monospace;
}

[data-theme="dark"] {
    --bg: #071018;
    --card: #0f1720;
    --accent: #1e90ff;
    --accent-2: #0077ff;
    --text: #e6f6ff;
    --muted: #7f98a9;
    --border: #14232e;
}

* { box-sizing: border-box; }
body { margin: 0; font-family: Inter, system-ui, Arial; color: var(--text); background: var(--bg); transition: background .25s, color .25s; }
header { background: linear-gradient(90deg, var(--accent), var(--accent-2)); color: #fff; padding: 14px 18px; display: flex; justify-content: space-between; align-items: center; }
.logo { width: 44px; height: 44px; border-radius: 8px; background: linear-gradient(180deg, var(--accent-2), var(--accent)); display: flex; align-items: center; justify-content: center; font-weight: 700; color: white; }
nav { display: flex; gap: 10px; align-items: center; }
nav a { color: rgba(255,255,255,.95); text-decoration: none; padding: 8px 10px; border-radius: 8px; font-weight: 700; }
nav a.active { background: rgba(255,255,255,.12); }
.container { max-width: 980px; margin: 26px auto; padding: 0 18px; }
.card { background: var(--card); padding: 16px; border-radius: 12px; border: 1px solid var(--border); box-shadow: 0 6px 18px rgba(0,0,0,0.04); }
.grid { display: grid; grid-template-columns: 1fr 340px; gap: 16px; }
@media (max-width: 920px) { .grid { grid-template-columns: 1fr; } }
input, textarea, select { width: 100%; padding: 10px; border-radius: 8px; border: 1px solid var(--border); background: transparent; color: var(--text); }
button { cursor: pointer; }
.big-btn { background: linear-gradient(180deg, var(--accent-2), var(--accent)); color: white; border: none; padding: 10px 12px; border-radius: 8px; font-weight: 700; }
.small { font-size: 13px; color: var(--muted); }
.post-meta { display: flex; justify-content: space-between; gap: 8px; align-items: center; }
.post { border-radius: 8px; padding: 12px; border: 1px solid var(--border); background: rgba(0,0,0,0.01); margin-bottom: 12px; }
pre { white-space: pre-wrap; font-family: var(--mono); background: rgba(0,0,0,0.03); padding: 10px; border-radius: 8px; overflow: auto; }
.hidden { display: none; }
footer { text-align: center; color: var(--muted); margin: 18px 0; font-size: 13px; }
.notice { padding: 8px; border-radius: 8px; background: #fffae6; border: 1px solid #fff0b3; color: #665100; }
"""

@app.route('/static/icon.svg')
def serve_icon():
    return """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><circle cx="50" cy="50" r="45" fill="#0a74da"/><text x="50" y="58" font-size="48" text-anchor="middle" fill="white" font-family="Arial">฿</text></svg>"""

if __name__ == '__main__':
    init_db()
    app.run(debug=True)

<xaiArtifact artifact_id="3472400a-099c-4072-b714-c993269308c2" artifact_version_id="5bbbf53b-d71f-4072-abbc-6d3163cb21da" title="templates/index.html" contentType="text/html">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Blue Cat — Post Scripts (Login Required)</title>
<link rel="icon" href="/static/icon.svg">
<link rel="stylesheet" href="/static/style.css">
<body>
<header>
    <div style="display:flex;gap:12px;align-items:center">
        <div class="logo">฿</div>
        <div>
            <div style="font-weight:800">Blue Cat</div>
            <div class="small">Post your Roblox scripts — login required to post</div>
        </div>
    </div>
    <nav>
        <a href="#" class="nav-link active" data-target="feed">Feed</a>
        <a href="#" class="nav-link" data-target="greet">Post (Greet)</a>
        <a href="#" class="nav-link" data-target="info">Info</a>
        <a href="#" class="nav-link" data-target="settings">Settings</a>
        {% if session.get('user_id') %}
            <a href="/logout" class="nav-link">Logout</a>
        {% else %}
            <a href="#" class="nav-link" data-target="login">Login</a>
        {% endif %}
        <a href="https://discord.gg/YOUR_DISCORD_INVITE" target="_blank" style="background:#5865f2;padding:8px 10px;border-radius:8px;color:white;text-decoration:none">Discord</a>
    </nav>
</header>
<main class="container">
    <div class="grid">
        <section id="feed" class="card">
            <h2 style="margin:0 0 10px 0">Scripts Feed</h2>
            <div id="feedList">
                <div class="small">Loading...</div>
            </div>
        </section>
        <aside class="card">
            <h3 style="margin:0 0 8px 0">Your status</h3>
            <div id="userPanel" class="small">
                {% if session.get('user_id') %}
                    Logged in — ready to post.
                {% else %}
                    Not logged in
                {% endif %}
            </div>
            <div style="height:12px"></div>
            <div class="notice small">Only logged-in users can post scripts. Your Cloudflare backend should verify tokens and store scripts in a DB (D1 / KV / or external DB).</div>
            <div style="height:10px"></div>
            <div>
                <strong>Quick links</strong>
                <div style="height:8px"></div>
                <a href="#" id="myScriptsLink" class="small">My Scripts</a>
            </div>
        </aside>
    </div>
    <section id="greet" class="card hidden" style="margin-top:16px">
        <h2>Post your script</h2>
        <div id="greetMsg" class="small {% if session.get('user_id') %}hidden{% endif %}">
            You must be logged in to post. <a href="#" id="gotoLogin">Login here</a>.
        </div>
        <form id="postForm" class="{% if not session.get('user_id') %}hidden{% endif %}" style="margin-top:12px">
            <label>Title</label>
            <input id="postTitle" required placeholder="Short title (e.g. Fast Spawn)">
            <label>Tags (comma separated)</label>
            <input id="postTags" placeholder="funny, utility">
            <label>Script content (.lua)</label>
            <textarea id="postContent" rows="10" placeholder="Paste your script here..." required></textarea>
            <div style="height:10px"></div>
            <div style="display:flex;gap:8px">
                <button type="submit" class="big-btn">Post Script</button>
                <button type="button" id="previewBtn">Preview</button>
            </div>
        </form>
        <div id="postPreview" class="hidden" style="margin-top:12px">
            <h4>Preview</h4>
            <pre id="postPreviewBox"></pre>
        </div>
    </section>
    <section id="login" class="card hidden" style="margin-top:16px">
        <h2>Login</h2>
        <form id="loginForm">
            <label>Email</label>
            <input id="loginEmail" type="email" required>
            <label>Password</label>
            <input id="loginPassword" type="password" required>
            <div style="height:8px"></div>
            <div style="display:flex;gap:8px">
                <button class="big-btn" type="submit">Login</button>
                <button type="button" id="gotoRegister" style="padding:10px 12px;border-radius:8px">Register</button>
            </div>
        </form>
        <div id="loginMsg" class="small" style="margin-top:8px"></div>
    </section>
    <section id="register" class="card hidden" style="margin-top:16px">
        <h2>Create account</h2>
        <form id="registerForm">
            <label>Display name</label>
            <input id="regName" required>
            <label>Email</label>
            <input id="regEmail" type="email" required>
            <label>Password</label>
            <input id="regPassword" type="password" required>
            <div style="height:8px"></div>
            <button class="big-btn" type="submit">Create account</button>
        </form>
        <div id="regMsg" class="small" style="margin-top:8px"></div>
    </section>
    <section id="info" class="card hidden" style="margin-top:16px">
        <h2>Info & Backend notes</h2>
        <p class="small">Hook these endpoints to your Cloudflare Worker / backend. The frontend expects JSON responses and a token (JWT or similar) on login/register.</p>
        <h4>Suggested API routes (replace with your Cloudflare endpoints)</h4>
        <pre class="small">
POST /api/register
  body: { name, email, password }
  returns: { success:true, user:{id,name,email}, token:"JWT-TOKEN" }

POST /api/login
  body: { email, password }
  returns: { success:true, user:{id,name,email}, token:"JWT-TOKEN" }

GET /api/scripts
  returns: { success:true, scripts:[ { id, title, content, tags, author:{id,name}, created_at } ] }

POST /api/scripts
  headers: Authorization: Bearer JWT-TOKEN
  body: { title, content, tags:[...] }
  returns: { success:true, script:{...} }
        </pre>
        <h4 class="small">Cloudflare tips</h4>
        <ul class="small">
            <li>Use <strong>D1</strong> (SQLite) for relational storage of scripts & users, or Workers KV for simple key-value.</li>
            <li>Store session tokens as secure, HttpOnly cookies when possible (safer than localStorage).</li>
            <li>Sanitize content server-side and rate-limit posts to prevent abuse.</li>
        </ul>
    </section>
    <section id="settings" class="card hidden" style="margin-top:16px">
        <h2>Appearance</h2>
        <div style="display:flex;gap:12px;align-items:center">
            <label><input type="radio" name="themeMode" value="auto" checked> Auto (system)</label>
            <label><input type="radio" name="themeMode" value="light"> Light</label>
            <label><input type="radio" name="themeMode" value="dark"> Dark</label>
        </div>
    </section>
</main>
<footer>© Blue Cat — Build & connect your Cloudflare backend to store scripts securely.</footer>
<script>
const API_BASE = '/api';
const API_LOGIN = API_BASE + '/login';
const API_REGISTER = API_BASE + '/register';
const API_SCRIPTS = API_BASE + '/scripts';

function saveToken(token) { localStorage.setItem('bc_token', token); }
function readToken() { return localStorage.getItem('bc_token'); }
function clearToken() { localStorage.removeItem('bc_token'); }
function isAuthenticated() { return !!readToken(); }

const navLinks = document.querySelectorAll('.nav-link');
navLinks.forEach(a => {
    a.addEventListener('click', (e) => {
        e.preventDefault();
        const target = a.dataset.target;
        navLinks.forEach(x => x.classList.toggle('active', x === a));
        document.querySelectorAll('main section').forEach(s => s.classList.add('hidden'));
        document.getElementById(target).classList.remove('hidden');
        window.scrollTo({ top: 0, behavior: 'smooth' });
    });
});

function updateAuthUI() {
    const authBtn = document.getElementById('authBtn');
    const userPanel = document.getElementById('userPanel');
    if (isAuthenticated()) {
        authBtn.textContent = 'Logout';
        authBtn.onclick = (e) => { e.preventDefault(); logout(); }
        userPanel.textContent = 'Logged in — ready to post.';
    } else {
        authBtn.textContent = 'Login';
        authBtn.onclick = (e) => { e.preventDefault(); document.querySelector('a.nav-link[data-target="login"]').click(); }
        userPanel.textContent = 'Not logged in';
    }
}

async function apiFetch(url, opts = {}) {
    opts.headers = opts.headers || {};
    const token = readToken();
    if (token) opts.headers['Authorization'] = 'Bearer ' + token;
    opts.headers['Content-Type'] = opts.headers['Content-Type'] || 'application/json';
    const res = await fetch(url, opts);
    let data;
    try { data = await res.json(); } catch (e) { data = { success: false, status: res.status }; }
    if (!res.ok) { throw data; }
    return data;
}

const feedList = document.getElementById('feedList');
async function loadFeed() {
    feedList.innerHTML = '<div class="small">Loading...</div>';
    try {
        const data = await apiFetch(API_SCRIPTS, { method: 'GET' });
        const scripts = data.scripts || [];
        if (scripts.length === 0) {
            feedList.innerHTML = '<div class="small">No scripts yet. Be the first to post!</div>';
            return;
        }
        const html = scripts.map(s => {
            const tags = (s.tags || []).map(t => `<span class="small" style="opacity:.8">#${escapeHtml(t)}</span>`).join(' ');
            const author = s.author && s.author.name ? escapeHtml(s.author.name) : 'anonymous';
            const when = new Date(s.created_at || Date.now()).toLocaleString();
            return `<div class="post">
                <div style="display:flex;justify-content:space-between;align-items:center">
                    <strong>${escapeHtml(s.title || 'Untitled')}</strong>
                    <div class="small">${when}</div>
                </div>
                <div class="small" style="margin:6px 0">by ${author} ${tags}</div>
                <pre>${escapeHtml(s.content || '')}</pre>
            </div>`;
        }).join('');
        feedList.innerHTML = html;
    } catch (err) {
        console.error(err);
        feedList.innerHTML = '<div class="small">Failed to load feed (check API). See console.</div>';
    }
}

const postForm = document.getElementById('postForm');
const greetMsg = document.getElementById('greetMsg');
const postPreview = document.getElementById('postPreview');
const postPreviewBox = document.getElementById('postPreviewBox');

document.getElementById('gotoLogin').addEventListener('click', e => {
    e.preventDefault();
    document.querySelector('a.nav-link[data-target="login"]').click();
});

function showPostFormIfAuthed() {
    if (isAuthenticated()) {
        postForm.classList.remove('hidden');
        greetMsg.classList.add('hidden');
    } else {
        postForm.classList.add('hidden');
        greetMsg.classList.remove('hidden');
    }
}

postForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const title = document.getElementById('postTitle').value.trim();
    const tags = (document.getElementById('postTags').value || '').split(',').map(s => s.trim()).filter(Boolean);
    const content = document.getElementById('postContent').value;
    if (!title || !content) { alert('Please provide title and content'); return; }
    try {
        const payload = { title, content, tags };
        const res = await apiFetch(API_SCRIPTS, { method: 'POST', body: JSON.stringify(payload) });
        alert('Posted!');
        loadFeed();
        postForm.reset();
        postPreview.classList.add('hidden');
        document.querySelector('a.nav-link[data-target="feed"]').click();
    } catch (err) {
        console.error(err);
        if (err && err.message) alert('Post failed: ' + err.message);
        else alert('Post failed (see console)');
    }
});

document.getElementById('previewBtn').addEventListener('click', () => {
    const content = document.getElementById('postContent').value;
    postPreviewBox.textContent = content;
    postPreview.classList.remove('hidden');
});

const loginForm = document.getElementById('loginForm');
const registerForm = document.getElementById('registerForm');

loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const email = document.getElementById('loginEmail').value.trim();
    const password = document.getElementById('loginPassword').value;
    try {
        const res = await fetch(API_LOGIN, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });
        const data = await res.json();
        if (!res.ok) throw data;
        if (data.token) {
            saveToken(data.token);
            updateAuthUI();
            loadFeed();
            showPostFormIfAuthed();
            alert('Login successful');
            document.querySelector('a.nav-link[data-target="feed"]').click();
        } else {
            alert('Login succeeded but no token returned. Check backend.');
        }
    } catch (err) {
        console.error(err);
        document.getElementById('loginMsg').textContent = err && err.message ? err.message : 'Login failed';
    }
});

registerForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const name = document.getElementById('regName').value.trim();
    const email = document.getElementById('regEmail').value.trim();
    const password = document.getElementById('regPassword').value;
    try {
        const res = await fetch(API_REGISTER, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, email, password })
        });
        const data = await res.json();
        if (!res.ok) throw data;
        if (data.token) {
            saveToken(data.token);
            updateAuthUI();
            loadFeed();
            showPostFormIfAuthed();
            alert('Account created & logged in');
            document.querySelector('a.nav-link[data-target="feed"]').click();
        } else {
            document.getElementById('regMsg').textContent = 'Registered but no token returned.';
        }
    } catch (err) {
        console.error(err);
        document.getElementById('regMsg').textContent = err && err.message ? err.message : 'Registration failed';
    }
});

document.getElementById('gotoRegister').addEventListener('click', (e) => {
    e.preventDefault();
    document.querySelector('a.nav-link[data-target="register"]').click();
});

function logout() {
    clearToken();
    updateAuthUI();
    showPostFormIfAuthed();
    alert('Logged out');
    loadFeed();
}

const root = document.documentElement;
function applyTheme(mode) {
    if (mode === 'auto') {
        const dark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        root.setAttribute('data-theme', dark ? 'dark' : 'light');
    } else {
        root.setAttribute('data-theme', mode);
    }
    localStorage.setItem('bc_theme', mode);
}

document.querySelectorAll('[name="themeMode"]').forEach(r => {
    r.addEventListener('change', () => applyTheme(document.querySelector('[name="themeMode"]:checked').value));
});

const savedTheme = localStorage.getItem('bc_theme') || 'auto';
document.querySelectorAll('[name="themeMode"]').forEach(r => { r.checked = (r.value === savedTheme); });
applyTheme(savedTheme);
window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    if ((localStorage.getItem('bc_theme') || 'auto') === 'auto') applyTheme('auto');
});

function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/[&<>"']/g, s => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[s]);
}

updateAuthUI();
showPostFormIfAuthed();
loadFeed();

document.getElementById('myScriptsLink').addEventListener('click', async (e) => {
    e.preventDefault();
    if (!isAuthenticated()) { 
        alert('Login first'); 
        document.querySelector('a.nav-link[data-target="login"]').click(); 
        return; 
    }
    try {
        const data = await apiFetch('/api/my-scripts', { method: 'GET' });
        const my = data.scripts || [];
        if (my.length === 0) { 
            alert('No scripts found for your account'); 
            return; 
        }
        feedList.innerHTML = my.map(s => `<div class="post"><strong>${escapeHtml(s.title)}</strong><div class="small">by ${escapeHtml(s.author.name)}</div><pre>${escapeHtml(s.content)}</pre></div>`).join('');
        document.querySelector('a.nav-link[data-target="feed"]').click();
    } catch (err) { 
        console.error(err); 
        alert('Failed to fetch your scripts'); 
    }
});
</script>
</body>
