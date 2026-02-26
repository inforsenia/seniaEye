import datetime
import threading

from scapy.all import sniff, DNSQR  # scapy is required, add to requirements

from agent.events.models import Event


class DNSMonitor:
    """Monitoriza consultas DNS mediante captura de paquetes con scapy.

    - Inicia un hilo independiente que usa ``scapy.sniff`` para capturar
      paquetes UDP en el puerto 53.
    - Cada vez que se detecta una consulta (DNSQR), genera un ``Event``.

    El callback se debe ajustar al mismo que usa el agente principal para
    encolar eventos (por ejemplo ``sender.add_event``).
    """

    def __init__(self, callback, machine_name: str = "unknown"):
        self.callback = callback
        self.machine_name = machine_name
        self._thread = None
        self._stop_sniff = threading.Event()

    def _process_packet(self, packet):
        if packet.haslayer(DNSQR):
            qname = packet[DNSQR].qname.decode(errors="ignore")
            evt = Event(
                machine_name=self.machine_name,
                event_type="dns_query",
                description=qname,
                timestamp=datetime.datetime.now().isoformat(),
            )
            try:
                self.callback(evt)
            except Exception:
                pass

    def start(self, iface: str | None = None):
        """Arranca la captura en un hilo demonio.

        ``iface`` puede usarse para especificar una interfaz concreta.
        """
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
