import datetime
import threading
from scapy.all import sniff, DNSQR, DNSRR, DNS
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
                # Extraer la IP resuelta de la respuesta DNS
                resolved_ips = []
                if packet.haslayer(DNS) and packet[DNS].an:
                    dns_layer = packet[DNS]
                    # Recorrer los registros de respuesta (answer section)
                    answer = dns_layer.an
                    while answer:
                        if hasattr(answer, 'rdata'):
                            # Registros A (IPv4) y AAAA (IPv6)
                            resolved_ips.append(str(answer.rdata))
                        answer = answer.payload if hasattr(answer, 'payload') else None
                
                # Only report violations if we got resolved IPs
                if resolved_ips:
                    ip_info = f" -> Resolved IPs: {', '.join(resolved_ips)}"
                    logger.info(f"DNS violation detected: {qname} - {violation['description']}{ip_info}")
                    evt = Event(
                        machine_name=self.machine_name,
                        event_type=violation["event_type"],
                        description=f"{violation['description']} (Resolved to: {', '.join(resolved_ips)})",
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
