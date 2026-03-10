# Reestructuración de Monitorización de Puertos - Resumen de Cambios

## Descripción General
Se ha reestructurado completamente la monitorización de puertos en SèniaEye para generar eventos únicamente en casos específicos, mejorando la precisión y reduciendo falsos positivos.

## Cambios Realizados

### 1. **Base de Datos (server/database.py)**

#### Nueva Tabla: `dns_doh_servers`
- **Propósito**: Almacenar servidores DNS que permiten DoH (DNS over HTTPS)
- **Campos**:
  - `id`: Identificador único (INTEGER, PRIMARY KEY)
  - `ip_address`: Dirección IP del servidor (TEXT, UNIQUE)
  - `hostname`: Nombre de host opcional
  - `description`: Descripción del servidor
  - `created_at`: Timestamp de creación
  - `updated_at`: Timestamp de última actualización

#### Nuevas Funciones CRUD
- `add_dns_doh_server(ip_address, hostname, description)` - Agregar servidor
- `remove_dns_doh_server(ip_address)` - Eliminar servidor
- `list_dns_doh_servers()` - Listar todos con metadata
- `get_dns_doh_ips()` - Obtener solo lista de IPs
- `dns_doh_server_exists(ip_address)` - Verificar existencia
- `update_dns_doh_server(ip_address, hostname, description)` - Actualizar
- `clear_all_dns_doh_servers()` - Limpiar todos

### 2. **Utilidades de Red Local (agent/utils/local_network.py) - NUEVO**

Archivo nuevo para detectar y verificar IPs locales de la máquina:

- `get_local_ips()` → Set[str]
  - Retorna todas las IPs locales de la máquina (IPv4 e IPv6)
  - Incluye addresses de loopback (127.0.0.1, ::1)

- `is_local_ip(ip: str)` → bool
  - Verifica si una IP es local a la máquina
  - Retorna `True` si es local, `False` si es externa

- `is_external_ip(ip: str)` → bool
  - Verifica si una IP es externa (opuesto a is_local_ip)

### 3. **Monitor de Puertos Reestructurado (agent/monitors/port_monitor.py)**

#### Nueva Lógica de Eventos

El monitor ahora genera eventos SOLO en estos casos:

**Regla 1: Puerto 853 (DNS over TLS/DTLS)**
- Genera eventos para TCP/UDP en puerto 853
- Sin condiciones adicionales
- Ejemplo: `TCP/853 192.168.1.100→8.8.8.8` → ✅ EVENTO

**Regla 2: Puerto 443 a Servidores DoH**
- Genera eventos para TCP/UDP en puerto 443
- SOLO si el destino está en la lista de servidores DoH en BD
- Ejemplo: 
  - `TCP/443 192.168.1.100→8.8.8.8` (sin DoH) → ❌ NO
  - `TCP/443 192.168.1.100→1.1.1.1` (DoH) → ✅ EVENTO

**Regla 3: Todos los Puertos a IPs Externas (Conexiones Establecidas)**
- Genera eventos para TODOS los puertos
- SOLO hacia direcciones IP externas (no locales)
- SOLO si la conexión se ha establecido:
  - **TCP**: Detecta handshake (SYN-ACK o ACK) → establece conexión
  - **UDP**: Reporta primer paquete (sin conexión en UDP)
- Ejemplo:
  - `TCP/8080 192.168.1.100→192.168.1.50` (local) → ❌ NO
  - `TCP/8080 192.168.1.100→8.8.8.8` (external, no established) → ❌ NO
  - `TCP/8080 192.168.1.100→8.8.8.8` (external, established) → ✅ EVENTO
  - `UDP/53 192.168.1.100→8.8.8.8` (external) → ✅ EVENTO

#### Detalles Técnicos

- **Rastreo de Conexiones TCP**: Usa flags TCP para detectar estado:
  - `SYN (0x02)`: Inicio de conexión
  - `SYN-ACK (0x12)`: Confirmación de servidor
  - `ACK (0x10)`: Acknowledgement
  - `FIN (0x01)`, `RST (0x04)`: Cierre/Reset

- **Detección de IPs Locales**:
  - Detecta automáticamente IPs locales de la máquina
  - Se refresca periódicamente
  - Incluye loopback addresses

- **Deduplicación**:
  - Evita reportar duplicados del mismo flujo en ventana de 10 segundos
  - Cada flow único: (src_ip, dst_ip, puerto, protocolo)

### 4. **Monitor de Reglas de Puertos Extendido (agent/monitors/port_rules_monitor.py)**

