import datetime
import threading

from scapy.all import sniff, IP  # capture any IP packet

from agent.events.models import Event


class IPMonitor:
    """Monitoriza tráfico IP y genera eventos con las IPs de destino.

    Implementación basada en scapy similar al monitor DNS.
    """

    def __init__(self, callback, machine_name: str = "unknown"):
        self.callback = callback
        self.machine_name = machine_name
        self._thread = None
        self._stop_sniff = threading.Event()

    def _process_packet(self, packet):
        if packet.haslayer(IP):
            dst = packet[IP].dst
            evt = Event(
                machine_name=self.machine_name,
                event_type="ip_destination",
                description=dst,
                timestamp=datetime.datetime.now().isoformat(),
            )
            try:
                self.callback(evt)
            except Exception:
                pass

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
