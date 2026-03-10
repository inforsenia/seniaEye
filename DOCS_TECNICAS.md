# Documentación Técnica - Reestructuración de Monitorización de Puertos

## Arquitectura General

```
┌─────────────────────── Client Agent ───────────────────────┐
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              MonitorManager (manager.py)              │  │
│  │  Orquesta y gestiona todos los monitores             │  │
│  └──────────────────────────────────────────────────────┘  │
│           ↓                   │                    ↓        │
│    ┌────────────┐        ┌────────────┐     ┌──────────┐   │
│    │ PortRules  │        │ PortMonitor│     │ Others   │   │
│    │ Monitor    │────────│  (NEW!)    │     │ monitors │   │
│    └────────────┘        └────────────┘     └──────────┘   │
│         ↓                      ↓                            │
│   Sinc. DoH Servers    Captura TCP/UDP                     │
│   Sync port rules      Filtra por reglas                   │
│                                                             │
└──────────────┬──────────────────────────────────────────────┘
               │ WebSocket eventos
               ↓
┌─────────────────────── Servidor ──────────────────────────┐
│                                                            │
│  ┌──────────────────────────────────────────────────────┐ │
│  │              server/main.py (FastAPI)                 │ │
│  │  - Recibe eventos de agents                          │ │
│  │  - Maneja APIs REST                                  │ │
│  │  - Sirve Dashboard                                   │ │
│  └──────────────────────────────────────────────────────┘ │
│           ↓                    │              ↓            │
│   ┌────────────────┐     ┌───────────┐ ┌──────────────┐   │
│   │    Database    │     │ DNS DoH   │ │  Port Rules  │   │
│   │   (SQLite)     │     │   CRUD    │ │     API      │   │
│   └────────────────┘     └───────────┘ └──────────────┘   │
│      - Sessions                                            │
│      - Events                                              │
│      - dns_doh_servers  ← NEW TABLE                        │
│      - blocked_domains                                     │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

## Flujo de Funcionamiento

### 1. Inicialización

```python
# agent/main.py
MonitorManager.__init__()
  ├─ PortRulesMonitor (server_url)  # Nueva instancia
  ├─ PortMonitor (port_rules_monitor)  # Referencia a PortRulesMonitor
  └─ ... otros monitores

MonitorManager.start()
  ├─ PortRulesMonitor.start()
  │   ├─ Hilo: sync_rules()  (cada 10 min)
  │   ├─ Hilo: sync_doh_servers()  (cada 10 min)  ← NEW
  │   └─ Sincronización inmediata al iniciar
  │
  ├─ PortMonitor.start()
  │   ├─ Hilo: sniff(packets)  (captura en tiempo real)
  │   └─ Hilo: _cleanup_loop()  (deduplicación)
  │
  └─ ... otros monitores
```

### 2. Captura y Filtrado de Paquetes

```
Cada paquete TCP/UDP →
  ↓
PortMonitor._packet_callback()
  ├─ Extraer: src_ip, dst_ip, dst_port, protocol, flags
  ├─ Llamar: _should_report_event()
  │   ├─ Regla 1: puerto == 853 ? → YES
  │   ├─ Regla 2: puerto == 443 AND dst_ip in DoH_servers ? → YES
  │   └─ Regla 3: 
  │       └─ is_external_ip(dst_ip) ?
  │           ├─ TCP: _track_tcp_connection() → établished ?
  │           └─ UDP: siempre YES
  │
  ├─ Si sí → _deduplicate_event()
  │   ├─ En cache? Y dentro ventana?
  │   │   ├─ Sí → return False (duplicado)
  │   │   └─ No → Agregar cache, return True
  │   │
  │   └─ Si True → callback(event)
  │
  └─ Evento generado con timestamp
```

### 3. Detección de IPs Locales

```python
# agent/utils/local_network.py
get_local_ips() → Set[str]
  ├─ socket.gethostname()
  ├─ socket.getaddrinfo(hostname, None)
  ├─ Agregar loopback (127.0.0.1, ::1)
  └─ Retorna set de IPs

is_local_ip(ip: str) → bool
  ├─ ipaddress.ip_address(ip)
  ├─ .is_loopback ?
  ├─ ip in get_local_ips() ?
  └─ Retorna bool

is_external_ip(ip: str) → bool
  └─ return not is_local_ip(ip)
