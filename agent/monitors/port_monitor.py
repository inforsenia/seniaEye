"""Port monitor - reports unallowed ports."""

import threading
from typing import Callable, Optional
from scapy.all import sniff, IP, TCP, UDP
from agent.utils.logger import get_logger

logger = get_logger(__name__)

class PortMonitor:
    """Monitors port traffic and reports unallowed ports."""
    
    def __init__(self, callback: Callable, interface: Optional[str] = None):
        self.callback = callback
        self.interface = interface
        self.thread: Optional[threading.Thread] = None
        self.running = False
    
    def _packet_callback(self, packet):
        try:
            if not packet.haslayer(IP):
                return
            
            dst_port = None
            if packet.haslayer(TCP):
                dst_port = packet[TCP].dport
            elif packet.haslayer(UDP):
                dst_port = packet[UDP].dport
            
            if dst_port:
                self.callback({"port": dst_port})
        except Exception as e:
            logger.error(f"Port monitor error: {e}")
    
    def start(self):
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        logger.info("PortMonitor started")
    
    def stop(self):
        self.running = False
        logger.info("PortMonitor stopped")
    
    def _run(self):
        try:
            sniff(
                prn=self._packet_callback,
                iface=self.interface,
                stop_filter=lambda x: not self.running,
                store=False
            )
        except Exception as e:
            logger.error(f"PortMonitor error: {e}")
            self.running = False

