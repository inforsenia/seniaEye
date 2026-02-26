"""
database.py — Capa de persistencia SQLite para SèniaEye.

Esquema:
  sessions  →  una fila por conexión de agente (desde connect hasta disconnect)
  events    →  todos los eventos recibidos, vinculados a una sesión
"""

import sqlite3
import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent / "seniaeye.db"

# SQLite no es thread-safe con la misma conexión; usamos un lock global
# y abrimos/cerramos conexiones por operación (check_same_thread=False
# es suficiente para nuestro uso secuencial desde asyncio en un solo hilo).
_lock = threading.Lock()


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")   # mejor concurrencia lectura/escritura
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ── Inicialización ─────────────────────────────────────────────────────────────

def init_db() -> None:
    """Crea las tablas si no existen. Llamar al arrancar el servidor."""
    with _lock:
        conn = _connect()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id    TEXT    NOT NULL,
                    started_at  TEXT    NOT NULL,
                    ended_at    TEXT,
                    duration_s  INTEGER,
                    event_count INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS events (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id  INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    agent_id    TEXT    NOT NULL,
                    event_type  TEXT    NOT NULL,
                    timestamp   TEXT    NOT NULL,
                    data        TEXT                 -- JSON serializado
                );

                CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id);
                CREATE INDEX IF NOT EXISTS idx_sessions_agent ON sessions(agent_id);
            """)
            conn.commit()
        finally:
            conn.close()


# ── Sesiones ───────────────────────────────────────────────────────────────────

def open_session(agent_id: str) -> int:
    """Abre una nueva sesión para el agente. Devuelve el session_id."""
    with _lock:
        conn = _connect()
        try:
            cur = conn.execute(
                "INSERT INTO sessions (agent_id, started_at) VALUES (?, ?)",
                (agent_id, _now())
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()


def close_session(session_id: int) -> None:
    """Cierra la sesión: guarda ended_at, duración y cuenta de eventos."""
    with _lock:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT started_at FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
            if not row:
                return
            ended_at = _now()
            started  = datetime.strptime(row["started_at"], "%Y-%m-%d %H:%M:%S")
            ended    = datetime.strptime(ended_at,          "%Y-%m-%d %H:%M:%S")
            duration = int((ended - started).total_seconds())

            count = conn.execute(
                "SELECT COUNT(*) FROM events WHERE session_id = ?", (session_id,)
            ).fetchone()[0]

            conn.execute(
                """UPDATE sessions
                   SET ended_at = ?, duration_s = ?, event_count = ?
                   WHERE id = ?""",
                (ended_at, duration, count, session_id)
            )
            conn.commit()
        finally:
            conn.close()


# ── Eventos ────────────────────────────────────────────────────────────────────

def save_event(session_id: int, agent_id: str, event_type: str,
               timestamp: str, data: Optional[dict]) -> None:
    """Persiste un evento asociado a una sesión."""
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                """INSERT INTO events (session_id, agent_id, event_type, timestamp, data)
                   VALUES (?, ?, ?, ?, ?)""",
                (session_id, agent_id, event_type, timestamp,
                 json.dumps(data) if data is not None else None)
            )
            conn.commit()
        finally:
            conn.close()


# ── Consultas ──────────────────────────────────────────────────────────────────

def list_sessions() -> list[dict]:
    """Devuelve todas las sesiones ordenadas de más reciente a más antigua."""
    with _lock:
        conn = _connect()
        try:
            rows = conn.execute(
                """SELECT id, agent_id, started_at, ended_at, duration_s, event_count
                   FROM sessions
                   ORDER BY id DESC"""
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()


def get_session(session_id: int) -> Optional[dict]:
    """Devuelve los metadatos de una sesión o None si no existe."""
    with _lock:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT * FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()


def get_session_events(session_id: int) -> list[dict]:
    """Devuelve todos los eventos de una sesión en orden cronológico."""
    with _lock:
        conn = _connect()
        try:
            rows = conn.execute(
                """SELECT id, agent_id, event_type, timestamp, data
                   FROM events
                   WHERE session_id = ?
                   ORDER BY id ASC""",
                (session_id,)
            ).fetchall()
            result = []
            for r in rows:
                ev = dict(r)
                ev["data"] = json.loads(ev["data"]) if ev["data"] else None
                result.append(ev)
            return result
        finally:
            conn.close()


def delete_session(session_id: int) -> bool:
    """Elimina una sesión y todos sus eventos (CASCADE). Devuelve True si existía."""
    with _lock:
        conn = _connect()
        try:
            cur = conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()


def delete_all_sessions() -> int:
    """Elimina todas las sesiones. Devuelve el número eliminado."""
    with _lock:
        conn = _connect()
        try:
            cur = conn.execute("DELETE FROM sessions")
            conn.commit()
            return cur.rowcount
        finally:
            conn.close()


# ── Utilidades ─────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
