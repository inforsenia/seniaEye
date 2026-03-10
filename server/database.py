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

                CREATE TABLE IF NOT EXISTS blocked_domains (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    domain      TEXT    NOT NULL UNIQUE,
                    created_at  TEXT    NOT NULL,
                    updated_at  TEXT    NOT NULL
                );

                CREATE TABLE IF NOT EXISTS dns_doh_servers (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    ip_address  TEXT    NOT NULL UNIQUE,
                    hostname    TEXT,
                    description TEXT,
                    created_at  TEXT    NOT NULL,
                    updated_at  TEXT    NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id);
                CREATE INDEX IF NOT EXISTS idx_sessions_agent ON sessions(agent_id);
                CREATE INDEX IF NOT EXISTS idx_blocked_domains_domain ON blocked_domains(domain);
                CREATE INDEX IF NOT EXISTS idx_dns_doh_servers_ip ON dns_doh_servers(ip_address);
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


# ── Dominios Bloqueados ────────────────────────────────────────────────────────

def add_blocked_domain(domain: str) -> bool:
    """Agrega un dominio bloqueado. Devuelve True si se agregó, False si ya existe."""
    with _lock:
        conn = _connect()
        try:
            now = _now()
            conn.execute(
                "INSERT INTO blocked_domains (domain, created_at, updated_at) VALUES (?, ?, ?)",
                (domain.strip(), now, now)
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()


def remove_blocked_domain(domain: str) -> bool:
    """Elimina un dominio bloqueado. Devuelve True si se eliminó."""
    with _lock:
        conn = _connect()
        try:
            cur = conn.execute(
                "DELETE FROM blocked_domains WHERE domain = ?",
                (domain.strip(),)
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()


def list_blocked_domains() -> list[dict]:
    """Devuelve todos los dominios bloqueados ordenados por fecha de creación descendente."""
    with _lock:
        conn = _connect()
        try:
            rows = conn.execute(
                "SELECT id, domain, created_at, updated_at FROM blocked_domains ORDER BY created_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()


def get_blocked_domain_list() -> list[str]:
    """Devuelve solo la lista de dominios (strings)."""
    with _lock:
        conn = _connect()
        try:
            rows = conn.execute(
                "SELECT domain FROM blocked_domains ORDER BY domain"
            ).fetchall()
            return [r[0] for r in rows]
        finally:
            conn.close()


def domain_exists(domain: str) -> bool:
    """Verifica si un dominio existe en la base de datos."""
    with _lock:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT id FROM blocked_domains WHERE domain = ?",
                (domain.strip(),)
            ).fetchone()
            return row is not None
        finally:
            conn.close()


def clear_all_blocked_domains() -> int:
    """Elimina todos los dominios bloqueados. Devuelve el número eliminado."""
    with _lock:
        conn = _connect()
        try:
            cur = conn.execute("DELETE FROM blocked_domains")
            conn.commit()
            return cur.rowcount
        finally:
            conn.close()


# ── Servidores DNS DoH ─────────────────────────────────────────────────────────

def add_dns_doh_server(ip_address: str, hostname: str = None, description: str = None) -> bool:
    """Agrega un servidor DNS DoH. Devuelve True si se agregó, False si ya existe."""
    with _lock:
        conn = _connect()
        try:
            now = _now()
            conn.execute(
                """INSERT INTO dns_doh_servers (ip_address, hostname, description, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (ip_address.strip(), hostname, description, now, now)
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()


def remove_dns_doh_server(ip_address: str) -> bool:
    """Elimina un servidor DNS DoH. Devuelve True si se eliminó."""
    with _lock:
        conn = _connect()
        try:
            cur = conn.execute(
                "DELETE FROM dns_doh_servers WHERE ip_address = ?",
                (ip_address.strip(),)
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()


def list_dns_doh_servers() -> list[dict]:
    """Devuelve todos los servidores DNS DoH ordenados por fecha de creación descendente."""
    with _lock:
        conn = _connect()
        try:
            rows = conn.execute(
                """SELECT id, ip_address, hostname, description, created_at, updated_at
                   FROM dns_doh_servers ORDER BY created_at DESC"""
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()


def get_dns_doh_ips() -> list[str]:
    """Devuelve solo la lista de IPs de servidores DNS DoH."""
    with _lock:
        conn = _connect()
        try:
            rows = conn.execute(
                "SELECT ip_address FROM dns_doh_servers ORDER BY ip_address"
            ).fetchall()
            return [r[0] for r in rows]
        finally:
            conn.close()


def dns_doh_server_exists(ip_address: str) -> bool:
    """Verifica si un servidor DNS DoH existe en la base de datos."""
    with _lock:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT id FROM dns_doh_servers WHERE ip_address = ?",
                (ip_address.strip(),)
            ).fetchone()
            return row is not None
        finally:
            conn.close()


def update_dns_doh_server(ip_address: str, hostname: str = None, description: str = None) -> bool:
    """Actualiza un servidor DNS DoH. Devuelve True si se actualizó."""
    with _lock:
        conn = _connect()
        try:
            updates = []
            params = []
            
            if hostname is not None:
                updates.append("hostname = ?")
                params.append(hostname)
            if description is not None:
                updates.append("description = ?")
                params.append(description)
            
            if not updates:
                return False
            
            updates.append("updated_at = ?")
            params.append(_now())
            params.append(ip_address.strip())
            
            query = f"UPDATE dns_doh_servers SET {', '.join(updates)} WHERE ip_address = ?"
            cur = conn.execute(query, params)
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()


def clear_all_dns_doh_servers() -> int:
    """Elimina todos los servidores DNS DoH. Devuelve el número eliminado."""
    with _lock:
        conn = _connect()
        try:
            cur = conn.execute("DELETE FROM dns_doh_servers")
            conn.commit()
            return cur.rowcount
        finally:
            conn.close()



# ── Utilidades ─────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
