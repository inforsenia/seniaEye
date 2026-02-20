#!/usr/bin/env python3
"""
SeniaEye – Servidor Central de Monitorización
Flask + Flask-Sock (WebSocket nativo) + SSE para el dashboard en tiempo real
"""

import json
import logging
import os
import queue
import threading
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from flask import Flask, Response, render_template_string, request

try:
    from flask_sock import Sock
except ImportError:
    raise SystemExit("Instala flask-sock:  pip install flask-sock")

# ── Configuración básica ──────────────────────────────────────────────────────
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [SERVIDOR] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("seniaeye-server")

# ══════════════════════════════════════════════════════════════════════════════
# Estado global del servidor
# ══════════════════════════════════════════════════════════════════════════════

class ServerState:
    def __init__(self):
        self._lock = threading.Lock()
        # agent_name → lista de últimos N eventos (para la UI)
        self.agent_events: dict[str, list] = defaultdict(list)
        # Colas SSE por cliente del dashboard (thread-safe)
        self.sse_queues: list[queue.Queue] = []
        # Contadores de infracciones por agente
        self.infraction_counts: dict[str, int] = defaultdict(int)
        # Estado de conexión: agent_name → True/False
        self.connected_agents: set[str] = set()

    # ── Registro de evento ────────────────────────────────────────────────────
    def record_event(self, event: dict):
        agent = event.get("agent", "unknown")
        ts_str = datetime.utcnow().strftime("%H:%M:%S")
        event["received_at"] = ts_str

        with self._lock:
            # Mantener últimos 200 eventos por agente en memoria
            self.agent_events[agent].append(event)
            if len(self.agent_events[agent]) > 200:
                self.agent_events[agent] = self.agent_events[agent][-200:]

            if event.get("severity") == "alert":
                self.infraction_counts[agent] += 1

        # Persistir en fichero
        self._write_to_file(agent, event)

        # Difundir a todas las colas SSE activas
        self._broadcast_sse(event)

    def _write_to_file(self, agent: str, event: dict):
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        filename = LOG_DIR / f"{agent}_{date_str}.jsonl"
        try:
            with open(filename, "a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
        except Exception as exc:
            log.error("Error escribiendo log de agente: %s", exc)

    # ── SSE broadcast ─────────────────────────────────────────────────────────
    def _broadcast_sse(self, event: dict):
        data = json.dumps(event, ensure_ascii=False)
        dead = []
        with self._lock:
            queues = list(self.sse_queues)
        for q in queues:
            try:
                q.put_nowait(data)
            except queue.Full:
                dead.append(q)
        if dead:
            with self._lock:
                for q in dead:
                    try:
                        self.sse_queues.remove(q)
                    except ValueError:
                        pass

    def add_sse_queue(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=500)
        with self._lock:
            self.sse_queues.append(q)
        return q

    def remove_sse_queue(self, q: queue.Queue):
        with self._lock:
            try:
                self.sse_queues.remove(q)
            except ValueError:
                pass

    def agent_connected(self, agent: str):
        with self._lock:
            self.connected_agents.add(agent)
        log.info("Agente conectado: %s", agent)

    def agent_disconnected(self, agent: str):
        with self._lock:
            self.connected_agents.discard(agent)
        log.info("Agente desconectado: %s", agent)

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "connected_agents": list(self.connected_agents),
                "infraction_counts": dict(self.infraction_counts),
                "agent_events": {k: v[-50:] for k, v in self.agent_events.items()},
            }


STATE = ServerState()

# ══════════════════════════════════════════════════════════════════════════════
# Flask + WebSocket
# ══════════════════════════════════════════════════════════════════════════════

app = Flask(__name__)
sock = Sock(app)

SEVERITY_COLOR = {
    "alert":   "#ff4d4d",
    "warning": "#ffaa00",
    "info":    "#44cc88",
}

EVENT_LABELS = {
    "hello":                   "Conexión",
    "heartbeat":               "Heartbeat",
    "unauthorized_port":       "Puerto no autorizado",
    "blacklist_domain_dns":    "Dominio en blacklist (DNS)",
    "blacklist_ip":            "IP en blacklist",
    "blacklist_ip_connection": "Conexión a IP en blacklist",
    "doh_detected":            "DNS over HTTPS detectado",
    "new_interface":           "Nueva interfaz de red",
    "interface_removed":       "Interfaz desconectada",
}

