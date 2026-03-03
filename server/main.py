from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
import json
import asyncio
import subprocess
import socket as _socket
from datetime import datetime
from pathlib import Path
import os
import logging

from server.database import (
    init_db, open_session, close_session, save_event,
    list_sessions, get_session, get_session_events,
    delete_session, delete_all_sessions
)
from server.domain_resolver import DomainResolver
from server.port_rules_manager import PortRulesManager

app = FastAPI()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Inicializar DB al arrancar
init_db()

# ── Domain Resolution ──────────────────────────────────────────────────────────
resolved_domains: dict = {}
resolver_timestamp: str = ""

# ── Port Rules ─────────────────────────────────────────────────────────────────
port_rules_manager: PortRulesManager = None


def _load_blocked_domains():
    """Load and resolve blocked domains at server boot."""
    global resolved_domains, resolver_timestamp

    blocked_domains_file = Path(os.path.dirname(os.path.abspath(__file__))) / "blocked_domains.txt"

    if not blocked_domains_file.exists():
        logger.warning(f"blocked_domains.txt not found at {blocked_domains_file}")
        return

    try:
        with open(blocked_domains_file, 'r') as f:
            domains = [line.strip() for line in f if line.strip()]

        if not domains:
            logger.warning("blocked_domains.txt is empty")
            return

        logger.info(f"[BOOT] Loading {len(domains)} domain(s)")
        resolver = DomainResolver()
        resolved_domains = resolver.resolve_domains(domains)
        resolver_timestamp = resolver.get_timestamp()

        total_ips = sum(len(ips) for ips in resolved_domains.values())
        logger.info(f"[BOOT] Loaded {len(resolved_domains)} domain(s) with {total_ips} total IP(s)")

    except Exception as e:
        logger.error(f"Failed to load blocked domains: {e}")


# ── Comandos ───────────────────────────────────────────────────────────────────
CMD_START = "START_MONITORING"
CMD_STOP  = "STOP_MONITORING"

# ── Estado global ──────────────────────────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self.agents: dict[str, dict] = {}
        self.dashboards: list[WebSocket] = []
        self.event_log: list[dict] = []

    async def connect_agent(self, ws: WebSocket, agent_id: str):
        session_id = open_session(agent_id)
        self.agents[agent_id] = {"ws": ws, "status": "waiting", "session_id": session_id}
        ev = {"type": "agent_connected", "agent_id": agent_id,
              "status": "waiting", "timestamp": _now()}
        self._append_log(ev)
        save_event(session_id, agent_id, "agent_connected", ev["timestamp"], None)
        await self._broadcast_dashboard(ev)

    def disconnect_agent(self, agent_id: str):
        entry = self.agents.pop(agent_id, None)
        if entry:
            close_session(entry["session_id"])
        ev = {"type": "agent_disconnected", "agent_id": agent_id, "timestamp": _now()}
        self._append_log(ev)
        asyncio.create_task(self._broadcast_dashboard(ev))

    async def handle_agent_message(self, agent_id: str, raw: str):
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"raw": raw}

        entry = self.agents.get(agent_id, {})
        session_id = entry.get("session_id")

        if "ack" in payload:
            new_status = "monitoring" if payload["ack"] == CMD_START else "waiting"
            if agent_id in self.agents:
                self.agents[agent_id]["status"] = new_status
            ev = {"type": "agent_status", "agent_id": agent_id,
                  "status": new_status, "timestamp": _now()}
            self._append_log(ev)
            if session_id:
                save_event(session_id, agent_id, "agent_status", ev["timestamp"],
                           {"status": new_status})
            await self._broadcast_dashboard(ev)
            return

        ts = _now()
        record = {"type": "event", "agent_id": agent_id, "timestamp": ts, "data": payload}
        self._append_log(record)
        if session_id:
            save_event(session_id, agent_id, "event", ts, payload)
        await self._broadcast_dashboard(record)

    async def send_command(self, agent_id: str, command: str) -> bool:
        entry = self.agents.get(agent_id)
        if not entry:
            return False
        await entry["ws"].send_text(json.dumps({"command": command}))
        return True

    async def broadcast_command(self, command: str) -> list[str]:
        reached, dead = [], []
        for agent_id, entry in self.agents.items():
            try:
                await entry["ws"].send_text(json.dumps({"command": command}))
                reached.append(agent_id)
            except Exception:
                dead.append(agent_id)
        for aid in dead:
            self.disconnect_agent(aid)
        return reached

    async def connect_dashboard(self, ws: WebSocket):
        self.dashboards.append(ws)
        snapshot = {
            "type": "snapshot",
            "agents": {aid: e["status"] for aid, e in self.agents.items()},
            "events": self.event_log[-500:]
        }
        await ws.send_text(json.dumps(snapshot))

    def disconnect_dashboard(self, ws: WebSocket):
        if ws in self.dashboards:
            self.dashboards.remove(ws)

    def _append_log(self, ev: dict):
        self.event_log.append(ev)
        if len(self.event_log) > 2000:
            self.event_log = self.event_log[-1000:]

    async def _broadcast_dashboard(self, message: dict):
        text = json.dumps(message)
        dead = []
        for ws in self.dashboards:
            try:
                await ws.send_text(text)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.dashboards.remove(ws)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


manager = ConnectionManager()

# Cargar dominios bloqueados al arrancar
_load_blocked_domains()

# Cargar reglas de puertos al arrancar
try:
    port_rules_manager = PortRulesManager("server/allowed_ports_config.yaml")
except Exception as e:
    logger.error(f"Failed to load port rules: {e}")
    port_rules_manager = PortRulesManager.__new__(PortRulesManager)
    port_rules_manager.rules = {}


