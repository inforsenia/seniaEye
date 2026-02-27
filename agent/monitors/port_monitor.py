"""Port monitor - reports port traffic and violations."""

import threading
from typing import Callable, Optional
from scapy.all import sniff, IP, TCP, UDP
from agent.utils.logger import get_logger

logger = get_logger(__name__)

class PortMonitor:
    """Monitors port traffic and reports violations based on rules."""
    
    def __init__(self, callback: Callable, interface: Optional[str] = None, 
                 port_rules_monitor=None):
        """
        Initialize port monitor.
        
        Args:
            callback: Function to call with events
            interface: Network interface to monitor
            port_rules_monitor: Optional PortRulesMonitor instance for rule checking
        """
        self.callback = callback
        self.interface = interface
        self.port_rules_monitor = port_rules_monitor
        self.thread: Optional[threading.Thread] = None
        self.running = False
    
    def _packet_callback(self, packet):
        try:
            if not packet.haslayer(IP):
                return
            
            ip_layer = packet[IP]
            src_ip = ip_layer.src
            dst_ip = ip_layer.dst
            
            dst_port = None
            protocol = None
            
            if packet.haslayer(TCP):
                dst_port = packet[TCP].dport
                protocol = "tcp"
            elif packet.haslayer(UDP):
                dst_port = packet[UDP].dport
                protocol = "udp"
            
            if dst_port and protocol:
                # Check if port is allowed by rules
                is_allowed = True
                matched_rule = None
                reason = None
                
                if self.port_rules_monitor:
                    is_allowed = self.port_rules_monitor.is_port_allowed(
                        dst_port, src_ip, protocol
                    )
                    
                    if not is_allowed:
                        # Get the rule for logging
                        rule = self.port_rules_monitor.get_rule(dst_port)
                        matched_rule = rule
                        reason = f"Port {dst_port} not allowed from {src_ip}"
                
                # Create event
                event = {
                    "type": "port_violation" if not is_allowed else "port_event",
                    "port": dst_port,
                    "protocol": protocol,
                    "source": src_ip,
                    "destination": dst_ip,
                    "allowed": is_allowed,
                    "matched_rule": matched_rule,
                    "reason": reason
                }
                
                self.callback(event)
        
        except Exception as e:
            logger.error(f"Port monitor error: {e}")
    
    def start(self):
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        logger.info("[PORT_MONITOR] Started")
    
    def stop(self):
        self.running = False
        logger.info("[PORT_MONITOR] Stopped")
    
    def set_port_rules_monitor(self, port_rules_monitor):
        """Set the port rules monitor for rule checking."""
        self.port_rules_monitor = port_rules_monitor
    
    def _run(self):
        try:
            sniff(
                prn=self._packet_callback,
                iface=self.interface,
                stop_filter=lambda x: not self.running,
                store=False
            )
        except Exception as e:
            logger.error(f"[PORT_MONITOR] Error: {e}")
            self.running = False

