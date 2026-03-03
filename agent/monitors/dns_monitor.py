import datetime
import threading
from scapy.all import sniff, DNSQR
from agent.events.models import Event
from agent.monitors.violations import ViolationChecker
from agent.utils.logger import get_logger

logger = get_logger(__name__)

class DNSMonitor:
    """Monitors DNS queries and reports violations."""
    
    def __init__(self, callback, violation_checker: ViolationChecker, machine_name: str = "unknown"):
        self.callback = callback
        self.violation_checker = violation_checker
        self.machine_name = machine_name
        self._thread = None
        self._stop_sniff = threading.Event()

    def _process_packet(self, packet):
        if packet.haslayer(DNSQR):
            qname = packet[DNSQR].qname.decode(errors="ignore")
            violation = self.violation_checker.check_dns(qname)
            if violation:
                logger.info(f"DNS violation detected: {qname} - {violation['description']}")
                evt = Event(
                    machine_name=self.machine_name,
                    event_type=violation["event_type"],
                    description=violation["description"],
                    timestamp=datetime.datetime.now().isoformat(),
                )
                try:
                    self.callback(evt)
                except Exception as e:
                    logger.error(f"DNS callback error: {e}")

    def start(self, iface: str | None = None):
        if self._thread and self._thread.is_alive():
            return

        def _sniff():
            sniff(
                filter="udp port 53",
                prn=self._process_packet,
                store=False,
                iface=iface,
                stop_filter=lambda x: self._stop_sniff.is_set(),
            )

        self._thread = threading.Thread(target=_sniff, daemon=True)
        self._thread.start()

    def stop(self):
        """Señala al hilo de captura para que termine."""
        self._stop_sniff.set()
        if self._thread:
            self._thread.join(timeout=1)