# ── WebSocket: Agentes ─────────────────────────────────────────────────────────

@app.websocket("/ws/events")
async def websocket_agents(websocket: WebSocket):
    await websocket.accept()
    agent_id = websocket.client.host
    print(f"[+] Agente conectado: {agent_id}")
    await manager.connect_agent(websocket, agent_id)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.handle_agent_message(agent_id, data)
    except WebSocketDisconnect:
        print(f"[-] Agente desconectado: {agent_id}")
        manager.disconnect_agent(agent_id)


# ── WebSocket: Dashboard ───────────────────────────────────────────────────────

@app.websocket("/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket):
    await websocket.accept()
    print("[+] Dashboard conectado")
    await manager.connect_dashboard(websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            action = msg.get("action")

            if action == "send_command":
                agent_id = msg["agent_id"]
                command  = msg["command"]
                success  = await manager.send_command(agent_id, command)
                await websocket.send_text(json.dumps({
                    "type": "command_ack", "agent_id": agent_id,
                    "command": command, "success": success, "timestamp": _now()
                }))

            elif action == "broadcast_command":
                command = msg["command"]
                reached = await manager.broadcast_command(command)
                await websocket.send_text(json.dumps({
                    "type": "broadcast_ack", "command": command,
                    "reached": reached, "count": len(reached), "timestamp": _now()
                }))

    except WebSocketDisconnect:
        print("[-] Dashboard desconectado")
        manager.disconnect_dashboard(websocket)


# ── API REST: Internet (senia-firefox) ─────────────────────────────────────────

def _get_aula() -> str:
    """Obtiene el tercer octeto de la IP del servidor (número de aula)."""
    try:
        hostname = _socket.gethostname()
        ip = _socket.gethostbyname(hostname)
        return ip.split('.')[2]
    except Exception:
        return "0"


def _run_senia(args: list[str]) -> str:
    """Ejecuta senia-firefox con los argumentos dados y devuelve stdout."""
    result = subprocess.run(
        ["senia-firefox"] + args,
        capture_output=True, text=True, timeout=10
    )
    return result.stdout.strip()


@app.get("/api/internet/status")
async def api_inet_status():
    """Consulta el estado de internet via: senia-firefox <aula> status"""
    aula = _get_aula()
    output = await asyncio.get_event_loop().run_in_executor(
        None, lambda: _run_senia([aula, "status"])
    )
    on = "HAY INTERNET" in output.upper()
    return JSONResponse({"status": "on" if on else "off", "raw": output, "aula": aula})


@app.post("/api/internet/{value}")
async def api_inet_set(value: int):
    """Activa (1) o corta (0) internet via: senia-firefox <aula> <0|1>"""
    if value not in (0, 1):
        raise HTTPException(status_code=400, detail="Valor debe ser 0 o 1")
    aula = _get_aula()
    await asyncio.get_event_loop().run_in_executor(
        None, lambda: _run_senia([aula, str(value)])
    )
    # Verificar estado real tras el cambio
    status_out = await asyncio.get_event_loop().run_in_executor(
        None, lambda: _run_senia([aula, "status"])
    )
    on = "HAY INTERNET" in status_out.upper()
    return JSONResponse({"status": "on" if on else "off", "raw": status_out, "aula": aula})


# ── API REST: Block List ───────────────────────────────────────────────────────

@app.get("/api/block-list")
async def api_block_list():
    """Get resolved blocked domains and IPs."""
    return JSONResponse({
        "timestamp": resolver_timestamp,
        "domains": resolved_domains,
        "total_domains": len(resolved_domains),
        "total_ips": sum(len(ips) for ips in resolved_domains.values())
    })


# ── API REST: Port Rules ───────────────────────────────────────────────────────

@app.get("/api/port-rules")
async def api_port_rules():
    """Get all port rules."""
    if not port_rules_manager or not port_rules_manager.rules:
        return JSONResponse({
            "timestamp": _now(),
            "total_rules": 0,
            "rules": []
        })
    return JSONResponse({
        "timestamp": _now(),
        "total_rules": len(port_rules_manager.rules),
        "rules": [rule.to_dict() for rule in port_rules_manager.get_all_rules()]
    })


@app.get("/api/port-rules/{port}")
async def api_port_rule(port: int):
    """Get rule for specific port."""
    if not port_rules_manager:
        raise HTTPException(status_code=404, detail="Port rules not loaded")
    rule = port_rules_manager.get_port_rule(port)
    if not rule:
        raise HTTPException(status_code=404, detail=f"No rule found for port {port}")
    return JSONResponse({
        "port": rule.port,
        "protocol": rule.protocol,
        "description": rule.description,
        "allowed_sources": [source.to_dict() for source in rule.allowed_sources]
    })


# ── API REST: Sesiones ─────────────────────────────────────────────────────────

@app.get("/api/sessions")
async def api_list_sessions():
    return JSONResponse(list_sessions())

@app.get("/api/sessions/{session_id}")
async def api_get_session(session_id: int):
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    events = get_session_events(session_id)
    return JSONResponse({"session": session, "events": events})

@app.delete("/api/sessions/{session_id}")
async def api_delete_session(session_id: int):
    deleted = delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    return JSONResponse({"ok": True, "deleted_id": session_id})

@app.delete("/api/sessions")
async def api_delete_all_sessions():
    count = delete_all_sessions()
    return JSONResponse({"ok": True, "deleted_count": count})


# ── HTTP: Páginas ──────────────────────────────────────────────────────────────

BASE_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

@app.get("/")
async def serve_dashboard():
    return FileResponse(BASE_DIR / "static" / "index.html")

@app.get("/sessions")
async def serve_sessions():
    return FileResponse(BASE_DIR / "static" / "sessions.html")