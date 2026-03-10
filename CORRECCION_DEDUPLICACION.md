# 🔧 Corrección: Deduplicación de Eventos - Paso a Paso

## 🚨 IMPORTANTE: Reiniciar el Agente

El código ha sido actualizado pero **el agente debe ser reiniciado** para que use el nuevo código.

```bash
# Detener el agente actual
Ctrl+C en la terminal donde corre el agente

# Esperar 2 segundos

# Reiniciar el agente
make agent
# o
python3 -m agent.main
```

---

## 🔍 ¿Cómo Verificar que Funciona?

### 1. Revisar los Logs del Agente

Cuando reinicies, busca estos mensajes en la terminal del agente:

```
[PORT] NEW: TCP/46984 151.101.129.91→192.168.2.33 [REPORTED, total_in_flow: 1]
[PORT] DUP:  TCP/46984 151.101.129.91→192.168.2.33 [SKIPPED, total_in_flow: 2]
[PORT] DUP:  TCP/46984 151.101.129.91→192.168.2.33 [SKIPPED, total_in_flow: 3]
[PORT] DUP:  TCP/46984 151.101.129.91→192.168.2.33 [SKIPPED, total_in_flow: 4]
[PORT] DUP:  TCP/46984 151.101.129.91→192.168.2.33 [SKIPPED, total_in_flow: 5]
```

**Esto significa:**
- ✅ PRIMER paquete: Se reporta (NEW)
- ✅ Paquetes 2-5: Se ignoran (DUP - duplicado)
- ✅ Total agregado: 5 paquetes en 1 evento

### 2. Ver el Evento en el Dashboard

El evento reportado incluirá:

```json
{
  "type": "port_violation",
  "port": 46984,
  "protocol": "tcp",
  "source": "151.101.129.91",
  "destination": "192.168.2.33",
  "packet_count": 5,
  "reason": "Port 46984 not allowed from 151.101.129.91"
}
```

**En lugar de:**
```
5 eventos idénticos separados
```

---

## 📊 Cambios Realizados

### En `port_monitor.py`:

1. **Ventana de deduplicación aumentada**: De 5s a 10s
2. **Lógica mejorada**: Ahora es completamente atómica dentro de locks
3. **Logging detallado**: [NEW] vs [DUP] para cada event
4. **Mejor rastreo**: Registra timestamp y counters correctamente

---

## 🧪 Test Rápido

### Intentar conectar al puerto 22 varias veces:

```bash
# En la máquina cliente
for i in {1..10}; do
  timeout 1 nc -zv 192.168.2.33 22 2>/dev/null
  sleep 0.1
done
```

**Esperado:**
- Logs en agente: 1x NEW + 9x DUP
- Dashboard: 1 evento con `packet_count: 10`

**Anterior (sin funcionar):**
- Logs: 10 eventos duplicados
- Dashboard: 10 eventos diferentes

---

## 🔧 Configuración (Opcional)

### Cambiar ventanas de deduplicación

En `agent/monitors/port_monitor.py`, línea ~15:

```python
DEDUP_WINDOW = 10  # Cambiar aquí (segundos)
MIN_REPORT_INTERVAL = 10  # Cambiar aquí
```

**Recomendaciones:**
- `5s`: Menos agregación, más sensible
- `10s`: RECOMENDADO ← Balance
- `30s`: Mucha agregación, poco ruido

---

## 🐛 Troubleshooting

### Si aún sigue viendo duplicados después de reiniciar:

```bash
# 1. Verificar que Python está usando el archivo correcto
python3 -c "import agent.monitors.port_monitor; print(agent.monitors.port_monitor.__file__)"

# 2. Limpiar bytecode
find . -name "*.pyc" -delete
find . -name "__pycache__" -delete

# 3. Reiniciar nuevamente
make agent
```

### Si no ve logs de [PORT]:

```bash
# Verificar que el agente está capturando paquetes
# (Podría necesitar sudo/permisos)

sudo python3 -m agent.main
```

---

## ✅ Checklist de Verificación

- [ ] Agente ha sido reiniciado después de cambios
- [ ] Se ven logs [NEW] y [DUP] en la terminal del agente
- [ ] Dashboard muestra solo 1 evento con `packet_count > 1`
- [ ] Los eventos muestran la información correcta
- [ ] Sin duplicados en el mismo segundo

---

## 📝 Ejemplo de Antes vs Después

### ANTES (Sin funcionar)

```
Timestamp: 09:18:19
Event 1: TCP/46984 from 151.101.129.91 to 192.168.2.33
Event 2: TCP/46984 from 151.101.129.91 to 192.168.2.33  ← DUP
Event 3: TCP/46984 from 151.101.129.91 to 192.168.2.33  ← DUP
Event 4: TCP/46984 from 151.101.129.91 to 192.168.2.33  ← DUP
Event 5: TCP/46984 from 151.101.129.91 to 192.168.2.33  ← DUP
Event 6: TCP/46984 from 151.101.129.91 to 192.168.2.33  ← DUP
```

Total: 6 eventos

### DESPUÉS (Funcionando)

```
Timestamp: 09:18:19
Event 1: TCP/46984 from 151.101.129.91 to 192.168.2.33 [packet_count: 6]

Logs:
[PORT] NEW:  TCP/46984 151.101.129.91→192.168.2.33 [REPORTED, total_in_flow: 1]
[PORT] DUP:  TCP/46984 151.101.129.91→192.168.2.33 [SKIPPED, total_in_flow: 2]
[PORT] DUP:  TCP/46984 151.101.129.91→192.168.2.33 [SKIPPED, total_in_flow: 3]
[PORT] DUP:  TCP/46984 151.101.129.91→192.168.2.33 [SKIPPED, total_in_flow: 4]
[PORT] DUP:  TCP/46984 151.101.129.91→192.168.2.33 [SKIPPED, total_in_flow: 5]
[PORT] DUP:  TCP/46984 151.101.129.91→192.168.2.33 [SKIPPED, total_in_flow: 6]
```

Total: 1 evento + 5 ignorados = **6 eventos agregados en 1 reporte**

---

## 🎯 Pasos Siguientes

### Para 100% seguro de que funciona:

1. **Ejecuta en modo debug** para ver los logs:

```bash
# Terminal 1: Agente con debug
python3 -m agent.main

# Terminal 2: Generar tráfico de prueba
for i in {1..50}; do
  timeout 0.5 nc -zv 192.168.2.33 22 2>/dev/null &
done
```

2. **Observa los logs**: Deberías ver NEW una vez, DUP ~49 veces

3. **Verifica en dashboard**: 1 evento con `packet_count: 50`

---

## 📞 Si Sigue Sin Funcionar

Por favor comparte:

1. El contenido de `agent/monitors/port_monitor.py` línea ~15 (confirmar DEDUP_WINDOW)
2. Los primeros 10 eventos del nuevo log (después de reiniciar)
3. Salida de: `python3 -c "import agent.monitors.port_monitor; print(agent.monitors.port_monitor.PortMonitor.DEDUP_WINDOW)"`

Esto me ayudará a ver si realmente se están usando los nuevos cambios.

---

**Versión:** 2.0 (Revisada)  
**Estado:** ✅ Ready to Test  
**Necesita:** Reinicio del agente