#### Nuevas Funcionalidades
- Sincronización de servidores DoH desde servidor
- `sync_doh_servers()` - Sincroniza lista de servidores DoH
- `get_doh_servers()` - Retorna lista actual de IPs DoH

- Sincronización automática cada 10 minutos (configurable)
- Sincroniza reglas de puertos Y servidores DoH en paralelo

### 5. **API REST para DNS DoH (server/main.py)**

Nuevos endpoints para gestionar servidores DNS DoH:

#### Endpoints

1. **GET /api/dns-doh/list**
   - Lista todos los servidores DNS DoH registrados
   - Retorna: `{servers: [...], total: N, timestamp}`

2. **POST /api/dns-doh/add**
   - Parámetros: `ip_address` (requerido), `hostname` (opcional), `description` (opcional)
   - Agrega nuevo servidor DoH
   - Retorna: Confirmación con datos

3. **PUT /api/dns-doh/{ip_address}**
   - Actualiza información de servidor existente
   - Parámetros opcionales: `hostname`, `description`
   - Retorna: Datos actualizados

4. **DELETE /api/dns-doh/{ip_address}**
   - Elimina un servidor DoH
   - Retorna: Confirmación

5. **POST /api/dns-doh/clear-all**
   - Elimina todos los servidores registrados
   - Retorna: Número de servidores eliminados

## Ejemplo de Uso

### Agregar Servidores DoH vía API

```bash
# Agregar Cloudflare (1.1.1.1)
curl -X POST "http://127.0.0.1:1984/api/dns-doh/add?ip_address=1.1.1.1&hostname=cloudflare-dns&description=Cloudflare DoH"

# Agregar Google (8.8.8.8)
curl -X POST "http://127.0.0.1:1984/api/dns-doh/add?ip_address=8.8.8.8&hostname=google-dns&description=Google Public DNS"

# Listar todos
curl "http://127.0.0.1:1984/api/dns-doh/list"

# Actualizar
curl -X PUT "http://127.0.0.1:1984/api/dns-doh/1.1.1.1?description=Updated description"

# Eliminar
curl -X DELETE "http://127.0.0.1:1984/api/dns-doh/1.1.1.1"
```

## Flujo de Sincronización

1. **Agent inicia** → PortRulesMonitor inicia
2. **PortRulesMonitor**: Sincroniza reglas de puertos Y servidores DoH inmediatamente
3. **Cada 10 minutos**: Resincroniza ambos
4. **PortMonitor**: Consulta DoH servers en tiempo real para Regla 2

## Eventos Generados

Formato de evento del monitor:
```python
{
    "type": "port_event",
    "port": 443,
    "protocol": "tcp",
    "source": "192.168.1.100",
    "destination": "1.1.1.1",
    "is_external": True,
    "packet_count": 1
}
```

## Testing Recomendado

1. **Regla 1 (Puerto 853)**:
   ```bash
   # Cualquier tráfico TCP/UDP en puerto 853 debe generar evento
   nc -u 8.8.8.8 853  # UDP
   nc -z 8.8.8.8 853  # TCP
   ```

2. **Regla 2 (Puerto 443 a DoH)**:
   ```bash
   # Primero registrar 1.1.1.1 como DoH server
   curl https://1.1.1.1  # Debe generar evento
   curl https://8.8.8.8  # No registrado, NO genera evento
   ```

3. **Regla 3 (Externas establecidas)**:
   ```bash
   # Conexión establece a puerto Web (externa)
   curl https://8.8.8.8  # Evento generado si conexión se establece
   ```

## Notas Importantes

- ⚠️ **Es necesario ejecutar como root** para capturar paquetes TCP/UDP
- 📡 **Los cambios en DoH servers** se sincronizan automáticamente cada 10 minutos
- 🔍 **El rastreo TCP es estadístico** - se basa en flags observados
- 🚀 **UDP es sin conexión** - se reporta el primer paquete hacia IP externa
- 💾 **Los datos se persisten** en la BD, sobreviven reiniciosxn

## Archivos Modificados

| Archivo | Cambios |
|---------|---------|
| `server/database.py` | +tabla dns_doh_servers, +CRUD functions |
| `agent/utils/local_network.py` | NUEVO - detección IPs locales |
| `agent/monitors/port_monitor.py` | COMPLETAMENTE REESTRUCTURADO |
| `agent/monitors/port_rules_monitor.py` | +sincronización DoH servers |
| `server/main.py` | +5 nuevos endpoints API |
