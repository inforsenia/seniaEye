"""Monitor manager orchestrates all monitors."""

from typing import Callable, Optional
import datetime
import threading
from agent.monitors.dns_monitor import DNSMonitor
from agent.monitors.ip_monitor import IPMonitor
from agent.monitors.port_monitor import PortMonitor
from agent.monitors.port_rules_monitor import PortRulesMonitor
from agent.monitors.interface_monitor import InterfaceMonitor
from agent.monitors.block_list_monitor import BlockListMonitor
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
                 interface: Optional[str] = None,
                 server_url: str = "http://localhost:8000"):
        
        self.event_callback = event_callback
        self.machine_name = machine_name
        self.interface = interface
        
        self.policy = MonitoringPolicy()
        
        # Initialize block list monitor first (needed by violation checker)
        self.block_list_monitor = BlockListMonitor(server_url=server_url)
        
        # Thread for syncing blocked IPs from block list monitor
        self._ip_sync_thread = None
        self._stop_sync = threading.Event()
        
        # Pass block list monitor to violation checker
        self.violation_checker = ViolationChecker(self.policy, self.block_list_monitor)
        
        # Initialize port rules monitor
        self.port_rules_monitor = PortRulesMonitor(server_url=server_url)
        
        self.dns_monitor = DNSMonitor(event_callback, self.violation_checker, machine_name)
        self.ip_monitor = IPMonitor(event_callback, self.violation_checker, machine_name, self.block_list_monitor)
        self.interface_monitor = InterfaceMonitor(event_callback, machine_name)
        self.port_monitor = PortMonitor(self._handle_port, interface, self.port_rules_monitor)
        
        #self.monitors = [("DNS", self.dns_monitor), ("IP", self.ip_monitor), 
        #                ("Port", self.port_monitor),
        #                ("BlockList", self.block_list_monitor), ("PortRules", self.port_rules_monitor)]
        self.monitors = [("DNS", self.dns_monitor), ("BlockList", self.block_list_monitor), ("IP", self.ip_monitor), ("Port", self.port_monitor), ("Interface", self.interface_monitor)]
        
        logger.info("MonitorManager initialized")
    
    def update_policy(self, policy: MonitoringPolicy):
        """Update monitoring policy from server."""
        self.policy = policy
        self.violation_checker.update_policy(policy)
    
    def _sync_blocked_ips(self):
        """Continuously sync blocked IPs from block list monitor."""
        while not self._stop_sync.is_set():
            try:
                # Get all blocked IPs from block list monitor
                blocked_ips = self.block_list_monitor.get_blocked_ips()
                
                if blocked_ips:
                    # Update policy blocked IPs
                    self.policy.blocked_ips = blocked_ips
                    # Also update violation checker's policy
                    self.violation_checker.policy.blocked_ips = blocked_ips
                    
                    logger.info(f"[IP_SYNC] Updated {len(blocked_ips)} blocked IPs from block list")
            except Exception as e:
                logger.error(f"[IP_SYNC] Error syncing blocked IPs: {e}")
            
            # Check every 10 seconds or when stop is signaled
            self._stop_sync.wait(timeout=10)
    
    def _handle_port(self, port_data: dict):
        """Handle captured port and check for violation."""
        try:
            port = port_data.get("port")
            destination = port_data.get("destination")
            is_allowed = port_data.get("allowed", True)
            reason = port_data.get("reason", "")
            
            if port:
                # If port rules indicate violation, create event
                if not is_allowed:
                    source = port_data.get("source", "unknown")
                    protocol = port_data.get("protocol", "tcp")
                    
                    evt = Event(
                        machine_name=self.machine_name,
                        event_type="port_violation",
                        description=f"Unauthorized port access: {protocol}/{port} from {source}. {reason}",
                        timestamp=datetime.datetime.now().isoformat(),
                        destination_ip=destination,
                    )
                    self.event_callback(evt)
                else:
                    # For allowed ports, still check with violation checker
                    violation = self.violation_checker.check_port(port, destination)
                    if violation:
                        evt = Event(
                            machine_name=self.machine_name,
                            event_type=violation["event_type"],
                            description=violation["description"],
                            timestamp=datetime.datetime.now().isoformat(),
                            destination_ip=destination,
                        )
                        self.event_callback(evt)
        except Exception as e:
            logger.error(f"Port handler error: {e}")
    
    def start(self):
        """Start all monitors."""
        # Log interface being used
        if self.interface:
            logger.info(f"[MONITORS] Using interface: {self.interface}")
        else:
            logger.warning("[MONITORS] No interface specified, scapy will use default")
        
        # Start IP sync thread
        self._stop_sync.clear()
        self._ip_sync_thread = threading.Thread(target=self._sync_blocked_ips, daemon=True)
        self._ip_sync_thread.start()
        logger.info("IP Sync thread started")
        
        for name, monitor in self.monitors:
            try:
                if hasattr(monitor, 'start'):
                    # Pass interface to monitors that support it (DNS, IP monitors)
                    if name in ["DNS", "IP"]:
                        monitor.start(iface=self.interface)
                    else:
                        monitor.start()
                    logger.info(f"{name}Monitor started")
            except Exception as e:
                logger.error(f"Failed to start {name}Monitor: {e}")
    
    def stop(self):
        """Stop all monitors."""
        # Stop IP sync thread
        self._stop_sync.set()
        if self._ip_sync_thread and self._ip_sync_thread.is_alive():
            self._ip_sync_thread.join(timeout=2)
        
        for name, monitor in self.monitors:
            try:
                if hasattr(monitor, 'stop'):
                    monitor.stop()
                    logger.info(f"{name}Monitor stopped")
            except Exception as e:
                logger.error(f"Failed to stop {name}Monitor: {e}")

