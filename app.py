# app.py - VERSION CON BUG (rama main)
import logging
import sqlite3
import time
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log_auth = logging.getLogger("AuthService")
log_ctrl = logging.getLogger("AuthController")
log_db = logging.getLogger("DBConnection")

DB = "users.db"
DB_TIMEOUT = 5
failed_attempts = {}


def init_db():
    conn = sqlite3.connect(DB)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS users ("
        "id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT)"
    )
    conn.execute(
        "INSERT OR IGNORE INTO users (username, password) VALUES (?, ?)",
        ("jgarcia", "Clave123*"),
    )
    conn.commit()
    conn.close()


# FIX: consulta directa por igualdad exacta -> usa el indice UNIQUE de username.
def query_user(username):
    conn = sqlite3.connect(DB, timeout=DB_TIMEOUT)
    try:
        return conn.execute(
            "SELECT username, password FROM users WHERE username = ?",
            (username,),
        ).fetchone()
    finally:
        conn.close()


PAGE = """
<!doctype html><meta charset="utf-8">
<title>Plataforma Institucional</title>
<div style="font-family:sans-serif;max-width:360px;margin:60px auto">
  <h2>Iniciar sesion</h2>
  <input id="u" placeholder="Usuario" style="width:100%;padding:8px;margin:4px 0"><br>
  <input id="p" type="password" placeholder="Contrasena" style="width:100%;padding:8px;margin:4px 0"><br>
  <button onclick="login()" style="padding:8px 16px;margin-top:8px">Entrar</button>
  <p id="msg" style="font-weight:bold"></p>
  <script>
    async function login() {
      const msg = document.getElementById('msg');
      msg.style.color = '#555';
      msg.textContent = 'Verificando...';
      const t0 = Date.now();
      const r = await fetch('/login', {
        method: 'POST',
        headers: {'Content-Type': 'application/x-www-form-urlencoded'},
        body: 'username=' + encodeURIComponent(u.value) + '&password=' + encodeURIComponent(p.value)
      });
      const secs = ((Date.now() - t0) / 1000).toFixed(1);
      let data = {};
      try { data = await r.json(); } catch (e) {}
      msg.style.color = r.ok ? 'green' : 'red';
      msg.textContent = (data.message || data.error || 'Internal Server Error') + ' (' + secs + 's)';
    }
  </script>
</div>
"""


@app.route("/")
def index():
    return render_template_string(PAGE)


@app.route("/login", methods=["POST"])
def login():
    username = request.form.get("username", "")
    password = request.form.get("password", "")
    start = time.time()
    try:
        row = query_user(username)
        elapsed = time.time() - start
        if elapsed > DB_TIMEOUT:
            log_db.error('Timeout while querying table "users"')
            raise TimeoutError()
        if row and row[1] == password:
            failed_attempts.pop(username, None)
            return jsonify(ok=True, message=f"Bienvenido, {username}")
        raise ValueError()
    except (TimeoutError, ValueError):
        log_auth.error("Error validating user token")
        log_ctrl.warning(f"Login attempt failed for user: {username}")
        failed_attempts[username] = failed_attempts.get(username, 0) + 1
        if failed_attempts[username] >= 3:
            return jsonify(error="Internal Server Error"), 500
        return (
            jsonify(error="Error: credenciales no validas. Intentelo nuevamente."),
            401,
        )


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)