```

### 4. Rastreo de Conexiones TCP

```python
def _track_tcp_connection(src_ip, dst_ip, dst_port, flags):
    key = (src_ip, dst_ip, dst_port)
    
    # Flags TCP
    # 0x02 = SYN
    # 0x12 = SYN-ACK
    # 0x10 = ACK
    # 0x01 = FIN
    # 0x04 = RST
    
    if RST | FIN:
        connections.pop(key, None)
        return False
    
    if (flags & SYN | ACK) == (SYN | ACK):
        # SYN-ACK recibido → servidor respondió → ESTABLECIDA
        connections[key] = True
        return True
    
    if (flags & ACK) and not (flags & SYN):
        # ACK puro → datos o confirmación
        # Marcar como establecida y reportar
        connections[key] = True
        return True
    
    return False  # Aún no establecida
```

## Base de Datos

### Tabla: dns_doh_servers

```sql
CREATE TABLE dns_doh_servers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ip_address  TEXT    NOT NULL UNIQUE,
    hostname    TEXT,
    description TEXT,
    created_at  TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL
);

CREATE INDEX idx_dns_doh_servers_ip ON dns_doh_servers(ip_address);
```

### CRUD Functions (database.py)

```python
# Lectura
get_dns_doh_ips() → List[str]
  # SELECT ip_address FROM dns_doh_servers
  
list_dns_doh_servers() → List[dict]
  # SELECT * FROM dns_doh_servers
  
dns_doh_server_exists(ip_address) → bool

# Escritura
add_dns_doh_server(ip, hostname, description) → bool

update_dns_doh_server(ip, hostname, description) → bool

remove_dns_doh_server(ip_address) → bool

clear_all_dns_doh_servers() → int
```

## API Endpoints

### GET /api/dns-doh/list
**Descripción**: Listar todos los servidores DoH
**Response**:
```json
{
  "timestamp": "2026-03-10 14:30:45",
  "servers": [
    {
      "id": 1,
      "ip_address": "1.1.1.1",
      "hostname": "cloudflare",
      "description": "Cloudflare DoH",
      "created_at": "2026-03-10 14:30:00",
      "updated_at": "2026-03-10 14:30:00"
    }
  ],
  "total": 1
}
```

### POST /api/dns-doh/add
**Parámetros**: `ip_address` (req), `hostname` (opt), `description` (opt)
**Response**: Confirmación + datos

### PUT /api/dns-doh/{ip_address}
**Parámetros**: `hostname` (opt), `description` (opt)
**Response**: Confirmación + datos actualizados

### DELETE /api/dns-doh/{ip_address}
**Response**: Confirmación + IP eliminada

### POST /api/dns-doh/clear-all
**Response**: Confirmación + cantidad eliminada

## Sincronización

### PortRulesMonitor Sync Loop

```python
def start():
    self.running = True
    self.thread = Thread(target=self._run, daemon=True)
    self.thread.start()
    
    # Sync inmediato
    self.sync_rules()
    self.sync_doh_servers()

def _run():
    while self.running:
        time.sleep(self.sync_interval)  # 600s = 10 min
        if self.running:
            self.sync_rules()
            self.sync_doh_servers()
```

### Sync DoH Servers

```python
def sync_doh_servers() -> bool:
    try:
        response = requests.get(
            f"{server_url}/api/dns-doh/list",
            timeout=5
        )
        
        if response.status_code != 200:
            logger.debug(f"Failed: {response.status_code}")
            return False
        
        data = response.json()
        
        with lock:
            doh_servers = []
            for server in data.get("servers", []):
                ip = server.get("ip_address")
                if ip:
                    doh_servers.append(ip)
            
            last_doh_sync = time.time()
        
        logger.info(f"Synced {len(doh_servers)} DoH server(s)")
        return True
        
    except Exception as e:
        logger.debug(f"Sync error: {e}")
        return False
```

## Deduplicación

### Cache de Eventos

```python
# Estructura
event_cache: {
    (src_ip, dst_ip, port, protocol): {
        "count": N,           # Paquetes en flujo
        "first_seen": time,   # Timestamp primer paquete
        "last_seen": time     # Timestamp último paquete
    }
}

# Ventana de deduplicación: 10 segundos
# Después de 10s → permite reportar mismo flujo nuevamente
```

### Algoritmo

```python
def _deduplicate_event(src_ip, dst_ip, port, protocol) -> bool:
    key = (src_ip, dst_ip, port, protocol)
    now = time.time()
    
    with cache_lock:
        if key not in cache:
            # Nuevo flujo
            cache[key] = {
                "count": 1,
                "first_seen": now,
                "last_seen": now
            }
            return True  # Reportar
        
        data = cache[key]
        elapsed = now - data["last_seen"]
        
        if elapsed < DEDUP_WINDOW:
            # Dentro ventana → duplicado
            data["count"] += 1
            data["last_seen"] = now
            return False  # No reportar
        else:
            # Fuera ventana → nuevo intento
            data["count"] = 1
            data["first_seen"] = now
            data["last_seen"] = now
            return True  # Reportar
