import datetime
import threading
import pyudev
from agent.events.models import Event

class InterfaceMonitor:
    """Monitors network interface additions via udev."""
    
    def __init__(self, callback, machine_name: str = "unknown"):
        self.callback = callback
        self.machine_name = machine_name
        self.context = pyudev.Context()
        self.monitor = pyudev.Monitor.from_netlink(self.context)
        self.monitor.filter_by(subsystem="net")
        self.observer = pyudev.MonitorObserver(
            self.monitor, callback=self._udev_event, name="udev-mon"
        )

    def _udev_event(self, action, device):
        if action == "add":
            evt = Event(
                machine_name=self.machine_name,
                event_type="interface_added",
                description=f"Interface {device.sys_name} connected",
                timestamp=datetime.datetime.now().isoformat(),
            )
            try:
                self.callback(evt)
            except Exception:
                pass

    def start(self):
        """Start monitoring interfaces."""
        self.observer.start()

    def stop(self):
        """Detiene el observador si está en ejecución."""
        try:
            self.observer.stop()
        except Exception:
            pass
