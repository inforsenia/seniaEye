"""Port monitor - Monitors port traffic based on specific rules."""

import threading
import time
from typing import Callable, Optional, Dict, Tuple, Set
from scapy.all import sniff, IP, TCP, UDP
from agent.utils.logger import get_logger
from agent.utils.local_network import is_external_ip, get_local_ips

logger = get_logger(__name__)


class PortMonitor:
    """
    Monitors port traffic and reports events based on specific rules:
    1. Port 853 (TCP/UDP) - DNS over TLS/DTLS
    2. Port 443 (TCP/UDP) to DoH servers in database
    3. All ports when connection is ESTABLISHED to external IPs only
    """
    
    DEDUP_WINDOW = 10  # seconds - avoid duplicate reports
    
    def __init__(self, callback: Callable, interface: Optional[str] = None, 
                 port_rules_monitor=None):
        """
        Initialize port monitor.
        
        Args:
            callback: Function to call with events
            interface: Network interface to monitor
            port_rules_monitor: Optional monitor for port rules (includes DoH IPs)
        """
        self.callback = callback
        self.interface = interface
        self.port_rules_monitor = port_rules_monitor  # Contains DoH server IPs
        self.thread: Optional[threading.Thread] = None
        self.cleanup_thread: Optional[threading.Thread] = None
        self.running = False
        
        # Deduplication cache: {(src_ip, dst_ip, port, protocol): {data...}}
        self.event_cache: Dict[Tuple, Dict] = {}
        self.cache_lock = threading.Lock()
        
        # TCP connection tracking: {(src_ip, dst_ip, dst_port): True} for established
        self.tcp_connections: Dict[Tuple, bool] = {}
        self.tcp_lock = threading.Lock()
        
        # Local IPs cache (refreshed periodically)
        self.local_ips: Set[str] = set()
        self._refresh_local_ips()
    
    def _refresh_local_ips(self):
        """Refresh local IP addresses."""
        self.local_ips = get_local_ips()
        logger.debug(f"[PORT] Local IPs: {self.local_ips}")
    
    def _get_doh_servers(self) -> Set[str]:
        """
        Get set of DoH server IPs from port rules monitor.
        
        Returns:
            Set of IP addresses that are DNS DoH servers
        """
        if not self.port_rules_monitor:
            return set()
        
        try:
            # port_rules_monitor should have access to DoH IPs
            # This will be implemented via an extended PortRulesMonitor
            doh_ips = self.port_rules_monitor.get_doh_servers()
            return set(doh_ips) if doh_ips else set()
        except Exception as e:
            logger.warning(f"[PORT] Could not get DoH servers: {e}")
            return set()
    
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
        
        with self.cache_lock:
            if key not in self.event_cache:
                self.event_cache[key] = {
                    "count": 1,
                    "first_seen": now,
                    "last_seen": now
                }
                return True
            
            data = self.event_cache[key]
            time_since_last = now - data["last_seen"]
            
            if time_since_last < self.DEDUP_WINDOW:
                data["count"] += 1
                data["last_seen"] = now
                return False
            else:
                data["count"] = 1
                data["first_seen"] = now
                data["last_seen"] = now
                return True
    
    def _track_tcp_connection(self, src_ip: str, dst_ip: str, dst_port: int, 
                             flags: int) -> bool:
        """
        Track TCP connection state and determine if connection is established.
        
        Args:
            src_ip: Source IP
            dst_ip: Destination IP
            dst_port: Destination port
            flags: TCP flags bits
        
        Returns:
            True if connection is (or becomes) established, False otherwise
        """
        key = (src_ip, dst_ip, dst_port)
        
        # TCP Flags
        SYN = 0x02
        SYN_ACK = 0x12  # SYN + ACK
        ACK = 0x10
        FIN = 0x01
        RST = 0x04
        
        with self.tcp_lock:
            if RST in flags or FIN in flags:
                # Connection closed/reset
                self.tcp_connections.pop(key, None)
                return False
            
            if (flags & (SYN | ACK)) == (SYN | ACK):
                # SYN-ACK: connection is being established
                self.tcp_connections[key] = True
                return True
            
            if (flags & ACK) and not (flags & SYN):
                # Pure ACK: likely data transmission (connection established)
                if self.tcp_connections.get(key):
                    return True
                else:
                    # ACK without prior SYN-ACK (could be external to our capture)
                    self.tcp_connections[key] = True
                    return True
            
            return False
    
    def _should_report_event(self, src_ip: str, dst_ip: str, dst_port: int, 
                            protocol: str, flags: Optional[int] = None) -> bool:
        """
        Determine if an event should be reported based on port rules.
        
        Rules:
        1. Port 853 (TCP/UDP) → always report
        2. Port 443 (TCP/UDP) to DoH servers → report
        3. Other ports with external dst_ip → report only if connection established
        
        Returns:
            True if event should be reported, False otherwise
        """
        # Rule 1: Always report port 853
        if dst_port == 853:
            logger.debug(f"[PORT] Rule 1 match: port 853 ({protocol})")
            return True
        
        # Rule 2: Port 443 to DoH servers
        if dst_port == 443:
            doh_servers = self._get_doh_servers()
            if dst_ip in doh_servers:
                logger.debug(f"[PORT] Rule 2 match: port 443 to DoH server {dst_ip}")
                return True
        
        # Rule 3: Other ports with external destination
        if is_external_ip(dst_ip):
            # For TCP, check if connection is established
            if protocol == "tcp":
                if flags is not None and self._track_tcp_connection(src_ip, dst_ip, dst_port, flags):
                    logger.debug(f"[PORT] Rule 3 match: TCP/{dst_port} to external {dst_ip} (established)")
                    return True
                else:
                    logger.debug(f"[PORT] Rule 3 skip: TCP/{dst_port} to external {dst_ip} (not established)")
                    return False
            elif protocol == "udp":
                # For UDP, we can't reliably detect connection establishment
                # Report first packet to external IP as best effort
                logger.debug(f"[PORT] Rule 3 match: UDP/{dst_port} to external {dst_ip}")
                return True
        
        return False
    
    def _packet_callback(self, packet):
        try:
            if not packet.haslayer(IP):
                return
            
            ip_layer = packet[IP]
            src_ip = ip_layer.src
            dst_ip = ip_layer.dst
            
            dst_port = None
            protocol = None
            flags = None
            
            if packet.haslayer(TCP):
                dst_port = packet[TCP].dport
                protocol = "tcp"
                flags = packet[TCP].flags
            elif packet.haslayer(UDP):
                dst_port = packet[UDP].dport
                protocol = "udp"
            
            if not dst_port or not protocol:
                return
            
            # Check if event should be reported
            if not self._should_report_event(src_ip, dst_ip, dst_port, protocol, flags):
                return
            
            # Deduplicate
            is_unique = self._deduplicate_event(src_ip, dst_ip, dst_port, protocol)
            
            if is_unique:
                key = self._get_event_key(src_ip, dst_ip, dst_port, protocol)
                with self.cache_lock:
                    cached = self.event_cache[key]
                    count = cached["count"]
                
                # Create event
                event = {
                    "type": "port_event",
                    "port": dst_port,
                    "protocol": protocol,
                    "source": src_ip,
                    "destination": dst_ip,
                    "is_external": is_external_ip(dst_ip),
                    "packet_count": count
                }
                
                self.callback(event)
                
                logger.info(f"[PORT] NEW: {protocol.upper()}/{dst_port} {src_ip}→{dst_ip} "
                           f"(external={event['is_external']}) [REPORTED]")
            else:
                key = self._get_event_key(src_ip, dst_ip, dst_port, protocol)
                with self.cache_lock:
                    count = self.event_cache[key]["count"]
                logger.debug(f"[PORT] DUP:  {protocol.upper()}/{dst_port} {src_ip}→{dst_ip} "
                            f"[SKIPPED, total_in_flow: {count}]")
        
        except Exception as e:
            logger.error(f"[PORT] Packet callback error: {e}")
    
    def _run(self):
        """Main sniffing loop."""
        try:
            logger.info(f"[PORT_MONITOR] Sniffing on interface: {self.interface or 'default'}")
            sniff(
                prn=self._packet_callback,
                iface=self.interface,
                store=False,
                stop_filter=lambda x: not self.running
            )
        except Exception as e:
            logger.error(f"[PORT_MONITOR] Sniff error: {e}")
        finally:
            logger.info("[PORT_MONITOR] Sniffer stopped")
    
    def start(self):
        """Start the port monitor."""
        if self.running:
            return
        
        self.running = True
        self._refresh_local_ips()
        
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        
        self.cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self.cleanup_thread.start()
        
        logger.info("[PORT_MONITOR] Started with new filtering rules")
    
    def stop(self):
        """Stop the port monitor."""
        self.running = False
        if hasattr(self, 'thread') and self.thread:
            self.thread.join(timeout=5)
        if hasattr(self, 'cleanup_thread') and self.cleanup_thread:
            self.cleanup_thread.join(timeout=5)
        logger.info("[PORT_MONITOR] Stopped")
    
    def _cleanup_loop(self):
        """Periodically clean expired entries and refresh local IPs."""
        while self.running:
            try:
                self._clean_cache()
                # Refresh local IPs every 30 seconds
                time.sleep(1)
            except Exception as e:
                logger.error(f"[PORT_MONITOR] Cleanup error: {e}")
    
    def set_port_rules_monitor(self, port_rules_monitor):
        """Set the port rules monitor (contains DoH servers)."""
        self.port_rules_monitor = port_rules_monitor
    
    def get_cache_stats(self) -> Dict:
        """Get deduplication cache statistics."""
        with self.cache_lock:
            return {
                "cached_flows": len(self.event_cache),
                "total_packets": sum(data["count"] for data in self.event_cache.values())
            }

