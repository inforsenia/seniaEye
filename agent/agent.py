#!/usr/bin/env python3
"""
SeniaEye - Agente de Monitorización de Equipos en Aula
"""

import asyncio
import configparser
import json
import logging
import os
import platform
import socket
import time
from datetime import datetime
from pathlib import Path

import psutil
import websockets
import websockets.exceptions

# ── Intentar importar scapy (requiere permisos root) ──────────────────────────
try:
    from scapy.all import DNS, DNSQR, IP, TCP, UDP, sniff
    SCAPY_AVAILABLE = True
except ImportError:
    SCAPY_AVAILABLE = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [AGENTE] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("seniaeye-agent")

# ══════════════════════════════════════════════════════════════════════════════
# Carga de configuración
# ══════════════════════════════════════════════════════════════════════════════

CONFIG_PATH = Path(__file__).parent / "seniaeye.conf"


def load_config() -> configparser.ConfigParser:
    cfg = configparser.ConfigParser()
    if not CONFIG_PATH.exists():
        log.error("No se encuentra seniaeye.conf")
        raise FileNotFoundError(CONFIG_PATH)
    cfg.read(CONFIG_PATH)
    return cfg


# ══════════════════════════════════════════════════════════════════════════════
# Estado compartido del agente
# ══════════════════════════════════════════════════════════════════════════════

class AgentState:
    def __init__(self, cfg: configparser.ConfigParser):
        self.agent_name: str = cfg.get("agent", "name", fallback=socket.gethostname())
        self.allowed_ports: set[int] = {
            int(p.strip())
            for p in cfg.get("monitoring", "allowed_ports", fallback="53,80,443,853,22").split(",")
        }
        self.blacklist_domains: set[str] = {
            d.strip().lower()
            for d in cfg.get("monitoring", "blacklist_domains", fallback="").split(",")
            if d.strip()
        }
        self.doh_ips: set[str] = {
            ip.strip()
            for ip in cfg.get("monitoring", "doh_ips", fallback="").split(",")
            if ip.strip()
        }
        # IPs dinámicas resueltas de dominios en blacklist
        self.blacklist_ips: set[str] = set()
        # Interfaces conocidas al arranque
        self.known_interfaces: set[str] = set(psutil.net_if_addrs().keys())
        # Cola de eventos pendientes de envío
        self.event_queue: asyncio.Queue = asyncio.Queue()

    def resolve_blacklist_ips(self):
        """Resuelve las IPs de los dominios en la blacklist."""
        resolved: set[str] = set()
        for domain in self.blacklist_domains:
            try:
                infos = socket.getaddrinfo(domain, None)
                for info in infos:
                    resolved.add(info[4][0])
            except Exception:
                pass
        self.blacklist_ips = resolved
        log.info("IPs de blacklist resueltas: %d entradas", len(resolved))


# ══════════════════════════════════════════════════════════════════════════════
# Construcción de eventos
# ══════════════════════════════════════════════════════════════════════════════

def build_event(state: AgentState, event_type: str, severity: str, detail: dict) -> dict:
    return {
        "agent": state.agent_name,
        "timestamp": datetime.utcnow().isoformat(),
        "type": event_type,
        "severity": severity,  # "info" | "warning" | "alert"
        "detail": detail,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Monitor 1 – Puertos no autorizados (via psutil conexiones)
# ══════════════════════════════════════════════════════════════════════════════

async def monitor_ports(state: AgentState, interval: float = 5.0):
    reported: set[tuple] = set()   # (pid, raddr, rport) ya reportados
    log.info("Monitor de puertos iniciado (intervalo=%ss)", interval)
    while True:
        try:
            connections = psutil.net_connections(kind="inet")
            current: set[tuple] = set()
            for conn in connections:
                if conn.status != "ESTABLISHED":
                    continue
                if not conn.raddr:
                    continue
                rip, rport = conn.raddr
                pid = conn.pid
                key = (pid, rip, rport)
                current.add(key)
                if rport not in state.allowed_ports and key not in reported:
                    reported.add(key)
                    proc_name = ""
                    try:
                        proc_name = psutil.Process(pid).name() if pid else ""
                    except Exception:
                        pass
                    event = build_event(
                        state,
                        "unauthorized_port",
                        "alert",
                        {
                            "remote_ip": rip,
                            "remote_port": rport,
                            "pid": pid,
                            "process": proc_name,
                        },
                    )
                    log.warning("Puerto no autorizado: %s:%s (%s)", rip, rport, proc_name)
                    await state.event_queue.put(event)
            # Limpiar claves obsoletas
            reported &= current
        except Exception as exc:
            log.error("Error monitor_ports: %s", exc)
        await asyncio.sleep(interval)


# ══════════════════════════════════════════════════════════════════════════════
# Monitor 2 – DNS (via Scapy si disponible, o via psutil fallback)
# ══════════════════════════════════════════════════════════════════════════════

def _is_domain_blocked(domain: str, blacklist: set[str]) -> bool:
    domain = domain.rstrip(".").lower()
    if domain in blacklist:
        return True
    # Comprobar subdominios: www.chatgpt.com → chatgpt.com
    parts = domain.split(".")
    for i in range(1, len(parts)):
        parent = ".".join(parts[i:])
        if parent in blacklist:
            return True
    return False


if SCAPY_AVAILABLE:
    _dns_state_ref = None  # se asigna en monitor_dns

    def _dns_packet_callback(pkt):
        state = _dns_state_ref
        if state is None:
            return
        if pkt.haslayer(DNS) and pkt[DNS].qr == 0:  # query
            for i in range(pkt[DNS].qdcount):
                try:
                    qname = pkt[DNSQR][i].qname.decode().rstrip(".")
                except Exception:
                    continue
                if _is_domain_blocked(qname, state.blacklist_domains):
                    event = build_event(
                        state,
                        "blacklist_domain_dns",
                        "alert",
                        {"domain": qname, "method": "dns_query"},
                    )
                    log.warning("DNS bloqueado: %s", qname)
                    asyncio.get_event_loop().call_soon_threadsafe(
                        state.event_queue.put_nowait, event
                    )


async def monitor_dns_scapy(state: AgentState):
    global _dns_state_ref
    _dns_state_ref = state
    log.info("Monitor DNS (Scapy) iniciado")
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        lambda: sniff(
            filter="udp port 53 or tcp port 53",
            prn=_dns_packet_callback,
            store=False,
        ),
    )