# ── Endpoint WebSocket para agentes ──────────────────────────────────────────
@sock.route("/ws")
def ws_agent(ws):
    agent_name = None
    try:
        while True:
            raw = ws.receive()
            if raw is None:
                break
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                log.warning("JSON inválido recibido: %s", raw[:120])
                continue

            if agent_name is None:
                agent_name = event.get("agent", "unknown")
                STATE.agent_connected(agent_name)

            STATE.record_event(event)
            log.debug("[%s] Evento: %s (%s)", agent_name, event.get("type"), event.get("severity"))

    except Exception as exc:
        log.warning("Conexión WS cerrada (%s): %s", agent_name, exc)
    finally:
        if agent_name:
            STATE.agent_disconnected(agent_name)
            STATE.record_event({
                "agent": agent_name,
                "timestamp": datetime.utcnow().isoformat(),
                "type": "disconnected",
                "severity": "warning",
                "detail": {"note": "Agente desconectado"},
            })


# ── SSE para el dashboard ─────────────────────────────────────────────────────
@app.route("/stream")
def stream():
    q = STATE.add_sse_queue()

    def generate():
        try:
            while True:
                try:
                    data = q.get(timeout=25)
                    yield f"data: {data}\n\n"
                except queue.Empty:
                    yield ": keep-alive\n\n"
        except GeneratorExit:
            pass
        finally:
            STATE.remove_sse_queue(q)

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ── API JSON de estado ────────────────────────────────────────────────────────
@app.route("/api/state")
def api_state():
    return STATE.snapshot()


