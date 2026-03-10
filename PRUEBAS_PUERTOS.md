# Guía de Pruebas - Reestructuración de Monitorización de Puertos

## Prerrequisitos

- Servidor SèniaEye corriendo en `http://127.0.0.1:1984`
- Agent corriendo y conectado al servidor
- Acceso a terminal/bash
- `curl` disponible
- Permisos de root (para capturar paquetes)

## 1. Verificar Inicialización

### 1.1 Verificar que la tabla DNS DoH está creada

```bash
# Conectarse a la BD
sqlite3 ~/Documents/Projects/seniaEye/server/seniaeye.db

# En sqlite3 shell:
.tables
# Debería mostrar: sessions events blocked_domains dns_doh_servers

# Ver esquema
.schema dns_doh_servers

# Salir
.quit
```

### 1.2 Verificar que PortRulesMonitor se inicia

```bash
# En los logs del agent, debería ver:
# [PORT_RULES] Monitor started
# [PORT_RULES] Synced 0 rule(s) from server
# [PORT_RULES] Synced 0 DoH server(s) from server
```

## 2. Pruebas Funcionales de API

### 2.1 Listar Servidores DoH (vacío inicialmente)

```bash
curl -s "http://127.0.0.1:1984/api/dns-doh/list" | jq .
# Respuesta esperada:
# {
#   "timestamp": "2026-03-10 HH:MM:SS",
#   "servers": [],
#   "total": 0
# }
```

### 2.2 Agregar Servidores DoH

```bash
# Cloudflare
curl -s -X POST "http://127.0.0.1:1984/api/dns-doh/add?ip_address=1.1.1.1&hostname=cloudflare&description=Cloudflare DoH" | jq .

# Google
curl -s -X POST "http://127.0.0.1:1984/api/dns-doh/add?ip_address=8.8.8.8&hostname=google&description=Google Public DNS" | jq .

# Quad9
curl -s -X POST "http://127.0.0.1:1984/api/dns-doh/add?ip_address=9.9.9.9&hostname=quad9&description=Quad9 DoH" | jq .
```

### 2.3 Verificar que los servidores se agregaron

```bash
curl -s "http://127.0.0.1:1984/api/dns-doh/list" | jq .
# Debería mostrar 3 servidores añadidos
```

### 2.4 Actualizar un Servidor

```bash
curl -s -X PUT "http://127.0.0.1:1984/api/dns-doh/1.1.1.1?hostname=CF&description=Cloudflare DNS (Updated)" | jq .
```

### 2.5 Eliminar un Servidor

```bash
curl -s -X DELETE "http://127.0.0.1:1984/api/dns-doh/9.9.9.9" | jq .
```

### 2.6 Verificar eliminación

```bash
curl -s "http://127.0.0.1:1984/api/dns-doh/list" | jq .
# Debería mostrar 2 servidores (Cloudflare y Google)
```

## 3. Pruebas de Monitorización (Reglas)

### Preparación: Iniciar captura de logs

```bash
# En terminal 1: Ver logs del agent
tail -f logs/agent.log | grep -E "\[PORT\]"
```

### 3.1 Regla 1: Puerto 853 (DNS over TLS)

```bash
# En terminal 2: Hacer conexión a puerto 853
# TCP
nc -zv 8.8.8.8 853

# O UDP (si nc lo soporta)
echo "test" | nc -u 8.8.8.8 853
```

**Expectativa**: 
- En logs del agent: `[PORT] NEW: TCP/853 ...` o `[PORT] NEW: UDP/853 ...`
- En dashboard: Evento de puerto 853 aparece

### 3.2 Regla 2: Puerto 443 a Servidores DoH

```bash
# Cloudflare (1.1.1.1) - registrado como DoH
curl -v https://1.1.1.1 2>&1 | head -20

# Google (8.8.8.8) - registrado como DoH  
curl -v https://8.8.8.8 2>&1 | head -20

# Otro servidor HTTPS (no DoH)
curl -v https://1.0.0.1 2>&1 | head -20
```

**Expectativa**:
- Puerto 443 a 1.1.1.1 (DoH): Evento generado ✅
- Puerto 443 a 8.8.8.8 (DoH): Evento generado ✅
- Puerto 443 a 1.0.0.1 (no DoH): NO evento ❌

### 3.3 Regla 3: Todos los Puertos a IPs Externas (Establecidas)

#### 3.3.1 Puerto local (NO debe generar evento)

```bash
# Conexión a IP local (debería estar en 192.168.x.x o 127.0.0.1)
# Reemplaza X.X.X.X con IP local de tu máquina
ping -c 1 127.0.0.1  # Loopback
curl -v http://127.0.0.1:8000 2>&1 | head -20
```

**Expectativa**: NO genera evento (IP es local)

#### 3.3.2 Puerto HTTP a IP externa NO establecido

```bash
# Intentar conexión a puerto extraño (no escuchando)
nc -zv 8.8.8.8 12345
```

**Expectativa**: NO genera evento (conexión rechazada, NO establecida)

