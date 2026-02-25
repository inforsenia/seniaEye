from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import json
import asyncio
from datetime import datetime
from pathlib import Path

app = FastAPI()

# ── Estado global ──────────────────────────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        # Agentes conectados: host → WebSocket
        self.agents: dict[str, WebSocket] = {}
        # Dashboards conectados (solo 1, pero soportamos varios por robustez)
        self.dashboards: list[WebSocket] = []
        # Historial de eventos para nuevos dashboards que se conecten tarde
        self.event_log: list[dict] = []

    async def connect_agent(self, ws: WebSocket, agent_id: str):
        self.agents[agent_id] = ws
        await self._broadcast_dashboard({
            "type": "agent_connected",
            "agent_id": agent_id,
            "timestamp": _now()
        })

    def disconnect_agent(self, agent_id: str):
        self.agents.pop(agent_id, None)
        asyncio.create_task(self._broadcast_dashboard({
            "type": "agent_disconnected",
            "agent_id": agent_id,
            "timestamp": _now()
        }))

    async def connect_dashboard(self, ws: WebSocket):
        self.dashboards.append(ws)
        # Enviar estado actual: agentes conectados + historial
        snapshot = {
            "type": "snapshot",
            "agents": list(self.agents.keys()),
            "events": self.event_log[-500:]  # últimos 500 eventos
        }
        await ws.send_text(json.dumps(snapshot))

    def disconnect_dashboard(self, ws: WebSocket):
        self.dashboards.remove(ws)

    async def handle_agent_event(self, agent_id: str, raw: str):
        try:
            evento = json.loads(raw)
        except json.JSONDecodeError:
            evento = {"raw": raw}

        record = {
            "type": "event",
            "agent_id": agent_id,
            "timestamp": _now(),
            "data": evento
        }
        self.event_log.append(record)
        if len(self.event_log) > 2000:
            self.event_log = self.event_log[-1000:]

        await self._broadcast_dashboard(record)

    async def send_command(self, agent_id: str, command: dict) -> bool:
        """Envía un comando a un agente específico. Devuelve True si tuvo éxito."""
        ws = self.agents.get(agent_id)
        if not ws:
            return False
        await ws.send_text(json.dumps(command))
        return True

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
            await manager.handle_agent_event(agent_id, data)
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
            # El dashboard puede enviar comandos: {"action":"send_command","agent_id":"...","command":{...}}
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            if msg.get("action") == "send_command":
                success = await manager.send_command(msg["agent_id"], msg["command"])
                await websocket.send_text(json.dumps({
                    "type": "command_ack",
                    "agent_id": msg["agent_id"],
                    "success": success,
                    "timestamp": _now()
                }))
    except WebSocketDisconnect:
        print("[-] Dashboard desconectado")
        manager.disconnect_dashboard(websocket)


# ── HTTP: Servir el dashboard ──────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent
#BASE_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
print(f"Base directory: {BASE_DIR}")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

@app.get("/")
async def serve_dashboard():
    return FileResponse(BASE_DIR / "static" / "index.html")