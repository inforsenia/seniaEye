import asyncio
import json
import logging
from typing import List
from websockets import connect, WebSocketException
from websockets.exceptions import ConnectionClosed
from agent.events.models import Event
from agent.config import load_config

logger = logging.getLogger("ws_sender")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

# Comandos — deben coincidir con los definidos en el servidor
CMD_START = "START_MONITORING"
CMD_STOP  = "STOP_MONITORING"


class WSSender:
    def __init__(self):
        self.config       = load_config()
        self.server_url   = self.config.get("server_ws_url")
        self.retry_delay  = self.config.get("retry_delay", 30)
        self.event_queue: List[Event] = []

        # Estado interno del agente
        self._monitoring  = False   # True → monitorización activa
        self._ws          = None    # WebSocket activo

    # ── API pública ────────────────────────────────────────────────────────────

    def add_event(self, event: Event):
        """Añade un evento a la cola. Solo se enviará si la monitorización está activa."""
        if self._monitoring:
            self.event_queue.append(event)
        else:
            logger.debug(f"Evento ignorado (en espera): {event}")

    # ── Bucle principal ────────────────────────────────────────────────────────

    async def run(self):
        while True:
            try:
                async with connect(self.server_url) as ws:
                    self._ws = ws
                    logger.info(f"Conectado al servidor: {self.server_url}")
                    logger.info("Esperando orden de inicio desde el dashboard...")

                    # Lanzar lectura de comandos y envío de eventos en paralelo
                    await asyncio.gather(
                        self._receive_commands(ws),
                        self._send_loop(ws),
                    )

            except (ConnectionClosed, WebSocketException, OSError) as e:
                self._ws = None
                self._monitoring = False
                logger.warning(f"Conexión perdida: {e}")
                logger.info(f"Reintentando en {self.retry_delay}s...")
                await asyncio.sleep(self.retry_delay)

            except Exception as e:
                self._ws = None
                self._monitoring = False
                logger.error(f"Error inesperado: {e}")
                await asyncio.sleep(self.retry_delay)

    # ── Recepción de comandos del servidor ────────────────────────────────────

    async def _receive_commands(self, ws):
        async for raw in ws:
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning(f"Mensaje no JSON recibido: {raw}")
                continue

            command = msg.get("command")

            if command == CMD_START:
                if not self._monitoring:
                    self._monitoring = True
                    logger.info("▶ Monitorización INICIADA")
                    await self._ack(ws, CMD_START)
                    await self._on_start()
                else:
                    logger.debug("START recibido pero ya estaba monitorizando")

            elif command == CMD_STOP:
                if self._monitoring:
                    self._monitoring = False
                    logger.info("■ Monitorización DETENIDA")
                    await self._ack(ws, CMD_STOP)
                    await self._on_stop()
                else:
                    logger.debug("STOP recibido pero no estaba monitorizando")

            else:
                logger.warning(f"Comando desconocido: {command}")

    # ── Envío de eventos al servidor ──────────────────────────────────────────

    async def _send_loop(self, ws):
        """Vacía la cola de eventos mientras haya conexión."""
        while True:
            if self._monitoring and self.event_queue:
                await self._flush_queue(ws)
            await asyncio.sleep(0.5)

    async def _flush_queue(self, ws):
        pending = self.event_queue[:]
        for event in pending:
            try:
                await ws.send(event.json())
                self.event_queue.remove(event)
                logger.info(f"Evento enviado: {event}")
            except ConnectionClosed:
                logger.warning("Conexión cerrada al enviar. Reconectando...")
                raise
            except WebSocketException as e:
                logger.error(f"Error al enviar evento: {e}")
                break

    # ── Confirmación de comando ───────────────────────────────────────────────

    async def _ack(self, ws, command: str):
        try:
            await ws.send(json.dumps({"ack": command}))
        except Exception as e:
            logger.error(f"No se pudo enviar ACK: {e}")

    # ── Hooks de ciclo de vida ────────────────────────────────────────────────
    # Sobreescribe estos métodos en una subclase para ejecutar lógica propia
    # al iniciar o detener la monitorización.

    async def _on_start(self):
        """Se ejecuta cuando el agente recibe START. Sobreescribir si es necesario."""
        pass

    async def _on_stop(self):
        """Se ejecuta cuando el agente recibe STOP. Sobreescribir si es necesario."""
        pass
