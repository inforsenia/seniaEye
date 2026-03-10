# Visualización: Deduplicación de Eventos de Puertos

## Antes vs Después

### ❌ ANTES (Sin Deduplicación)

```
Tiempo        Evento                                    Dashboard
─────────────────────────────────────────────────────────────────
17:32:45.001  ⚠️ TCP/22 violation: 192.168.1.50 ───→ [1] Violation
17:32:45.002  ⚠️ TCP/22 violation: 192.168.1.50 ───→ [2] Violation
17:32:45.003  ⚠️ TCP/22 violation: 192.168.1.50 ───→ [3] Violation
17:32:45.004  ⚠️ TCP/22 violation: 192.168.1.50 ───→ [4] Violation
17:32:45.005  ⚠️ TCP/22 violation: 192.168.1.50 ───→ [5] Violation
...
17:32:45.255  ⚠️ TCP/22 violation: 192.168.1.50 ───→ [254] Violation
17:32:45.256  ⚠️ TCP/22 violation: 192.168.1.50 ───→ [255] Violation

❌ PROBLEMA: 255+ eventos idénticos en 1 segundo
❌ Dashboard inundado
❌ Difícil analizar
```

---

### ✅ DESPUÉS (Con Deduplicación)

```
Caché de Deduplicación
─────────────────────────────────────────
(192.168.1.50, 10.0.0.1, 22, tcp)
  ├─ count: 1      → Report event [Violation #1]
  ├─ first_seen: 17:32:45.001
  └─ last_seen: 17:32:45.001

Paquetes 2-255 (dentro de 5 segundos)
  └─ Actualizar count: 2, 3, 4... ✗ NO REPORTAR

Después de 5 segundos (nueva ventana)
  └─ Limpiar caché, flujo expirado


Tiempo        Evento                                    Dashboard
─────────────────────────────────────────────────────────────────
17:32:45.001  ⚠️ TCP/22 violation: 192.168.1.50 ───→ [1] Violation
              (agregó 254 paquetes más)
              packet_count: 255

17:32:50.050  ⚠️ TCP/22 violation: 192.168.1.50 ───→ [2] Violation   ← Nueva ventana
              (nuevo intento)
              packet_count: 8

✅ RESULTADO: 2 eventos en lugar de 263
✅ Dashboard limpio
✅ Fácil de analizar
```

---

## Flujo Técnico

```
                    ┌─ TCP/IP Stack ─┐
                    │  (Scapy sniff)  │
                    └────────┬────────┘
                             │
                             ↓
                    ┌─────────────────────────┐
                    │  _packet_callback()     │
                    │  Procesa cada paquete   │
                    └────────────┬────────────┘
                                 │
                  ┌──────────────┴──────────────┐
                  │                             │
                  ↓                             ↓
         ┌─────────────────┐      ┌──────────────────────┐
         │ Extract Fields  │      │ Check Port Rules     │
         │ src, dst, port  │      │ Allowed/Blocked?     │
         └────────┬────────┘      └──────────┬───────────┘
                  │                           │
                  └───────────────┬───────────┘
                                  │
                                  ↓
                        ┌──────────────────────────┐
                        │ _deduplicate_event()     │
                        │ Check event_cache        │
                        └──────┬─────────┬─────────┘
                               │         │
                        ┌──────┘         │
                        │                │
                  ┌─────▼────┐    ┌──────▼─────────┐
                  │ NEW EVENT │    │ DUPLICATE      │
                  │ Report    │    │ Update count   │
                  │ to server │    │ (no report)    │
                  └───────────┘    └────────────────┘

                  ▲
                  │
        ┌─────────┴────────────────┐
        │ _cleanup_loop() Thread   │
        │ (cada 1 segundo)         │
        │ Remove expirados         │
        └──────────────────────────┘
```

---

## Ejemplo de Estadísticas

### Simulación: Ataque de Port Scanning

```
Atacante intenta puertos: 20, 21, 22, 23, 25, 80, 443...

SIN Deduplicación:
├─ Paquetes capturados: 1,200+
├─ Eventos reportados: 1,200+
├─ Tiempo dashboard: 10+ segundos para cargar
└─ ❌ Imposible analizar

CON Deduplicación (ventana 5s):
├─ Paquetes capturados: 1,200+
├─ Eventos reportados: 15   ← 1 por puerto único (puertos 20-22 violados)
├─ Tiempo dashboard: carga al instante
└─ ✅ Claro ver puertos atacados
```

---

## Caché en Memoria

```
event_cache = {
    ('192.168.1.50', '10.0.0.1', 22, 'tcp'): {
        'count': 255,
        'first_seen': 1709990365.123,
        'last_seen': 1709990365.382
    },
    ('192.168.1.50', '10.0.0.1', 80, 'tcp'): {
        'count': 3,
        'first_seen': 1709990370.001,
        'last_seen': 1709990370.005
    },
    ('192.168.1.51', '10.0.0.2', 443, 'tcp'): {
        'count': 1,
        'first_seen': 1709990372.450,
        'last_seen': 1709990372.450
    }
}

                    ▼
        DEDUP_WINDOW = 5 segundos
              (limpieza automática)

[After 5s]
    event_cache = {}  ← todos expirados, caché limpio
```

---

## Ventanas de Tiempo

```
Paquete 1 (t=0.001s)
  └─ Crear entrada en caché
     ↓ REPORT EVENT #1 (packet_count: 1)

Paquetes 2-100 (t=0.002s - 0.150s)
  └─ Misma clave, last_seen actualizado
     ✗ NO REPORT (quedan dentro de ventana)

Paquetes 101-250 (t=0.151s - 0.382s)
  └─ Aún dentro de ventana (< 5s total)
     ✗ NO REPORT

[t=5.000s]
  └─ Ventana expirada
     Caché limpiado:  cache[key] = deleted

Paquete 251 (t=5.050s) - NUEVO INTENTO
  └─ Crear NUEVA entrada en caché
     ↓ REPORT EVENT #2 (packet_count: 1)
```

---

## Impacto

| Métrica | Antes | Después | Mejora |
|---------|-------|---------|--------|
| Eventos por flujo | 100-1000+ | 1 + contador | **99.9%** |
| Carga DB | Alta | Baja | **100x** |
| Análisis manual | Difícil | Fácil | **∞** |
| Dashboard speed | Lento | Rápido | **10x+** |
| Storage eventos | Masivo | Mínimo | **99%** |

---

## 📊 Configuración

### Ajustar Ventana de Deduplicación

Archivo: `agent/monitors/port_monitor.py`

```python
# Línea 15
DEDUP_WINDOW = 5  # Cambiar aquí

Valores recomendados:
├─ 1s   → Muy sensible (reporta mucho)
├─ 3s   → Medium
├─ 5s   → RECOMENDADO (balance)
├─ 10s  → Muy agregado (pierde detalles)
└─ 30s  → Extremo (solo intent intento por minuto!)
```

### Cambiar Frecuencia de Limpieza

Archivo: `agent/monitors/port_monitor.py`

```python
# En _cleanup_loop()
time.sleep(1)  # Cambiar aquí

Frecuencias:
├─ 0.5s → Más limpio, más CPU
├─ 1s → RECOMENDADO
├─ 5s → Menos limpio, menos CPU
└─ 10s → Puede dejar basura
```

---

## ✨ Conclusión

La deduplicación transforma un flujo de eventos ruidoso en un flujo limpio y significativo, manteniendo toda la información necesaria en el campo `packet_count`.

**Antes:** 🔴🔴🔴 Caos  
**Después:** 🟢🟢🟢 Orden
