import datetime
import threading
from scapy.all import sniff, IP
from agent.events.models import Event
from agent.monitors.violations import ViolationChecker
from agent.utils.logger import get_logger

logger = get_logger(__name__)

class IPMonitor:
    """Monitors IP traffic and reports violations."""
    
    def __init__(self, callback, violation_checker: ViolationChecker, machine_name: str = "unknown"):
        self.callback = callback
        self.violation_checker = violation_checker
        self.machine_name = machine_name
        self._thread = None
        self._stop_sniff = threading.Event()

    def _process_packet(self, packet):
        if packet.haslayer(IP):
            dst = packet[IP].dst
            violation = self.violation_checker.check_ip(dst)
            if violation:
                evt = Event(
                    machine_name=self.machine_name,
                    event_type=violation["event_type"],
                    description=violation["description"],
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
