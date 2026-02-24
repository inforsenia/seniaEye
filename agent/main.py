"""
Este fichero es el punto de entrada principal del agente de monitorización que se ejecuta
en cada equipo del aula.

Funciones y comportamiento principal:

- Inicializa la instancia de WSSender, que se encarga de la comunicación con el servidor
  central mediante WebSockets.

- Lanza el bucle de envío de eventos en segundo plano, manteniendo la conexión activa y
  retransmitiendo eventos pendientes si fuese necesario.

- Simula o recibe eventos generados por los distintos monitores (puertos, DNS, IPs, interfaces)
  y los agrega a la cola del WSSender para su envío al servidor.

- Contiene un bucle principal que, en este ejemplo de prueba, genera eventos de forma periódica
  (cada 5 segundos) para demostrar la transmisión de datos.

En resumen:
Este fichero orquesta la operación del agente, asegurando que los eventos del equipo se
recopilen y envíen de forma continua y confiable al servidor central.
"""

import asyncio
from agent.sender.ws_sender import WSSender
from agent.events.models import Event
import datetime

async def main():
    sender = WSSender()

    # Lanzar el envío de eventos en background
    asyncio.create_task(sender.run())

    # Simulación de eventos
    while True:
        event = Event(
            machine_name="PC-Aula-1",
            event_type="port_violation",
            description="Intento de acceso a puerto no permitido",
            timestamp=datetime.datetime.now().isoformat()
        )
        sender.add_event(event)
        await asyncio.sleep(5)  # Cada 5s generar un evento de prueba

if __name__ == "__main__":
    asyncio.run(main())