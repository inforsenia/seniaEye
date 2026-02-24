import asyncio
import json
import logging
from pathlib import Path
from typing import List
import os
from websockets import connect, WebSocketException
from websockets.exceptions import ConnectionClosed

from agent.events.models import Event  # tu modelo de evento Pydantic
from agent.config import load_config

logger = logging.getLogger("ws_sender")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

class WSSender:
    def __init__(self):
        self.config = load_config()  # Devuelve dict con 'server_url', etc.
        self.server_url = self.config.get("server_ws_url")
        self.retry_delay = self.config.get("retry_delay", 30)
        self.event_queue: List[Event] = []
    """
    async def send_event(self, ws, event: Event):
        try:
            data = event.json()
            await ws.send(data)
            logger.info(f"Evento enviado: {event}")
        except WebSocketException as e:
            logger.error(f"Error al enviar evento: {e}")
            self.event_queue.append(event)  # Reintentar más tarde
    """
    async def flush_queue(self, ws):
        """Enviar eventos pendientes"""
        if not self.event_queue:
            return
        logger.info(f"Reintentando {len(self.event_queue)} eventos pendientes")
        for event in self.event_queue[:]:
            try:
                await ws.send(event.json())
                self.event_queue.remove(event)
                logger.info(f"Evento pendiente enviado: {event}")
            except ConnectionClosed:
                logger.warning("Conexión cerrada. Forzando reconexión...")
                raise  # IMPORTANTE → salir hacia run()
            except WebSocketException as e:
                logger.error(f"No se pudo enviar evento pendiente: {e}")
                break  # Salir y reintentar luego

    async def run(self):
        while True:
            try:
                async with connect(self.server_url) as ws:
                    logger.info(f"Conectado al servidor WebSocket {self.server_url}")

                    # Loop para enviar eventos a medida que se agregan a la cola
                    while True:
                        if self.event_queue:
                            await self.flush_queue(ws)
                        await asyncio.sleep(1)

            except Exception as e:
                logger.warning(f"No se pudo conectar al servidor: {e}")
                logger.info(f"Reintentando en {self.retry_delay} segundos...")
                await asyncio.sleep(self.retry_delay)

    def add_event(self, event: Event):
        """Agregar evento a la cola para enviar"""
        self.event_queue.append(event)


"""
Este módulo implementa la comunicación del agente con el servidor central mediante WebSockets.

Clases y Funciones Principales:

- WSSender:
    - Encargado de enviar los eventos generados por el agente al servidor en tiempo real.
    - Mantiene una cola de eventos pendientes para asegurar que no se pierdan datos si el servidor
      no está disponible en el momento.
    - Gestiona la reconexión automática en caso de fallo de conexión, intentando reconectar
      cada cierto intervalo (configurable).

- send_event(ws, event):
    - Envía un evento individual al servidor a través de la conexión WebSocket.
    - Si el envío falla, el evento se guarda en la cola para reintentos posteriores.

- flush_queue(ws):
    - Revisa la cola de eventos pendientes y los envía al servidor.
    - Permite asegurar que los eventos que no pudieron enviarse previamente se transmitan
      cuando la conexión esté disponible.

- run():
    - Bucle principal que mantiene la conexión WebSocket con el servidor.
    - Reintenta la conexión automáticamente en caso de fallo.
    - Envía los eventos nuevos o pendientes al servidor de manera continua.

- add_event(event):
    - Permite agregar eventos a la cola desde otras partes del agente.
    - Los eventos agregados se enviarán inmediatamente si la conexión está activa, o se
      guardarán para su envío posterior en caso de desconexión.

En resumen:
Este fichero gestiona de forma confiable la transmisión de eventos desde cada equipo del aula
hacia el servidor central, asegurando que los datos se envíen en tiempo real y que los eventos
no se pierdan aunque haya problemas temporales de conectividad.
"""

