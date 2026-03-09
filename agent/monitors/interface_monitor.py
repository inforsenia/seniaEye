import datetime
import threading
import pyudev
from agent.events.models import Event
from agent.utils.logger import get_logger

logger = get_logger(__name__)

class InterfaceMonitor:
    """Monitors network interface additions via udev, especially USB WiFi devices."""
    
    def __init__(self, callback, machine_name: str = "unknown"):
        self.callback = callback
        self.machine_name = machine_name
        self.observer = None
        try:
            self.context = pyudev.Context()
            self.monitor = pyudev.Monitor.from_netlink(self.context)
            self.monitor.filter_by(subsystem="net")
            self.observer = pyudev.MonitorObserver(
                self.monitor, callback=self._udev_event, name="udev-mon"
            )
            logger.info("[INTERFACE_MONITOR] Initialized successfully with pyudev")
        except Exception as e:
            logger.error(f"[INTERFACE_MONITOR] Failed to initialize pyudev: {e}")
            logger.warning("[INTERFACE_MONITOR] Will not monitor interfaces")

    def _udev_event(self, device):
        """Handle udev events for network interfaces."""
        try:
            action = device.action
            device_name = device.get('INTERFACE', device.sys_name)
            
            if action == "add":
                logger.info(f"[INTERFACE_MONITOR] Detected interface added: {device_name}")
                
                # Get device properties for logging
                driver = device.get('DRIVER', 'unknown')
                devpath = device.get('DEVPATH', '')
                logger.debug(f"[INTERFACE_MONITOR] Device: {device_name}, Driver: {driver}, Path: {devpath}")
                
                # Check if USB device (potential USB WiFi)
                parent = device.find_parent(subsystem='usb')
                is_usb = parent is not None
                
                description = f"[VIOLATION] Network interface detected: {device_name}"
                if is_usb:
                    description = f"[VIOLATION] USB Network Device detected: {device_name}"
                    logger.warning(f"[INTERFACE_MONITOR] USB interface added: {device_name}")
                
                evt = Event(
                    machine_name=self.machine_name,
                    event_type="interface_violation",
                    description=description,
                    timestamp=datetime.datetime.now().isoformat(),
                )
                try:
                    self.callback(evt)
                    logger.info(f"[INTERFACE_MONITOR] Event sent for interface: {device_name}")
                except Exception as e:
                    logger.error(f"[INTERFACE_MONITOR] Callback error: {e}")
                    
            elif action == "remove":
                logger.info(f"[INTERFACE_MONITOR] Interface removed: {device_name}")
                
        except Exception as e:
            logger.error(f"[INTERFACE_MONITOR] Error processing event: {e}")

    def start(self):
        """Start monitoring interfaces."""
        if self.observer:
            logger.info("[INTERFACE_MONITOR] Starting udev monitor observer")
            self.observer.start()
        else:
            logger.warning("[INTERFACE_MONITOR] Observer not initialized, cannot start")

    def stop(self):
        """Stop monitoring interfaces."""
        if self.observer:
            logger.info("[INTERFACE_MONITOR] Stopping udev monitor observer")
            try:
                self.observer.stop()
            except Exception as e:
                logger.error(f"[INTERFACE_MONITOR] Error stopping observer: {e}")
        else:
            logger.debug("[INTERFACE_MONITOR] Observer already stopped or not initialized")