```

## Eventos Generados

### Event JSON

```json
{
  "type": "port_event",
  "port": 443,
  "protocol": "tcp",
  "source": "192.168.1.100",
  "destination": "1.1.1.1",
  "is_external": true,
  "packet_count": 1
}
```

### Flujo en Dashboard

```
PortMonitor callback(event)
  ↓
MonitorManager._handle_port(port_data)
  ├─ Crear Event pydantic
  └─ event_callback (WSSender.add_event)
      ↓
    WSSender
      ├─ Enqueue a buffer
      ├─ Enviar vía WebSocket
      └─ Persistir en BD
          ↓
        ConnectionManager
          ├─ Broadcast a dashboards
          ├─ Log en memory
          └─ save_event(session_id, agent_id, "event", ts, data)
```

## Configuración y Extensión

### Cambiar intervalo de sincronización

```python
# agent/monitors/manager.py
self.port_rules_monitor = PortRulesMonitor(
    server_url=server_url,
    sync_interval=300  # 5 minutos en lugar de 10
)
```

### Agregar nueva regla de puerto

En `agent/monitors/port_monitor.py`, método `_should_report_event()`:

```python
# Ejemplo: Agregar regla para puerto 22 (SSH)
if dst_port == 22 and protocol == "tcp":
    logger.debug(f"[PORT] Custom rule: SSH to {dst_ip}")
    return is_external_ip(dst_ip)  # Solo reportar si es externo
```

### Cambiar ventana de deduplicación

```python
# agent/monitors/port_monitor.py
class PortMonitor:
    DEDUP_WINDOW = 5  # Cambiar de 10 a 5 segundos
```

### Habilitar logs detallados

```python
# agent/utils/logger.py
# Cambiar DEBUG_MODE o nivel global
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Performance y Optimizaciones

### 1. Event Cache Cleanup
- Se ejecuta cada segundo en thread separado
- Elimina entradas expiradas (> DEDUP_WINDOW)
- Evita memory leak por flujos antiguos

### 2. TCP Connection Cache
- Usa dict con key = (src_ip, dst_ip, port)
- Se limpia al detectar FIN/RST
- Soporte para múltiples conexiones simultáneas

### 3. DoH Server Caching
- Cache en memory del PortRulesMonitor
- Sincroniza cada 10 minutos (no en cada paquete)
- Operación O(1) para buscar si IP está en DoH servers

### 4. Local IP Detection
- Cache en memory al iniciar
- Puede ser refresh ocasional si se reacomodan interfaces
- Evita llamadas repetidas a socket

## Debugging y Troubleshooting

### Ver qué está siendo capturado

```bash
# Terminal 1: Logs del agent
tail -f logs/agent.log | grep "\[PORT\]"

# Terminal 2: tcpdump para verificar paquetes reales
sudo tcpdump -i any '(tcp or udp) and (port 443 or port 853)' -n -vv
```

### Verificar estado de cache

```python
# En agent/monitors/port_monitor.py
stats = port_monitor.get_cache_stats()
print(f"Cached flows: {stats['cached_flows']}")
print(f"Total packets: {stats['total_packets']}")
```

### Verificar sincronización DoH

```python
# En agent/monitors/port_rules_monitor.py
doh_ips = port_rules_monitor.get_doh_servers()
print(f"DoH servers in cache: {doh_ips}")
```

### Test IP Detection

```python
from agent.utils.local_network import get_local_ips, is_external_ip

local = get_local_ips()
print(f"Local IPs: {local}")
print(f"8.8.8.8 is external: {is_external_ip('8.8.8.8')}")
```

## Posibles Problemas y Soluciones

| Problema | Causa | Solución |
|----------|-------|----------|
| No hay eventos puerto 853 | Interfaz no captura TCP/UDP | Verificar con tcpdump |
| Eventos duplicados | DEDUP_WINDOW muy corto | Aumentar ventana |
| No se sincronizan DoH | Servidor no responde | Verificar `/api/dns-doh/list` |
| IPs locales no detectadas | No acceso a interfaz | Ejecutar con permisos |
| Mucho consumo CPU | Demasiados paquetes | Aplicar filtros en scapy |
| Conexiones TCP no detectadas | Flags TCP no capturados | Verificar flags en logs DEBUG |

## Roadmap Futuro

1. **WebUI para gestionar DoH servers** - Dashboard para CRUD sin APIs
2. **GeoIP integration** - Mostrar país de destino
3. **Threat intelligence** - Marcar IPs maliciosas
4. **Rules engine** - Sistema flexible de reglas (similarJSON-based)
5. **Rate limiting** - Alertas si tráfico anormal
6. **VPN/Proxy detection** - Detectar anómalo en patrones
