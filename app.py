Python 3.13.14 (tags/v3.13.14:fd17997, Jun 10 2026, 13:03:48) [MSC v.1944 64 bit (AMD64)] on win32
Enter "help" below or click "Help" above for more information.
# app.py — VERSIÓN CON BUG (rama main)
# Incidencia simulada: error de autenticación tras actualización del módulo auth.
# Reproduce: login de 6-8s, "credenciales no válidas" con credenciales correctas,
# error 500 tras varios intentos, timeout en tabla "users".

import logging
import sqlite3
import time
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

# ---------- Logging (mismo formato de los logs del servidor) ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log_auth = logging.getLogger("AuthService")
log_ctrl = logging.getLogger("AuthController")
log_db = logging.getLogger("DBConnection")

DB = "users.db"
DB_TIMEOUT = 5  # segundos máximos permitidos para la consulta
failed_attempts = {}  # contador de intentos fallidos por usuario


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


# ---------------------------------------------------------------------
# BUG: este método fue modificado en la actualización del módulo de
# autenticación (hace 24 horas). Se agregó una "verificación extendida"
# que recorre la tabla users SIN usar el índice (LOWER() sobre la
# columna anula el índice único) y agrega latencia de red/BD.
# Resultado: cada login tarda 6-8 segundos y supera el DB_TIMEOUT.
# ---------------------------------------------------------------------
def query_user_extended(username):
    time.sleep(6.5)  # simula el full scan + latencia introducidos en la actualización
    conn = sqlite3.connect(DB)
    row = conn.execute(
        "SELECT username, password FROM users WHERE LOWER(username) = LOWER(?)",
        (username,),
    ).fetchone()
    conn.close()
    return row


PAGE = """
<!doctype html><meta charset="utf-8">
<title>Plataforma Institucional</title>
<div style="font-family:sans-serif;max-width:360px;margin:60px auto">
  <h2>Iniciar sesión</h2>
  <form method="post" action="/login">
    <input name="username" placeholder="Usuario" style="width:100%;padding:8px;margin:4px 0"><br>
    <input name="password" type="password" placeholder="Contraseña" style="width:100%;padding:8px;margin:4px 0"><br>
    <button style="padding:8px 16px;margin-top:8px">Entrar</button>
  </form>
</div>
"""

... 
... @app.route("/")
... def index():
...     return render_template_string(PAGE)
... 
... 
... @app.route("/login", methods=["POST"])
... def login():
...     username = request.form.get("username", "")
...     password = request.form.get("password", "")
...     start = time.time()
...     try:
...         row = query_user_extended(username)
...         elapsed = time.time() - start
...         if elapsed > DB_TIMEOUT:
...             log_db.error('Timeout while querying table "users"')
...             raise TimeoutError()
...         if row and row[1] == password:
...             failed_attempts.pop(username, None)
...             return jsonify(ok=True, message=f"Bienvenido, {username}")
...         raise ValueError()
...     except (TimeoutError, ValueError):
...         log_auth.error("Error validating user token")
...         log_ctrl.warning(f"Login attempt failed for user: {username}")
...         failed_attempts[username] = failed_attempts.get(username, 0) + 1
...         if failed_attempts[username] >= 3:
...             # BUG adicional: los reintentos acumulados terminan en un 500
...             return jsonify(error="Internal Server Error"), 500
...         # BUG: el timeout de BD se reporta al usuario como credenciales inválidas
...         return (
...             jsonify(error="Error: credenciales no válidas. Inténtelo nuevamente."),
...             401,
...         )
... 
... 
... if __name__ == "__main__":
...     init_db()
