* Cada agente envía eventos por WebSocket o HTTP POST al servidor.
* El servidor almacena o procesa los eventos y llama a notify_dashboards.
      - uvicorn server.main:app --reload --host 0.0.0.0 --port 8000
            ```sh
            server.main → indica que se debe importar el módulo server/main.py.
            :app → indica que dentro de ese módulo hay una variable llamada app, que debe ser la instancia de FastAPI.
            --reload → activa recarga automática. Cada vez que guardes cambios en .py, Uvicorn reiniciará la aplicación automáticamente.
            --host 0.0.0.0 → hace que el servidor acepte conexiones desde cualquier IP (no solo localhost).
            --port 8000 → puerto donde el servidor estará escuchando.
            ```
* La clase Broadcaster envía los eventos a todos los dashboards conectados en tiempo real.
* Los dashboards actualizan la interfaz sin necesidad de refrescar la página.

Perfecto, vamos a detallar el **flujo de datos** de tu sistema de monitorización, indicando **qué archivos intervienen en cada paso**, para que quede claro cómo se conecta todo desde los agentes hasta el dashboard:


![alt text](<ChatGPT Image 23 de febr. del 2026, 12_31_29.png>)

---

## **Flujo de Datos del Sistema de Monitorización**

### 1️⃣ Generación de eventos en el agente

**Qué ocurre:**
Cada equipo del aula genera eventos sobre actividad sospechosa, como puertos no autorizados, dominios bloqueados, IPs prohibidas o nuevas interfaces de red.

**Archivos involucrados:**

* `agent/main.py` → Punto de entrada que orquesta la ejecución del agente y añade eventos a la cola.
* `agent/monitors/port_monitor.py` → Detecta intentos de conexión a puertos no permitidos.
* `agent/monitors/dns_monitor.py` → Detecta accesos a dominios bloqueados.
* `agent/monitors/ip_monitor.py` → Compara IPs de destino con la blacklist.
* `agent/monitors/interface_monitor.py` → Detecta nuevas interfaces de red.
* `agent/events/models.py` → Define la estructura de los eventos (Pydantic).
* `agent/events/queue.py` → Cola local de eventos antes de enviarlos.
* `agent/sender/ws_sender.py` → Encargado de enviar eventos al servidor vía WebSocket, gestionando reconexión y cola de reintentos.

---

### 2️⃣ Envío de eventos al servidor

**Qué ocurre:**
El agente envía los eventos generados al servidor central mediante WebSockets. Si la conexión falla, los eventos quedan en la cola local y se reintentan.

**Archivos involucrados:**

* `agent/sender/ws_sender.py` → Gestión de conexión WebSocket y envío de eventos.
* `agent/config.py` → Carga la URL del servidor y parámetros de reconexión.
* `.env` / `.env.example` → Configuración de la URL del servidor, delay de reconexión, etc.

---

### 3️⃣ Recepción de eventos en el servidor

**Qué ocurre:**
El servidor recibe los eventos desde los agentes y los procesa para almacenamiento o retransmisión al dashboard.

**Archivos involucrados:**

* `server/main.py` → Inicializa FastAPI y la instancia del `Broadcaster`.
* `server/api/routes/events.py` → Ruta `POST /events` que recibe los eventos desde los agentes.
* `shared/schemas.py` → Define la estructura de los eventos en Pydantic para validar los datos.

---

### 4️⃣ Retransmisión de eventos a los dashboards

**Qué ocurre:**
Los eventos recibidos se envían en tiempo real a todos los dashboards conectados mediante WebSockets.

**Archivos involucrados:**

* `server/ws/broadcaster.py` → Clase `Broadcaster` que mantiene las conexiones WebSocket de los dashboards y retransmite los eventos.
* `server/main.py` → Endpoint WebSocket `/ws/events` que acepta la conexión de los dashboards y los registra en `Broadcaster`.

---

### 5️⃣ Visualización en el dashboard

**Qué ocurre:**
El dashboard web recibe los eventos vía WebSocket y actualiza la interfaz de supervisión en tiempo real.

**Archivos involucrados:**

* `dashboard/app.js` → Se conecta al servidor WebSocket y actualiza la UI con los eventos.
* `dashboard/index.html` → Interfaz web del dashboard.
* `dashboard/style.css` → Estilos de la interfaz del dashboard.

---

### **Resumen gráfico del flujo de archivos**

```
[Equipo Aula] 
   └── agent/main.py
        ├── monitors/port_monitor.py
        ├── monitors/dns_monitor.py
        ├── monitors/ip_monitor.py
        ├── monitors/interface_monitor.py
        ├── events/models.py
        ├── events/queue.py
        └── sender/ws_sender.py
             │
             ▼
[Servidor Central]
   ├── server/main.py
   ├── api/routes/events.py
   └── ws/broadcaster.py
             │
             ▼
[Dashboard Web]
   ├── dashboard/app.js
   ├── dashboard/index.html
   └── dashboard/style.css
```

