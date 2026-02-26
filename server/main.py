from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
import json
import asyncio
from datetime import datetime
from pathlib import Path
import os

from server.database import (
    init_db, open_session, close_session, save_event,
    list_sessions, get_session, get_session_events,
    delete_session, delete_all_sessions
)

app = FastAPI()

# Inicializar DB al arrancar
init_db()

# ── Comandos ───────────────────────────────────────────────────────────────────
CMD_START = "START_MONITORING"
CMD_STOP  = "STOP_MONITORING"

# ── Estado global ──────────────────────────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        # agent_id → { "ws", "status", "session_id" }
        self.agents: dict[str, dict] = {}
        self.dashboards: list[WebSocket] = []
        self.event_log: list[dict] = []

    # ── Agentes ────────────────────────────────────────────────────────────────

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

        # ACK de estado
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

        # Evento de monitorización
        ts = _now()
        record = {"type": "event", "agent_id": agent_id, "timestamp": ts, "data": payload}
        self._append_log(record)
        if session_id:
            save_event(session_id, agent_id, "event", ts, payload)
        await self._broadcast_dashboard(record)

    # ── Comandos hacia agentes ─────────────────────────────────────────────────

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

    # ── Dashboard ──────────────────────────────────────────────────────────────

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
