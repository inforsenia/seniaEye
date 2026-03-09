import datetime
import threading
import time
from scapy.all import sniff, IP
from agent.events.models import Event
from agent.monitors.violations import ViolationChecker
from agent.utils.logger import get_logger
from typing import Optional

logger = get_logger(__name__)

class IPMonitor:
    """Monitors IP traffic and reports violations."""
    
    # Deduplication window: only report same IP once per N seconds
    DEDUP_WINDOW_SECONDS = 60
    
    def __init__(self, callback, violation_checker: ViolationChecker, machine_name: str = "unknown", block_list_monitor=None):
        self.callback = callback
        self.violation_checker = violation_checker
        self.machine_name = machine_name
        self.block_list_monitor = block_list_monitor
        self._thread = None
        self._stop_sniff = threading.Event()
        self._packet_count = 0
        # Track recent violations: {ip: timestamp}
        self._recent_violations = {}
        self._dedup_lock = threading.Lock()

    def _get_domain_for_ip(self, ip: str) -> Optional[str]:
        """Find the domain(s) associated with an IP address."""
        if not self.block_list_monitor:
            return None
        
        try:
            block_list = self.block_list_monitor.get_block_list()
            for domain, ips in block_list.items():
                if ip in ips:
                    return domain
        except Exception as e:
            logger.debug(f"Error looking up domain for IP {ip}: {e}")
        
        return None

    def _should_report_violation(self, ip: str) -> bool:
        """
        Check if we should report a violation for this IP.
        Uses deduplication to avoid reporting same IP multiple times in short window.
        """
        current_time = time.time()
        
        with self._dedup_lock:
            last_report = self._recent_violations.get(ip)
            
            if last_report is None:
                # First time seeing this IP
                self._recent_violations[ip] = current_time
                return True
            
            time_since_last = current_time - last_report
            if time_since_last >= self.DEDUP_WINDOW_SECONDS:
                # Enough time has passed, allow new report
                self._recent_violations[ip] = current_time
                return True
            
            # Too soon, skip this violation
            return False

    def _process_packet(self, packet):
        if packet.haslayer(IP):
            dst = packet[IP].dst
            violation = self.violation_checker.check_ip(dst)
            if violation:
                # Check deduplication - only report once per minute per IP
                if not self._should_report_violation(dst):
                    return
                
                # Enhance description with domain information
                domain = self._get_domain_for_ip(dst)
                description = violation["description"]
                if domain:
                    description += f" (from domain: {domain})"
                
                evt = Event(
                    machine_name=self.machine_name,
                    event_type=violation["event_type"],
                    description=description,
                    timestamp=datetime.datetime.now().isoformat(),
                )
                try:
                    self.callback(evt)
                except Exception as e:
                    logger.error(f"IP callback error: {e}")

    def start(self, iface: str | None = None):
        if self._thread and self._thread.is_alive():
            return

        def _sniff():
            sniff(
                prn=self._process_packet,
                store=False,
                iface=iface,
                stop_filter=lambda x: self._stop_sniff.is_set(),
            )

        self._thread = threading.Thread(target=_sniff, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_sniff.set()
        if self._thread:
            self._thread.join(timeout=1)
        
        # Clear deduplication cache
        with self._dedup_lock:
            self._recent_violations.clear()
        logger.info("[IP_MONITOR] Deduplication cache cleared")