async def monitor_dns_fallback(state: AgentState, interval: float = 3.0):
    """
    Fallback: inspecciona conexiones activas hacia puerto 53 y
    comparar IPs de destino contra blacklist_ips.
    """
    log.info("Monitor DNS (fallback psutil) iniciado")
    reported: set[str] = set()
    while True:
        try:
            connections = psutil.net_connections(kind="inet")
            for conn in connections:
                if not conn.raddr:
                    continue
                rip, rport = conn.raddr
                # Detectar intento de DoH (HTTPS a IP de DoH conocida)
                if rip in state.doh_ips and rport in (443, 853):
                    key = f"doh:{rip}"
                    if key not in reported:
                        reported.add(key)
                        event = build_event(
                            state,
                            "doh_detected",
                            "alert",
                            {"remote_ip": rip, "port": rport, "note": "DNS over HTTPS/TLS detectado"},
                        )
                        log.warning("DoH detectado → %s:%s", rip, rport)
                        await state.event_queue.put(event)
                # Detectar conexión a IP de blacklist
                if rip in state.blacklist_ips:
                    key = f"blip:{rip}"
                    if key not in reported:
                        reported.add(key)
                        event = build_event(
                            state,
                            "blacklist_ip",
                            "alert",
                            {"remote_ip": rip, "port": rport},
                        )
                        log.warning("IP de blacklist: %s", rip)
                        await state.event_queue.put(event)
        except Exception as exc:
            log.error("Error monitor_dns_fallback: %s", exc)
        await asyncio.sleep(interval)


# ══════════════════════════════════════════════════════════════════════════════
# Monitor 3 – IPs de destino vs blacklist_ips
# ══════════════════════════════════════════════════════════════════════════════

async def monitor_ips(state: AgentState, interval: float = 5.0):
    log.info("Monitor de IPs iniciado")
    reported: set[str] = set()
    while True:
        try:
            connections = psutil.net_connections(kind="inet")
            for conn in connections:
                if not conn.raddr:
                    continue
                rip = conn.raddr[0]
                if rip in state.blacklist_ips and rip not in reported:
                    reported.add(rip)
                    pid = conn.pid
                    proc = ""
                    try:
                        proc = psutil.Process(pid).name() if pid else ""
                    except Exception:
                        pass
                    event = build_event(
                        state,
                        "blacklist_ip_connection",
                        "alert",
                        {"remote_ip": rip, "port": conn.raddr[1], "pid": pid, "process": proc},
                    )
                    log.warning("Conexión a IP de blacklist: %s (%s)", rip, proc)
                    await state.event_queue.put(event)
        except Exception as exc:
            log.error("Error monitor_ips: %s", exc)
        await asyncio.sleep(interval)


# ══════════════════════════════════════════════════════════════════════════════
# Monitor 4 – Nuevas interfaces de red
# ══════════════════════════════════════════════════════════════════════════════

