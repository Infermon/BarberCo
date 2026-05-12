"""
BarberCo — Backend FastAPI + SQLite
Sirve el index.html tal cual y expone una API REST en /api/
El index.html detecta si el backend está disponible y lo usa;
si no, cae de vuelta a localStorage (modo offline).
"""

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
import sqlite3, hashlib, os, json
from pathlib import Path

# ──────────────────────────────────────
# APP
# ──────────────────────────────────────
app = FastAPI(title="BarberCo API", version="1.0.0")

DB_PATH  = Path(__file__).parent / "barberico.db"
HTML_PATH = Path(__file__).parent / "index.html"

HORARIOS_BASE = [
    {"id": 1, "hora": "09:00"},
    {"id": 2, "hora": "10:00"},
    {"id": 3, "hora": "11:00"},
    {"id": 4, "hora": "12:00"},
    {"id": 5, "hora": "14:00"},
    {"id": 6, "hora": "15:00"},
    {"id": 7, "hora": "16:00"},
    {"id": 8, "hora": "17:00"},
    {"id": 9, "hora": "18:00"},
]

# ──────────────────────────────────────
# BASE DE DATOS
# ──────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre   TEXT NOT NULL,
            telefono TEXT NOT NULL,
            correo   TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            rol      TEXT NOT NULL DEFAULT 'cliente'
        );

        CREATE TABLE IF NOT EXISTS horarios (
            id         INTEGER PRIMARY KEY,
            hora       TEXT NOT NULL,
            disponible INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS citas (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            horario_id INTEGER NOT NULL,
            hora       TEXT NOT NULL,
            fecha      TEXT NOT NULL,
            servicio   TEXT NOT NULL,
            estado     TEXT NOT NULL DEFAULT 'confirmada',
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
            FOREIGN KEY (horario_id) REFERENCES horarios(id)
        );
    """)

    # Admin por defecto
    admin_pw = hashlib.sha256("admin123".encode()).hexdigest()
    cur.execute("""
        INSERT OR IGNORE INTO usuarios (id, nombre, telefono, correo, password, rol)
        VALUES (1, 'Administrador', '0000000000', 'admin@barberia.com', ?, 'admin')
    """, (admin_pw,))

    # Horarios base
    for h in HORARIOS_BASE:
        cur.execute("INSERT OR IGNORE INTO horarios (id, hora, disponible) VALUES (?,?,1)", (h["id"], h["hora"]))

    conn.commit()
    conn.close()

init_db()

# ──────────────────────────────────────
# HELPERS
# ──────────────────────────────────────
def hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

def row_to_dict(row):
    return dict(row) if row else None

# ──────────────────────────────────────
# SCHEMAS
# ──────────────────────────────────────
class RegistroBody(BaseModel):
    nombre: str
    telefono: str
    correo: str
    password: str

class LoginBody(BaseModel):
    correo: str
    password: str

class ReservaBody(BaseModel):
    usuario_id: int
    horario_id: int
    fecha: str
    servicio: str

class CancelarBody(BaseModel):
    cita_id: int
    usuario_id: int
    es_admin: bool = False

# ──────────────────────────────────────
# RUTAS API
# ──────────────────────────────────────

@app.get("/api/ping")
def ping():
    """El frontend llama esto para saber si el backend está vivo."""
    return {"ok": True}


# ── USUARIOS ──

@app.post("/api/registro")
def registro(body: RegistroBody):
    if len(body.password) < 6:
        raise HTTPException(400, "La contraseña debe tener al menos 6 caracteres.")

    conn = get_db()
    cur = conn.cursor()
    existing = cur.execute("SELECT id FROM usuarios WHERE correo = ?", (body.correo.lower(),)).fetchone()
    if existing:
        conn.close()
        raise HTTPException(409, "Este correo ya está registrado.")

    cur.execute(
        "INSERT INTO usuarios (nombre, telefono, correo, password, rol) VALUES (?,?,?,?,?)",
        (body.nombre, body.telefono, body.correo.lower(), hash_pw(body.password), "cliente")
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return {"ok": True, "id": new_id}


@app.post("/api/login")
def login(body: LoginBody):
    conn = get_db()
    user = conn.execute(
        "SELECT * FROM usuarios WHERE correo = ? AND password = ?",
        (body.correo.lower(), hash_pw(body.password))
    ).fetchone()
    conn.close()

    if not user:
        raise HTTPException(401, "Correo o contraseña incorrectos.")

    return {
        "ok": True,
        "usuario": {
            "id": user["id"],
            "nombre": user["nombre"],
            "rol": user["rol"]
        }
    }


# ── HORARIOS ──

@app.get("/api/horarios")
def get_horarios():
    conn = get_db()
    rows = conn.execute("SELECT * FROM horarios ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── CITAS ──

@app.get("/api/citas")
def get_citas(usuario_id: Optional[int] = None):
    conn = get_db()
    if usuario_id:
        rows = conn.execute(
            "SELECT * FROM citas WHERE usuario_id = ? ORDER BY id DESC", (usuario_id,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM citas ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/citas/admin")
def get_citas_admin():
    """Citas con nombre del cliente para el panel admin."""
    conn = get_db()
    rows = conn.execute("""
        SELECT c.*, u.nombre AS nombre_cliente, u.telefono AS telefono_cliente
        FROM citas c
        JOIN usuarios u ON u.id = c.usuario_id
        ORDER BY c.id DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/api/citas")
def crear_cita(body: ReservaBody):
    conn = get_db()
    cur = conn.cursor()

    horario = cur.execute("SELECT * FROM horarios WHERE id = ?", (body.horario_id,)).fetchone()
    if not horario or not horario["disponible"]:
        conn.close()
        raise HTTPException(409, "Ese horario ya no está disponible.")

    cur.execute(
        "INSERT INTO citas (usuario_id, horario_id, hora, fecha, servicio, estado) VALUES (?,?,?,?,?,?)",
        (body.usuario_id, body.horario_id, horario["hora"], body.fecha, body.servicio, "confirmada")
    )
    cur.execute("UPDATE horarios SET disponible = 0 WHERE id = ?", (body.horario_id,))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return {"ok": True, "id": new_id}


@app.patch("/api/citas/{cita_id}/cancelar")
def cancelar_cita(cita_id: int, body: CancelarBody):
    conn = get_db()
    cur = conn.cursor()

    cita = cur.execute("SELECT * FROM citas WHERE id = ?", (cita_id,)).fetchone()
    if not cita:
        conn.close()
        raise HTTPException(404, "Cita no encontrada.")

    if not body.es_admin and cita["usuario_id"] != body.usuario_id:
        conn.close()
        raise HTTPException(403, "No tienes permiso para cancelar esta cita.")

    cur.execute("UPDATE citas SET estado = 'cancelada' WHERE id = ?", (cita_id,))
    cur.execute("UPDATE horarios SET disponible = 1 WHERE id = ?", (cita["horario_id"],))
    conn.commit()
    conn.close()
    return {"ok": True}


# ── CLIENTES (admin) ──

@app.get("/api/clientes")
def get_clientes():
    conn = get_db()
    rows = conn.execute("SELECT id, nombre, telefono, correo, rol FROM usuarios WHERE rol = 'cliente'").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── STATS (admin) ──

@app.get("/api/stats")
def get_stats():
    conn = get_db()
    total      = conn.execute("SELECT COUNT(*) FROM citas").fetchone()[0]
    confirmadas = conn.execute("SELECT COUNT(*) FROM citas WHERE estado='confirmada'").fetchone()[0]
    canceladas  = conn.execute("SELECT COUNT(*) FROM citas WHERE estado='cancelada'").fetchone()[0]
    clientes    = conn.execute("SELECT COUNT(*) FROM usuarios WHERE rol='cliente'").fetchone()[0]
    conn.close()
    return {
        "total": total,
        "confirmadas": confirmadas,
        "canceladas": canceladas,
        "clientes": clientes
    }


# ──────────────────────────────────────
# SERVIR EL INDEX.HTML SIN TOCARLO
# ──────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
def serve_index():
    return HTML_PATH.read_text(encoding="utf-8")


# ──────────────────────────────────────
# ARRANCAR
# ──────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
