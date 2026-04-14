"""Port monitor - reports port traffic and violations."""

import threading
import time
from typing import Callable, Optional, Dict, Tuple
from scapy.all import sniff, IP, TCP, UDP
from agent.utils.logger import get_logger

logger = get_logger(__name__)

class PortMonitor:
    """Monitors port traffic and reports violations based on rules."""
    
    # Event deduplication: aggregate same flows within this window
    DEDUP_WINDOW = 10  # seconds - report same flow only once per window
    MIN_REPORT_INTERVAL = 10  # minimum seconds between same flow reports
    
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
        self.cleanup_thread: Optional[threading.Thread] = None
        self.running = False
        self._paused = False
        self._pause_lock = threading.Lock()
        
        # Deduplication cache
        self.event_cache: Dict[Tuple, Dict] = {}
        self.cache_lock = threading.Lock()
    
    def _get_event_key(self, src_ip: str, dst_ip: str, port: int, protocol: str) -> Tuple:
        """Get deduplication key for event."""
        return (src_ip, dst_ip, port, protocol)
    
    def _clean_cache(self):
        """Remove expired entries from cache."""
        now = time.time()
        with self.cache_lock:
            expired_keys = [
                key for key, data in self.event_cache.items()
                if now - data["last_seen"] > self.DEDUP_WINDOW
            ]
            for key in expired_keys:
                del self.event_cache[key]
    
    def _deduplicate_event(self, src_ip: str, dst_ip: str, port: int, protocol: str) -> bool:
        """
        Check if event is new and should be reported.
        
        Returns:
            True if this is a new event (first in window), False if duplicate
        """
        key = self._get_event_key(src_ip, dst_ip, port, protocol)
        now = time.time()
        
        with self.cache_lock:  # ATOMIC: Everything inside lock
            if key not in self.event_cache:
                # NEW EVENT - register it
                self.event_cache[key] = {
                    "count": 1,
                    "first_seen": now,
                    "last_seen": now
                }
                return True  # Report this event
            
            # Key EXISTS - check if still within window
            data = self.event_cache[key]
            time_since_last = now - data["last_seen"]
            
            if time_since_last < self.DEDUP_WINDOW:
                # Still within dedup window - this is a duplicate
                data["count"] += 1
                data["last_seen"] = now
                return False  # Do NOT report
            else:
                # Outside dedup window - treat as new attempt
                data["count"] = 1
                data["first_seen"] = now
                data["last_seen"] = now
                return True  # Report as new event
    
    def _packet_callback(self, packet):
        # Skip if paused
        with self._pause_lock:
            if self._paused:
                return
        
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
                
                # Deduplicate: only report first occurrence of each unique flow
                is_unique = self._deduplicate_event(src_ip, dst_ip, dst_port, protocol)
                
                if is_unique:
                    # Get current count and timestamps
                    key = self._get_event_key(src_ip, dst_ip, dst_port, protocol)
                    with self.cache_lock:
                        cached = self.event_cache[key]
                        count = cached["count"]
                        first_seen = cached["first_seen"]
                    
                    # Create event
                    event = {
                        "type": "port_violation" if not is_allowed else "port_event",
                        "port": dst_port,
                        "protocol": protocol,
                        "source": src_ip,
                        "destination": dst_ip,
                        "allowed": is_allowed,
                        "matched_rule": matched_rule,
                        "reason": reason,
                        "packet_count": count  # Number of packets for this flow
                    }
                    
                    self.callback(event)
                    
                    logger.info(f"[PORT] NEW: {protocol.upper()}/{dst_port} {src_ip}→{dst_ip} "
                               f"[REPORTED, total_in_flow: {count}]")
                else:
                    # Duplicate within dedup window - silently aggregated
                    key = self._get_event_key(src_ip, dst_ip, dst_port, protocol)
                    with self.cache_lock:
                        count = self.event_cache[key]["count"]
                    logger.debug(f"[PORT] DUP:  {protocol.upper()}/{dst_port} {src_ip}→{dst_ip} "
                                f"[SKIPPED, total_in_flow: {count}]")
        
        except Exception as e:
            logger.error(f"Port monitor error: {e}")
    
    def start(self):
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        
        # Start cache cleanup thread
        self.cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self.cleanup_thread.start()
        
        logger.info("[PORT_MONITOR] Started (with event deduplication)")
    
    def stop(self):
        self.running = False
        if hasattr(self, 'thread') and self.thread:
            self.thread.join(timeout=5)
        if hasattr(self, 'cleanup_thread') and self.cleanup_thread:
            self.cleanup_thread.join(timeout=5)
        logger.info("[PORT_MONITOR] Stopped")
    
    def pause(self):
        """Pause packet processing without stopping the monitor."""
        with self._pause_lock:
            self._paused = True
        logger.info("[PORT_MONITOR] Paused")
    
    def resume(self):
        """Resume packet processing."""
        with self._pause_lock:
            self._paused = False
        logger.info("[PORT_MONITOR] Resumed")
    
    def _cleanup_loop(self):
        """Periodically clean expired entries from cache."""
        while self.running:
            try:
                self._clean_cache()
                time.sleep(1)  # Clean every second
            except Exception as e:
                logger.error(f"[PORT_MONITOR] Cleanup error: {e}")
    
    def set_port_rules_monitor(self, port_rules_monitor):
        """Set the port rules monitor for rule checking."""
        self.port_rules_monitor = port_rules_monitor
    
    def get_cache_stats(self) -> Dict:
        """Get current cache statistics."""
        with self.cache_lock:
            return {
                "cached_flows": len(self.event_cache),
                "total_packets": sum(data["count"] for data in self.event_cache.values()),
                "dedup_window": self.DEDUP_WINDOW
            }
    
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