@app.route("/api/logs/<agent_name>")
def api_agent_logs(agent_name):
    date_str = request.args.get("date", datetime.utcnow().strftime("%Y-%m-%d"))
    filepath = LOG_DIR / f"{agent_name}_{date_str}.jsonl"
    if not filepath.exists():
        return {"events": [], "error": "Archivo no encontrado"}, 404
    events = []
    with open(filepath, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except Exception:
                    pass
    return {"events": events}


# ── Dashboard HTML ────────────────────────────────────────────────────────────
DASHBOARD_HTML = r"""
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SeniaEye – Monitor de Aula</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Barlow:wght@300;600;800&display=swap');

  :root {
    --bg: #0b0e14;
    --surface: #111621;
    --surface2: #171d2c;
    --border: #1e2840;
    --accent: #00e5ff;
    --alert: #ff4444;
    --warn: #ffaa00;
    --ok: #00e676;
    --text: #cdd9f0;
    --muted: #5a6a88;
    --font-mono: 'Share Tech Mono', monospace;
    --font-ui: 'Barlow', sans-serif;
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: var(--font-ui);
    min-height: 100vh;
    display: flex;
    flex-direction: column;
  }

  /* ── Header ─────────────────────────────────────────────────── */
  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 28px;
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    position: sticky; top: 0; z-index: 100;
  }
  .logo {
    font-family: var(--font-mono);
    font-size: 1.4rem;
    color: var(--accent);
    letter-spacing: 3px;
    text-transform: uppercase;
  }
  .logo span { color: var(--text); }
  .status-bar {
    display: flex; gap: 18px; align-items: center;
    font-size: .78rem; font-weight: 600; letter-spacing: 1px;
  }
  .pill {
    padding: 4px 12px;
    border-radius: 20px;
    font-family: var(--font-mono);
    font-size: .72rem;
  }
  .pill-live { background: #001a10; border: 1px solid var(--ok); color: var(--ok); }
  .pill-alert { background: #1a0000; border: 1px solid var(--alert); color: var(--alert); }
  #clock { color: var(--muted); font-family: var(--font-mono); }

  /* ── Layout ──────────────────────────────────────────────────── */
  main { display: flex; flex: 1; gap: 0; overflow: hidden; height: calc(100vh - 57px); }

  /* ── Panel izquierdo: equipos ─────────────────────────────────── */
  #agents-panel {
    width: 240px; min-width: 200px;
    background: var(--surface);
    border-right: 1px solid var(--border);
    display: flex; flex-direction: column;
    overflow-y: auto;
  }
  .panel-title {
    padding: 14px 16px 10px;
    font-size: .68rem; font-weight: 800;
    letter-spacing: 2px; text-transform: uppercase;
    color: var(--muted); border-bottom: 1px solid var(--border);
  }
  .agent-card {
    padding: 12px 16px;
    border-bottom: 1px solid var(--border);
    cursor: pointer;
    transition: background .15s;
  }
  .agent-card:hover, .agent-card.selected { background: var(--surface2); }
  .agent-name {
    font-family: var(--font-mono); font-size: .85rem; color: var(--text);
    margin-bottom: 4px;
  }
  .agent-meta { display: flex; gap: 8px; align-items: center; }
  .dot {
    width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0;
  }
  .dot-online { background: var(--ok); box-shadow: 0 0 6px var(--ok); }
  .dot-offline { background: var(--muted); }
  .infraction-badge {
    margin-left: auto;
    background: var(--alert);
    color: #fff;
    border-radius: 10px;
    padding: 1px 7px;
    font-size: .7rem;
    font-weight: 700;
    display: none;
  }

  /* ── Centro: feed de eventos ──────────────────────────────────── */
  #feed-panel {
    flex: 1; display: flex; flex-direction: column; overflow: hidden;
  }
  .feed-header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 12px 20px;
    border-bottom: 1px solid var(--border);
    background: var(--surface);
  }
  .feed-header h2 { font-size: .9rem; font-weight: 600; letter-spacing: 1px; }
  .btn {
    background: transparent; border: 1px solid var(--border);
    color: var(--text); padding: 4px 14px; border-radius: 4px;
    font-family: var(--font-ui); font-size: .78rem; cursor: pointer;
    transition: border-color .15s, color .15s;
  }
  .btn:hover { border-color: var(--accent); color: var(--accent); }

  #event-feed {
    flex: 1; overflow-y: auto; padding: 10px 16px;
    display: flex; flex-direction: column; gap: 6px;
  }
  .event-row {
    display: grid;
    grid-template-columns: 80px 120px 170px 1fr;
    gap: 12px;
    align-items: start;
    background: var(--surface);
    border: 1px solid var(--border);
    border-left: 3px solid var(--muted);
    border-radius: 4px;
    padding: 8px 12px;
    font-size: .78rem;
    animation: slideIn .2s ease;
  }
  @keyframes slideIn {
    from { opacity:0; transform: translateY(-6px); }
    to   { opacity:1; transform: translateY(0); }
  }
  .event-row.severity-alert  { border-left-color: var(--alert); }
  .event-row.severity-warning{ border-left-color: var(--warn); }
  .event-row.severity-info   { border-left-color: var(--ok); }

  .ev-time  { color: var(--muted); font-family: var(--font-mono); }
  .ev-agent { color: var(--accent); font-family: var(--font-mono); font-weight: 600; }
  .ev-type  { color: var(--text); font-weight: 600; }
  .ev-detail{ color: var(--muted); font-family: var(--font-mono); word-break: break-all; }

  /* ── Panel derecho: stats ─────────────────────────────────────── */
  #stats-panel {
    width: 260px; min-width: 220px;
    background: var(--surface);
    border-left: 1px solid var(--border);
    display: flex; flex-direction: column; overflow-y: auto;
  }
  .stat-block {
    padding: 16px 18px;
    border-bottom: 1px solid var(--border);
  }
  .stat-label {
    font-size: .66rem; font-weight: 800; letter-spacing: 2px;
    text-transform: uppercase; color: var(--muted); margin-bottom: 8px;
  }
  .stat-value {
    font-family: var(--font-mono); font-size: 2rem; color: var(--accent); font-weight: 400;
  }
  .stat-value.red { color: var(--alert); }

  .infraction-list { list-style: none; display: flex; flex-direction: column; gap: 4px; }
  .infraction-item {
    display: flex; justify-content: space-between; align-items: center;
    font-size: .78rem; padding: 4px 0;
    border-bottom: 1px solid var(--border);
  }
  .infraction-item:last-child { border-bottom: none; }
  .infraction-agent { font-family: var(--font-mono); color: var(--text); }
  .infraction-count {
    font-family: var(--font-mono); font-weight: 700;
    color: var(--alert); font-size: .9rem;
  }

  /* ── Scrollbar ─────────────────────────────────────────────────── */
  ::-webkit-scrollbar { width: 5px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }

  .empty-state {
    text-align: center; color: var(--muted);
    font-size: .8rem; padding: 30px; font-family: var(--font-mono);
  }

  /* blink para nuevas alertas */
  @keyframes blink { 0%,100%{opacity:1} 50%{opacity:.3} }
  .blink { animation: blink 1s ease 3; }
</style>
</head>
<body>

<header>
  <div class="logo">SENIA<span>EYE</span></div>
  <div class="status-bar">
    <span id="sse-status" class="pill pill-live">● EN VIVO</span>
    <span class="pill" id="alert-pill" style="display:none">⚠ ALERTAS</span>
    <span id="clock">--:--:--</span>
  </div>
</header>

<main>
  <!-- Equipos -->
  <aside id="agents-panel">
    <div class="panel-title">Equipos</div>
    <div id="agent-list"><div class="empty-state">Sin agentes</div></div>
  </aside>

  <!-- Feed -->
  <section id="feed-panel">
    <div class="feed-header">
      <h2 id="feed-title">TODOS LOS EQUIPOS</h2>
      <button class="btn" onclick="clearFeed()">Limpiar</button>
    </div>
    <div id="event-feed"><div class="empty-state" id="no-events">Esperando eventos…</div></div>
  </section>

  <!-- Stats -->
  <aside id="stats-panel">
    <div class="stat-block">
      <div class="stat-label">Equipos activos</div>
      <div class="stat-value" id="stat-connected">0</div>
    </div>
    <div class="stat-block">
      <div class="stat-label">Total alertas (sesión)</div>
      <div class="stat-value red" id="stat-alerts">0</div>
    </div>
    <div class="stat-block">
      <div class="stat-label">Infracciones por equipo</div>
      <ul class="infraction-list" id="infraction-list">
        <li class="empty-state" style="list-style:none">Sin datos</li>
      </ul>
    </div>
  </aside>
</main>

<script>
  // ── Estado cliente ──────────────────────────────────────────────────────
  const agents = {};       // name → { connected, infractions, events[] }
  let totalAlerts = 0;
  let selectedAgent = null;  // null = todos
  let MAX_ROWS = 300;

  const eventLabels = {
    "hello":                   "Conexión",
    "heartbeat":               "Heartbeat",
    "unauthorized_port":       "Puerto no autorizado",
    "blacklist_domain_dns":    "Dominio en blacklist (DNS)",
    "blacklist_ip":            "IP en blacklist",
    "blacklist_ip_connection": "Conexión a IP en blacklist",
    "doh_detected":            "DoH detectado",
    "new_interface":           "Nueva interfaz de red",
    "interface_removed":       "Interfaz desconectada",
    "disconnected":            "Desconectado",
  };

  // ── Reloj ───────────────────────────────────────────────────────────────
  function tick() {
    const d = new Date();
    document.getElementById('clock').textContent =
      d.toLocaleTimeString('es-ES', {hour12: false});
  }
  setInterval(tick, 1000); tick();

  // ── SSE ─────────────────────────────────────────────────────────────────
  const statusEl = document.getElementById('sse-status');

  function connectSSE() {
    const es = new EventSource('/stream');
    es.onopen = () => {
      statusEl.textContent = '● EN VIVO';
      statusEl.className = 'pill pill-live';
    };
    es.onerror = () => {
      statusEl.textContent = '○ SIN CONEXIÓN';
      statusEl.className = 'pill pill-alert';
    };
    es.onmessage = (e) => {
      const ev = JSON.parse(e.data);
      handleEvent(ev);
    };
  }

  // ── Manejo de eventos ───────────────────────────────────────────────────
  function handleEvent(ev) {
    const name = ev.agent || 'unknown';

    // Inicializar agente
    if (!agents[name]) {
      agents[name] = { connected: false, infractions: 0, events: [] };
    }
    const ag = agents[name];
    ag.events.push(ev);
    if (ag.events.length > 200) ag.events.shift();

    // Estado conexión
    if (ev.type === 'hello' || (ev.type !== 'disconnected')) {
      ag.connected = true;
    }
    if (ev.type === 'disconnected') {
      ag.connected = false;
    }

    // Infracciones
    if (ev.severity === 'alert') {
      ag.infractions++;
      totalAlerts++;
    }

    renderAgentList();
    renderStats();

    // Mostrar en feed si corresponde
    if (selectedAgent === null || selectedAgent === name) {
      addEventRow(ev);
    }
  }

  // ── Renderizar lista de agentes ─────────────────────────────────────────
  function renderAgentList() {
    const list = document.getElementById('agent-list');
    list.innerHTML = '';
    const names = Object.keys(agents).sort();
    if (names.length === 0) {
      list.innerHTML = '<div class="empty-state">Sin agentes</div>';
      return;
    }
    names.forEach(name => {
      const ag = agents[name];
      const div = document.createElement('div');
      div.className = 'agent-card' + (selectedAgent === name ? ' selected' : '');
      div.onclick = () => selectAgent(name);
      div.innerHTML = `
        <div class="agent-name">${name}</div>
        <div class="agent-meta">
          <span class="dot ${ag.connected ? 'dot-online' : 'dot-offline'}"></span>
          <span style="font-size:.72rem;color:var(--muted)">${ag.connected ? 'online' : 'offline'}</span>
          ${ag.infractions > 0 ? `<span class="infraction-badge" style="display:block">${ag.infractions}</span>` : ''}
        </div>`;
      list.appendChild(div);
    });
  }

  // ── Stats panel ─────────────────────────────────────────────────────────
  function renderStats() {
    const connected = Object.values(agents).filter(a => a.connected).length;
    document.getElementById('stat-connected').textContent = connected;
    document.getElementById('stat-alerts').textContent = totalAlerts;

    if (totalAlerts > 0) {
      const ap = document.getElementById('alert-pill');
      ap.style.display = 'block';
      ap.textContent = `⚠ ${totalAlerts} ALERTA${totalAlerts>1?'S':''}`;
      ap.className = 'pill pill-alert';
    }

    const ul = document.getElementById('infraction-list');
    const entries = Object.entries(agents)
      .filter(([,ag]) => ag.infractions > 0)
      .sort(([,a],[,b]) => b.infractions - a.infractions);
    if (entries.length === 0) {
      ul.innerHTML = '<li class="empty-state" style="list-style:none">Sin infracciones</li>';
      return;
    }
    ul.innerHTML = entries.map(([n, ag]) => `
      <li class="infraction-item">
        <span class="infraction-agent">${n}</span>
        <span class="infraction-count">${ag.infractions}</span>
      </li>`).join('');
  }

  // ── Selección de agente ─────────────────────────────────────────────────
  function selectAgent(name) {
    if (selectedAgent === name) {
      selectedAgent = null;
      document.getElementById('feed-title').textContent = 'TODOS LOS EQUIPOS';
    } else {
      selectedAgent = name;
      document.getElementById('feed-title').textContent = name.toUpperCase();
    }
    rebuildFeed();
    renderAgentList();
  }

  function rebuildFeed() {
    const feed = document.getElementById('event-feed');
    feed.innerHTML = '';
    let evs = [];
    if (selectedAgent === null) {
      Object.values(agents).forEach(ag => evs.push(...ag.events));
      evs.sort((a,b) => (a.timestamp||'').localeCompare(b.timestamp||''));
    } else {
      evs = (agents[selectedAgent]?.events || []);
    }
    evs.slice(-MAX_ROWS).forEach(addEventRow);
    if (evs.length === 0) {
      feed.innerHTML = '<div class="empty-state" id="no-events">Sin eventos para este equipo</div>';
    }
  }

  // ── Añadir fila al feed ─────────────────────────────────────────────────
  function addEventRow(ev) {
    const feed = document.getElementById('event-feed');
    const noEv = document.getElementById('no-events');
    if (noEv) noEv.remove();

    const label = eventLabels[ev.type] || ev.type;
    const detail = ev.detail ? JSON.stringify(ev.detail) : '';
    const time = ev.received_at || ev.timestamp?.slice(11,19) || '';

    const row = document.createElement('div');
    row.className = `event-row severity-${ev.severity || 'info'}`;
    if (ev.severity === 'alert') row.classList.add('blink');

    row.innerHTML = `
      <span class="ev-time">${time}</span>
      <span class="ev-agent">${ev.agent}</span>
      <span class="ev-type">${label}</span>
      <span class="ev-detail">${detail}</span>`;

    feed.prepend(row);  // Más recientes arriba

    // Limitar filas en DOM
    while (feed.children.length > MAX_ROWS) {
      feed.removeChild(feed.lastChild);
    }
  }

  // ── Limpiar feed ────────────────────────────────────────────────────────
  function clearFeed() {
    document.getElementById('event-feed').innerHTML =
      '<div class="empty-state" id="no-events">Feed limpiado</div>';
  }

  // ── Cargar estado inicial desde API ────────────────────────────────────
  fetch('/api/state').then(r => r.json()).then(data => {
    (data.connected_agents || []).forEach(name => {
      if (!agents[name]) agents[name] = { connected: true, infractions: 0, events: [] };
      agents[name].connected = true;
    });
    Object.entries(data.infraction_counts || {}).forEach(([name, count]) => {
      if (!agents[name]) agents[name] = { connected: false, infractions: 0, events: [] };
      agents[name].infractions = count;
      totalAlerts += count;
    });
    renderAgentList();
    renderStats();
  });

  connectSSE();
</script>
</body>
</html>
"""

@app.route("/")
def dashboard():
    return render_template_string(DASHBOARD_HTML)


# ══════════════════════════════════════════════════════════════════════════════
# Entrypoint
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    host = "0.0.0.0"
    port = 5000
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    log.info("SeniaEye Servidor arrancado en ws://%s:%d/ws", host, port)
    log.info("Dashboard → http://localhost:%d", port)
    # Usar threaded=True para manejar múltiples WS simultáneos
    app.run(host=host, port=port, threaded=True, debug=False)