#### 3.3.3 Puerto HTTP a IP externa ESTABLECIDO

```bash
# HTTP a Google (típicamente abierto)
curl -v http://8.8.8.8:80 2>&1 | head -30

# O HTTPS
curl -v https://8.8.4.4 2>&1 | head -30
```

**Expectativa**: 
- TCP/80→8.8.8.8: Evento generado (si conexión se establece)
- TCP/443→8.8.4.4: Evento generado (si conexión se establece)

#### 3.3.4 UDP a IP externa

```bash
# Consulta DNS a Google
dig @8.8.8.8 google.com

# O simplemente:
nslookup google.com 8.8.8.8
```

**Expectativa**: 
- UDP/53→8.8.8.8: Evento generado

## 4. Verificar Deduplicación

```bash
# Ejemplo: Hacer la misma conexión múltiples veces en corta ventana
for i in {1..5}; do
  curl -v https://1.1.1.1 -w "\nIntento $i\n" 2>&1 | grep -E "Connected|Intento"
  sleep 1
done
```

**Expectativa**:
- Primer intento: Evento generado
- Intentos 2-5 (dentro de ventana de 10s): Duplicados silenciosos (sin eventos)
- Después de 10s: Nuevamente evento

## 5. Verificar Detección de IPs Locales

### 5.1 Verificar que el agent detecta IPs locales

```python
# Script de prueba
python3 << 'EOF'
from agent.utils.local_network import is_local_ip, get_local_ips, is_external_ip

# Ver IPs locales detectadas
local_ips = get_local_ips()
print(f"Local IPs detected: {local_ips}")

# Pruebas
print(f"127.0.0.1 is local: {is_local_ip('127.0.0.1')}")  # True
print(f"8.8.8.8 is local: {is_local_ip('8.8.8.8')}")      # False
print(f"8.8.8.8 is external: {is_external_ip('8.8.8.8')}") # True
EOF
```

**Expectativa**:
- 127.0.0.1: Local
- 8.8.8.8: Externo
- IPs del hostname local: Local

## 6. Verificar Sincronización de DoH Servers

```bash
# Esperar 10+ minutos O forzar:

# Agregar servidor nuevo
curl -s -X POST "http://127.0.0.1:1984/api/dns-doh/add?ip_address=101.101.101.101&hostname=test" | jq .

# Hacer conexión a puerto 443 a IP 101.101.101.101
# (No se establecerá pero debería ser rechazada de inmediato)
nc -zv 101.101.101.101 443

# Ver en logs del agent
tail -f logs/agent.log | grep -E "Rule 2|DoH"
```

**Expectativa**:
- DoH servers se sincronizan automáticamente cada 10 minutos
- El port_monitor conoce los servidores DoH actualizados

## 7. Casos Edge

### 7.1 Conexión a localhost en puerto 443

```bash
# Si hay servidor HTTPS en localhost
curl -v https://127.0.0.1:443 2>&1 | head -20
# O
curl -v https://localhost:443 2>&1 | head -20
```

**Expectativa**: NO genera evento (IP local)

### 7.2 Conexión rechazada (RST)

```bash
# Puerto que no escucha
curl -v http://8.8.8.8:12345 2>&1
```

**Expectativa**: NO genera evento (conexión rechazada = no establecida)

### 7.3 Timeout

```bash
# IP que no responde (debería timeout)
curl -m 3 http://192.0.2.1 2>&1
```

**Expectativa**: NO genera evento (conexión no establecida)

## 8. Dashboard Verification

1. Abrir http://127.0.0.1:1984/ en navegador
2. Pestaña "Dashboard"
3. Realizar pruebas anteriores
4. Verificar que eventos aparecen en tiempo real:
   - Tipo: `port_event`
   - Puerto: Según regla
   - Source/Destination: IPs correctas
   - `is_external`: True/False según corresponda

## 9. Próximos Steps después de pruebas

1. ✅ Todas las pruebas pasan → Implementación exitosa
2. ❌ Fallos en Regla 1/2 → Revisar sincronización de DoH servers
3. ❌ Fallos en Regla 3 → Revisar detección TCP/UDP y IPs locales
4. 🔍 Logs vacíos → Asegurar que agent está corriendo y capturando paquetes

## Notas de Debugging

### Ver estado de PortRulesMonitor

```bash
# En sqlite3:
SELECT COUNT(*) FROM dns_doh_servers;
SELECT * FROM dns_doh_servers;
```

### Ver paquetes siendo capturados

```bash
# En otra terminal (requiere root)
sudo tcpdump -i any '(tcp or udp) and (port 443 or port 853)' -n
```

### Habilitar modo verbose en agent

Editar `agent/config/default.yaml`:
```yaml
log_level: DEBUG  # Cambiar de INFO a DEBUG
```

Entonces verás más detalles:
```
[PORT] Rule 1 match: port 853
[PORT] Rule 2 match: port 443 to DoH server 1.1.1.1
[PORT] Rule 3 match: TCP/8080 to external 8.8.8.8 (established)
```
