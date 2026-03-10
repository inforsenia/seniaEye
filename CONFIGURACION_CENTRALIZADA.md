# Configuración Centralizada - Puerto 1984

## Descripción General

Se ha centralizado la configuración de la dirección del servidor en archivos de configuración específicos. El puerto ahora se define en **un único lugar** para cada componente (servidor y agente).

## Ubicaciones de Configuración

### 1. Servidor (Backend)

**Archivo Principal: `server/config.yaml`**

```yaml
server:
  host: "0.0.0.0"          # Dirección de escucha
  port: 1984               # Puerto - PARÁMETRO CENTRAL
  base_url: "http://127.0.0.1:1984"
  websocket:
    url: "ws://127.0.0.1:1984/ws/events"
```

**Cómo se usa:**
- El Makefile referencia este puerto al ejecutar el servidor
- El módulo `server/config.py` proporciona funciones para leer esta configuración

**Para cambiar el puerto del servidor:**
1. Edita `server/config.yaml` → cambiar `port: 1984`
2. El Makefile automáticamente usará el puerto que se defina en el archivo de configuración

---

### 2. Agente (Frontend/Client)

**Archivo Principal: `agent/config/default.yaml`**

```yaml
server:
  ws_url: "ws://127.0.0.1:1984/ws/events"
  retry_delay: 30

agent:
  machine_name: ""
  log_level: "INFO"
```

**Cómo se usa:**
- El agente carga esta configuración al iniciar
- La URL se usa para conectar al servidor WebSocket

**Para cambiar la dirección del servidor desde el agente:**
1. Edita `agent/config/default.yaml` → modificar la URL en `server.ws_url`
2. O establece la variable de entorno `SERVER_WS_URL`

---

## Archivos Modificados

### Cambios realizados:

1. **`server/config.yaml`** (CREADO)
   - Configuración centralizada del servidor
   - Define host, puerto, URLs base y WebSocket

2. **`server/config.py`** (CREADO)
   - Módulo para cargar configuración del servidor
   - Funciones: `load_server_config()`, `get_server_address()`, `get_server_url()`

3. **`agent/config/default.yaml`** (ACTUALIZADO)
   - Puerto actualizado a 1984

4. **`agent/config.py`** (ACTUALIZADO)
   - Fallback de puerto actualizado a 1984

5. **`agent/utils/config.py`** (ACTUALIZADO)
   - Fallback de puerto actualizado a 1984

6. **`agent/main.py`** (ACTUALIZADO)
   - Fallback de puerto actualizado a 1984

7. **`agent/monitors/manager.py`** (ACTUALIZADO)
   - Fallback de puerto actualizado a 1984

8. **`agent/monitors/block_list_monitor.py`** (ACTUALIZADO)
   - Fallback de puerto actualizado a 1984

9. **`Makefile`** (ACTUALIZADO)
   - Comando `make server` ahora usa puerto 1984

---

## Cómo Usar

### Iniciar el servidor:
```bash
make server
```
Escuchará en: `http://0.0.0.0:1984`

### Iniciar el agente:
```bash
make agent
```
Se conectará a: `ws://127.0.0.1:1984/ws/events`

### Acceder al dashboard:
```
http://127.0.0.1:1984/
```

---

## Cambiar a Otra Dirección/Puerto

### Para cambiar la dirección del servidor:

1. **Edita `server/config.yaml`:**
   ```yaml
   server:
     host: "0.0.0.0"
     port: 5000  # Cambiar aquí
     base_url: "http://127.0.0.1:5000"
     websocket:
       url: "ws://127.0.0.1:5000/ws/events"
   ```

2. **Edita `agent/config/default.yaml`:**
   ```yaml
   server:
     ws_url: "ws://127.0.0.1:5000/ws/events"
   ```

O usa variables de entorno:
```bash
export SERVER_WS_URL="ws://127.0.0.1:5000/ws/events"
```

---

## Próximos Pasos (Opcional)

Para mayor flexibilidad, se podría:

1. **Hacer el servidor lee `server/config.yaml`** en tiempo de ejecución
2. **Crear un archivo `.env`** para sobrescribir valores de configuración
3. **Agregar un endpoint API** para consultar la configuración del servidor
