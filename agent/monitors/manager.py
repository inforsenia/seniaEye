"""Monitor manager orchestrates all monitors."""

from typing import Callable, Optional
import datetime
from agent.monitors.dns_monitor import DNSMonitor
from agent.monitors.ip_monitor import IPMonitor
from agent.monitors.port_monitor import PortMonitor
from agent.monitors.interface_monitor import InterfaceMonitor
from agent.monitors.violations import ViolationChecker
from agent.config.models import MonitoringPolicy
from agent.events.models import Event
from agent.utils.logger import get_logger

logger = get_logger(__name__)

class MonitorManager:
    """Orchestrates all network monitors."""
    
    def __init__(self, 
                 event_callback: Callable,
                 machine_name: str,
                 interface: Optional[str] = None):
        
        self.event_callback = event_callback
        self.machine_name = machine_name
        self.interface = interface
        
        self.policy = MonitoringPolicy()
        self.violation_checker = ViolationChecker(self.policy)
        
        self.dns_monitor = DNSMonitor(event_callback, self.violation_checker, machine_name)
        self.ip_monitor = IPMonitor(event_callback, self.violation_checker, machine_name)
        self.port_monitor = PortMonitor(self._handle_port, interface)
        self.interface_monitor = InterfaceMonitor(event_callback, machine_name)
        
        self.monitors = [("DNS", self.dns_monitor), ("IP", self.ip_monitor), 
                        ("Port", self.port_monitor), ("Interface", self.interface_monitor)]
        logger.info("MonitorManager initialized")
    
    def update_policy(self, policy: MonitoringPolicy):
        """Update monitoring policy from server."""
        self.policy = policy
        self.violation_checker.update_policy(policy)
    
    def _handle_port(self, port_data: dict):
        """Handle captured port and check for violation."""
        try:
            port = port_data.get("port")
            if port:
                violation = self.violation_checker.check_port(port)
                if violation:
                    evt = Event(
                        machine_name=self.machine_name,
                        event_type=violation["event_type"],
                        description=violation["description"],
                        timestamp=datetime.datetime.now().isoformat(),
                    )
                    self.event_callback(evt)
        except Exception as e:
            logger.error(f"Port handler error: {e}")
    
    def start(self):
        """Start all monitors."""
        for name, monitor in self.monitors:
            try:
                if hasattr(monitor, 'start'):
                    monitor.start()
                    logger.info(f"{name}Monitor started")
            except Exception as e:
                logger.error(f"Failed to start {name}Monitor: {e}")
    
    def stop(self):
        """Stop all monitors."""
        for name, monitor in self.monitors:
            try:
                if hasattr(monitor, 'stop'):
                    monitor.stop()
                    logger.info(f"{name}Monitor stopped")
            except Exception as e:
                logger.error(f"Failed to stop {name}Monitor: {e}")

