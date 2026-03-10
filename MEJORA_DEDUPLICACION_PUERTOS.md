# Mejora de Monitoreo de Puertos - Deduplicación de Eventos

## 🎯 Problema Resuelto

Cuando había tráfico de red continuado hacia un puerto no permitido, se capturaban múltiples paquetes en milisegundos, generando cientos o miles de eventos idénticos en el mismo segundo. Esto dificultaba el análisis.

**Ejemplo del problema:**
```
17:32:45.001 - Port violation: TCP/22 from 192.168.1.50 to 10.0.0.1
17:32:45.002 - Port violation: TCP/22 from 192.168.1.50 to 10.0.0.1
17:32:45.003 - Port violation: TCP/22 from 192.168.1.50 to 10.0.0.1
17:32:45.004 - Port violation: TCP/22 from 192.168.1.50 to 10.0.0.1
... (100+ eventos idénticos)
```

---

## ✅ Solución Implementada

Se ha agregado un **sistema de deduplicación y agregación de eventos** que:

1. **Identifica flujos únicos** por: `(source_ip, destination_ip, port, protocol)`
2. **Agrega paquetes similares** dentro de una **ventana de 5 segundos**
3. **Reporta solo una vez** cuando ocurre un nuevo flujo
4. **Cuenta paquetes** en cada evento reportado
5. **Auto-limpia caché** cuando expira la ventana

---

## 🔄 Cómo Funciona

### Flujo de Deduplicación

```
Captura paquete TCP/22 desde 192.168.1.50
    ↓
Crear clave: (192.168.1.50, 10.0.0.1, 22, tcp)
    ↓
¿Existe en caché?
    ├─ NO  → Registrar como nuevo evento, contador=1 ✓ REPORTAR
    └─ SÍ  → ¿Dentro de 5 segundos?
            ├─ SÍ  → Incrementar contador (contador=2,3,4...) ✗ NO REPORTAR
            └─ NO  → Entró nueva ventana, registrar como nuevo ✓ REPORTAR
```

### Ejemplo Mejorado

```
17:32:45.001 - Port violation: TCP/22 from 192.168.1.50 to 10.0.0.1 [packets: 1]
17:32:45.002 - (silencio - mismo flujo)
17:32:45.003 - (silencio - mismo flujo)
17:32:45.100 - (silencio - mismo flujo, total ~20 paquetes)
17:32:50.050 - Port violation: TCP/22 from 192.168.1.50 to 10.0.0.1 [packets: 1] ← Nueva ventana

Resultado: 2 eventos en lugar de 1000+
```

---

## 📊 Componentes de la Solución

### 1. Caché de Deduplicación

```python
event_cache = {
    (src_ip, dst_ip, port, protocol): {
        "count": N,           # Número de paquetes cap turados
        "first_seen": ts,     # Cuándo empezó el evento
        "last_seen": ts       # Último paquete capturado
    }
}

DEDUP_WINDOW = 5  # segundos
```

### 2. Principales Métodos

#### `_deduplicate_event(src, dst, port, proto)`
- Verifica si el evento es duplicado
- Retorna `True` si es nuevo, `False` si está dentro de la ventana
- Actualiza contador automáticamente

#### `_clean_cache()`
- Ejecuta cada 1 segundo
- Elimina entradas expiradas (> 5 segundos sin actividad)
- Mantiene caché en tamaño razonable

#### `get_cache_stats()`
- Retorna estadísticas del caché
- Útil para monitoreo

---

## 🎨 Campos en Evento Reportado

Ahora cada evento incluye:

```python
event = {
    "type": "port_violation",        # Tipo de evento
    "port": 22,                      # Puerto
    "protocol": "tcp",               # Protocolo
    "source": "192.168.1.50",        # IP origen
    "destination": "10.0.0.1",       # IP destino
    "allowed": False,                # ¿Permitido?
    "matched_rule": {...},           # Regla que aplica
    "reason": "...",                 # Razón
    "packet_count": 47               # NEW: Paquetes agregados
}
```

---

## ⚙️ Configuración

### Ventana de Deduplicación

```python
DEDUP_WINDOW = 5  # segundos

# Para cambiar:
# en port_monitor.py, busca:
# DEDUP_WINDOW = 5
```

**Opciones:**
- `1-3 segundos`: Muy estricto, puede reportar muchos eventos
- `5 segundos`: Equilibrio (DEFAULT)
- `10+ segundos`: Agrupa mucho, pierde granularidad

### Frecuencia de Limpieza

```python
time.sleep(1)  # Limpia cada 1 segundo

# Para cambiar:
# en _cleanup_loop(), modifica el sleep
```

---

## 📈 Ventajas

✅ **Reducción de ruido**: 99% menos eventos en tráfico continuado  
✅ **Información preservada**: Se conoce cuántos paquetes fueron  
✅ **Análisis más fácil**: Dashboard no se satura  
✅ **Rendimiento mejorado**: Menos eventos = menos procesamiento  
✅ **Patrones claros**: Se ven los intentos reales de acceso  
✅ **Thread-safe**: Usa locks para evitar race conditions  

---

## 🔍 Monitoreo

### Ver Estadísticas del Caché

```python
# En el código
stats = port_monitor.get_cache_stats()
print(f"Flujos en caché: {stats['cached_flows']}")
print(f"Total paquetes: {stats['total_packets']}")
print(f"Ventana: {stats['dedup_window']}s")
```

### Logs Disponibles

```
[PORT] TCP/22: 192.168.1.50 → 10.0.0.1 [count: 47, allowed: False]
↑ Solo se log cuando se reporta el evento
```

---

## 🧪 Ejemplo de Uso

### Escenario Real

Un estudiante intenta conectar por SSH múltiples veces:

```
Intento 1: 192.168.1.50 → SSH (22) → BLOQUEADO
  Paquetes: SYN, SYN-ACK, RST... (múltiples en 100ms)
  
Evento generado: SOLO 1
  source: 192.168.1.50
  packet_count: 14
  
30 segundos después:
Intento 2: Nuevo flujo SSH
  
Evento generado: OTRO, porque es nueva ventana
  source: 192.168.1.50
  packet_count: 9
```

**Resultado:** 2 eventos claros en lugar de 23

---

## 🔧 Implementación Técnica

### Thread de Limpieza

```python
Thread("cleanup", daemon=True)
  ↓
  _cleanup_loop()
    ├─ while running:
    │   ├─ _clean_cache()  → Limpia expirados
    │   └─ sleep(1s)
    └─ join() al detener
```

### Thread-Safety

```python
with self.cache_lock:
    # Acceso seguro al event_cache
    # Múltiples paquetes no crean race conditions
```

---

## 📝 Notas de Desarrollo

- Cache automáticamente se adapta al tráfico
- No hay límite máximo de caché (se limpia por tiempo)
- Event_cache puede crecer si hay muchos flujos únicos
- Es seguro dejarlo ejecutando indefinidamente

---

## 🚀 Próximas Mejoras (Opcional)

1. **Configuración por archivo YAML**: Hacer DEDUP_WINDOW configurable
2. **Reportes de resumen**: Cada N minutos, resumen de eventos agregados
3. **Alertas inteligentes**: Si packet_count > threshold, alerta roja
4. **Estadísticas por puerto**: Dashboard mostrando puertos más intentados
5. **Machine learning**: Detectar patrones de ataque (port scanning)

---

**Versión:** 1.0  
**Fecha:** 10 de março de 2026  
**Estado:** ✅ ACTIVO
