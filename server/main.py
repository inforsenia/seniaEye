from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
import json
import asyncio
import subprocess
import socket as _socket
import subprocess
import socket as _socket
from datetime import datetime
from pathlib import Path
import os
import logging

from server.database import (
    init_db, open_session, close_session, save_event,
    list_sessions, get_session, get_session_events,
    delete_session, delete_all_sessions,
    add_blocked_domain, remove_blocked_domain, list_blocked_domains,
    get_blocked_domain_list, domain_exists, clear_all_blocked_domains,
    add_dns_doh_server, remove_dns_doh_server, list_dns_doh_servers,
    get_dns_doh_ips, dns_doh_server_exists, update_dns_doh_server,
    clear_all_dns_doh_servers
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


def _load_blocked_domains_from_db():
    """Load and resolve blocked domains from database at server boot."""
    global resolved_domains, resolver_timestamp

    try:
        domains = get_blocked_domain_list()

        if not domains:
            logger.warning("No blocked domains found in database")
            return

        logger.info(f"[BOOT] Loading {len(domains)} domain(s) from database")
        resolver = DomainResolver()
        resolved_domains = resolver.resolve_domains(domains)
        resolver_timestamp = resolver.get_timestamp()

        total_ips = sum(len(ips) for ips in resolved_domains.values())
        logger.info(f"[BOOT] Loaded {len(resolved_domains)} domain(s) with {total_ips} total IP(s)")

    except Exception as e:
        logger.error(f"Failed to load blocked domains from database: {e}")


def _resolve_domains(domain_list: list[str]) -> dict:
    """Resolve a list of domains to IPs."""
    try:
        resolver = DomainResolver()
        return resolver.resolve_domains(domain_list)
    except Exception as e:
        logger.error(f"Failed to resolve domains: {e}")
        return {}


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
            "agents": {aid: {"online": True, "status": e["status"]} for aid, e in self.agents.items()},
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

# Cargar dominios bloqueados al arrancar desde BD
_load_blocked_domains_from_db()

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
"""
def _get_aula() -> str:
    try:
        hostname = _socket.gethostname()
        ip = _socket.gethostbyname(hostname)
        return ip.split('.')[2]
    except Exception:
        return "0"


def _run_senia(args: list[str]) -> str:
    result = subprocess.run(
        ["senia-firefox"] + args,
        capture_output=True, text=True, timeout=10
    )
    return result.stdout.strip()


@app.get("/api/internet/status")
async def api_inet_status():
    aula = _get_aula()
    output = await asyncio.get_event_loop().run_in_executor(
        None, lambda: _run_senia([aula, "status"])
    )
    on = "HAY INTERNET" in output.upper()
    return JSONResponse({"status": "on" if on else "off", "raw": output, "aula": aula})


@app.post("/api/internet/{value}")
async def api_inet_set(value: int):
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
"""

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


# ── API REST: Blocked Domains Management ───────────────────────────────────────

@app.get("/api/blocked-domains")
async def api_list_blocked_domains():
    """Get all blocked domains from database."""
    domains = list_blocked_domains()
    return JSONResponse({
        "timestamp": _now(),
        "domains": domains,
        "total": len(domains)
    })


@app.post("/api/blocked-domains")
async def api_add_blocked_domain(domain: str):
    """Add a new blocked domain and resolve it."""
    global resolved_domains, resolver_timestamp
    
    if not domain or not domain.strip():
        raise HTTPException(status_code=400, detail="Domain cannot be empty")
    
    domain = domain.strip()
    
    if domain_exists(domain):
        raise HTTPException(status_code=409, detail=f"Domain {domain} already exists")
    
    # Add to database
    success = add_blocked_domain(domain)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to add domain to database")
    
    # Resolve the domain
    ips = _resolve_domains([domain])
    if domain in ips:
        resolved_domains[domain] = ips[domain]
        resolver_timestamp = _now()
    
    logger.info(f"Added blocked domain: {domain}")
    
    return JSONResponse({
        "success": True,
        "domain": domain,
        "ips": ips.get(domain, []),
        "timestamp": _now()
    })


@app.delete("/api/blocked-domains/{domain}")
async def api_remove_blocked_domain(domain: str):
    """Remove a blocked domain."""
    global resolved_domains, resolver_timestamp
    
    if not domain or not domain.strip():
        raise HTTPException(status_code=400, detail="Domain cannot be empty")
    
    domain = domain.strip()
    
    success = remove_blocked_domain(domain)
    if not success:
        raise HTTPException(status_code=404, detail=f"Domain {domain} not found")
    
    # Remove from resolved cache
    if domain in resolved_domains:
        del resolved_domains[domain]
        resolver_timestamp = _now()
    
    logger.info(f"Removed blocked domain: {domain}")
    
    return JSONResponse({
        "success": True,
        "deleted_domain": domain,
        "timestamp": _now()
    })


@app.post("/api/blocked-domains/reload")
async def api_reload_blocked_domains():
    """Reload and resolve all blocked domains from database."""
    global resolved_domains, resolver_timestamp
    
    try:
        _load_blocked_domains_from_db()
        return JSONResponse({
            "success": True,
            "total_domains": len(resolved_domains),
            "total_ips": sum(len(ips) for ips in resolved_domains.values()),
            "timestamp": resolver_timestamp
        })
    except Exception as e:
        logger.error(f"Error reloading domains: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reload domains: {str(e)}")


# ── API REST: DNS DoH Servers Management ───────────────────────────────────────

@app.get("/api/dns-doh/list")
async def api_list_dns_doh():
    """Get all DNS DoH servers."""
    servers = list_dns_doh_servers()
    return JSONResponse({
        "timestamp": _now(),
        "servers": servers,
        "total": len(servers)
    })


@app.post("/api/dns-doh/add")
async def api_add_dns_doh(ip_address: str, hostname: str = None, description: str = None):
    """Add a new DNS DoH server."""
    if not ip_address or not ip_address.strip():
        raise HTTPException(status_code=400, detail="IP address cannot be empty")
    
    ip_address = ip_address.strip()
    
    if dns_doh_server_exists(ip_address):
        raise HTTPException(status_code=409, detail=f"Server {ip_address} already exists")
    
    success = add_dns_doh_server(ip_address, hostname, description)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to add DoH server")
    
    logger.info(f"Added DNS DoH server: {ip_address}")
    
    return JSONResponse({
        "success": True,
        "ip_address": ip_address,
        "hostname": hostname,
        "description": description,
        "timestamp": _now()
    })


@app.put("/api/dns-doh/{ip_address}")
async def api_update_dns_doh(ip_address: str, hostname: str = None, description: str = None):
    """Update a DNS DoH server."""
    if not ip_address or not ip_address.strip():
        raise HTTPException(status_code=400, detail="IP address cannot be empty")
    
    ip_address = ip_address.strip()
    
    if not dns_doh_server_exists(ip_address):
        raise HTTPException(status_code=404, detail=f"Server {ip_address} not found")
    
    success = update_dns_doh_server(ip_address, hostname, description)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update DoH server")
    
    logger.info(f"Updated DNS DoH server: {ip_address}")
    
    return JSONResponse({
        "success": True,
        "ip_address": ip_address,
        "hostname": hostname,
        "description": description,
        "timestamp": _now()
    })


@app.delete("/api/dns-doh/{ip_address}")
async def api_remove_dns_doh(ip_address: str):
    """Remove a DNS DoH server."""
    if not ip_address or not ip_address.strip():
        raise HTTPException(status_code=400, detail="IP address cannot be empty")
    
    ip_address = ip_address.strip()
    
    success = remove_dns_doh_server(ip_address)
    if not success:
        raise HTTPException(status_code=404, detail=f"Server {ip_address} not found")
    
    logger.info(f"Removed DNS DoH server: {ip_address}")
    
    return JSONResponse({
        "success": True,
        "deleted_ip": ip_address,
        "timestamp": _now()
    })


@app.post("/api/dns-doh/clear-all")
async def api_clear_all_dns_doh():
    """Clear all DNS DoH servers."""
    count = clear_all_dns_doh_servers()
    logger.info(f"Cleared all DNS DoH servers ({count} removed)")
    
    return JSONResponse({
        "success": True,
        "cleared_count": count,
        "timestamp": _now()
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

@app.get("/domains")
async def serve_domains():
    return FileResponse(BASE_DIR / "static" / "domains.html")