async def monitor_interfaces(state: AgentState, interval: float = 5.0):
    log.info("Monitor de interfaces iniciado. Conocidas: %s", state.known_interfaces)
    while True:
        await asyncio.sleep(interval)
        try:
            current = set(psutil.net_if_addrs().keys())
            new_ifaces = current - state.known_interfaces
            removed_ifaces = state.known_interfaces - current
            for iface in new_ifaces:
                event = build_event(
                    state,
                    "new_interface",
                    "alert",
                    {"interface": iface, "action": "connected"},
                )
                log.warning("Nueva interfaz detectada: %s", iface)
                await state.event_queue.put(event)
            for iface in removed_ifaces:
                event = build_event(
                    state,
                    "interface_removed",
                    "info",
                    {"interface": iface, "action": "disconnected"},
                )
                log.info("Interfaz desconectada: %s", iface)
                await state.event_queue.put(event)
            state.known_interfaces = current
        except Exception as exc:
            log.error("Error monitor_interfaces: %s", exc)


# ══════════════════════════════════════════════════════════════════════════════
# Heartbeat periódico con estado general
# ══════════════════════════════════════════════════════════════════════════════

async def heartbeat(state: AgentState, interval: float = 30.0):
    log.info("Heartbeat iniciado (cada %ss)", interval)
    while True:
        await asyncio.sleep(interval)
        try:
            cpu = psutil.cpu_percent(interval=1)
            mem = psutil.virtual_memory().percent
            event = build_event(
                state,
                "heartbeat",
                "info",
                {"cpu_percent": cpu, "mem_percent": mem},
            )
            await state.event_queue.put(event)
        except Exception as exc:
            log.error("Error heartbeat: %s", exc)


# ══════════════════════════════════════════════════════════════════════════════
# Conexión WebSocket con reconexión automática
# ══════════════════════════════════════════════════════════════════════════════

async def websocket_sender(state: AgentState, uri: str, reconnect_interval: int = 30):
    log.info("Iniciando conexión WebSocket → %s", uri)
    while True:
        try:
            async with websockets.connect(uri, ping_interval=20, ping_timeout=20) as ws:
                log.info("Conectado al servidor: %s", uri)
                # Enviar identificación inicial
                hello = {
                    "agent": state.agent_name,
                    "timestamp": datetime.utcnow().isoformat(),
                    "type": "hello",
                    "severity": "info",
                    "detail": {
                        "hostname": socket.gethostname(),
                        "os": platform.system(),
                        "os_version": platform.version(),
                        "python": platform.python_version(),
                    },
                }
                await ws.send(json.dumps(hello))
                # Bucle de envío de eventos
                while True:
                    event = await state.event_queue.get()
                    try:
                        await ws.send(json.dumps(event))
                        log.debug("Evento enviado: %s", event["type"])
                    except Exception as send_exc:
                        log.error("Error enviando evento: %s", send_exc)
                        await state.event_queue.put(event)   # reencolar
                        raise
        except (websockets.exceptions.WebSocketException, OSError, ConnectionRefusedError) as exc:
            log.warning("Sin conexión (%s). Reintentando en %ss…", exc, reconnect_interval)
            await asyncio.sleep(reconnect_interval)
        except Exception as exc:
            log.error("Error inesperado WebSocket: %s", exc)
            await asyncio.sleep(reconnect_interval)


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

async def main():
    cfg = load_config()

    server_host = cfg.get("server", "host", fallback="127.0.0.1")
    server_port = cfg.getint("server", "port", fallback=5000)
    reconnect_interval = cfg.getint("agent", "reconnect_interval", fallback=30)
    send_interval = cfg.getfloat("agent", "send_interval", fallback=5)

    uri = f"ws://{server_host}:{server_port}/ws"

    state = AgentState(cfg)

    # Resolver IPs de blacklist en segundo plano (no bloquear arranque)
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, state.resolve_blacklist_ips)

    tasks = [
        asyncio.create_task(websocket_sender(state, uri, reconnect_interval)),
        asyncio.create_task(monitor_ports(state, send_interval)),
        asyncio.create_task(monitor_interfaces(state, send_interval)),
        asyncio.create_task(monitor_ips(state, send_interval)),
        asyncio.create_task(heartbeat(state, 30)),
    ]

    if SCAPY_AVAILABLE:
        tasks.append(asyncio.create_task(monitor_dns_scapy(state)))
        log.info("Scapy disponible → monitor DNS con captura de paquetes activo")
    else:
        tasks.append(asyncio.create_task(monitor_dns_fallback(state, send_interval)))
        log.warning("Scapy no disponible → usando monitor DNS por fallback (psutil)")

    log.info("SeniaEye Agente arrancado para '%s'", state.agent_name)
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    if platform.system() != "Windows" and os.geteuid() != 0:
        log.warning("Ejecutar como root para captura completa de paquetes (Scapy).")
    asyncio.run(main())
