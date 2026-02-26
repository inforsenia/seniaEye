import datetime
import threading

import pyudev

from agent.events.models import Event


class InterfaceMonitor:
    """Monitoriza eventos de udev relacionados con interfaces de red.

    Usa la librería ``pyudev`` para escuchar acciones sobre el subsystem
    ``net`` y emitir una instancia de ``Event`` cada vez que se añade
    una nueva interfaz.

    El constructor recibe un callback que se llamará con el objeto Event.
    Esto permite que el monitor sea fácilmente reutilizable desde el
    agente principal o cualquier otro componente.
    """

    def __init__(self, callback, machine_name: str = "unknown"):
        self.callback = callback
        self.machine_name = machine_name
        self.context = pyudev.Context()
        self.monitor = pyudev.Monitor.from_netlink(self.context)
        self.monitor.filter_by(subsystem="net")
        # ``MonitorObserver`` crea un hilo interno para escuchar eventos.
        self.observer = pyudev.MonitorObserver(
            self.monitor, callback=self._udev_event, name="udev-mon"
        )

    def _udev_event(self, action, device):
        if action == "add":
            evt = Event(
                machine_name=self.machine_name,
                event_type="interface_added",
                description=f"Nueva interfaz {device.sys_name} conectada",
                timestamp=datetime.datetime.now().isoformat(),
            )
            # llamar al callback en el hilo apropiado
            try:
                self.callback(evt)
            except Exception:
                # no dejamos que un fallo en el callback detenga el observer
                pass

    def start(self):
        """Arranca el observador de udev en un hilo separado."""
        self.observer.start()

    def stop(self):
        """Detiene el observador si está en ejecución."""
        try:
            self.observer.stop()
        except Exception:
            pass
