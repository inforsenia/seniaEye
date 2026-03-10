# Sistema de Monitorización de Equipos en Aula para Entornos de Examen

## Descripción del Proyecto

Este proyecto tiene como objetivo desarrollar un sistema de monitorización en tiempo real de los equipos informáticos de un aula durante la realización de exámenes, con el fin de detectar comportamientos no autorizados o potencialmente fraudulentos.

El sistema supervisa la actividad de red y el estado del equipo, enviando la información recopilada a un servidor central donde los datos son procesados y visualizados para su análisis por parte del personal responsable.

---

## Objetivos

* Garantizar que los equipos solo utilicen los servicios de red autorizados.
* Detectar accesos a páginas web no permitidas.
* Identificar conexiones sospechosas mediante análisis de IPs.
* Monitorizar la conexión de nuevas interfaces de red.
* Centralizar la información para facilitar la supervisión en tiempo real.

---

## Funcionamiento General
Se programa en python.
Cada equipo del aula ejecuta un agente de monitorización que realiza las siguientes tareas:

### 1. Control de Puertos de Destino

Se supervisa el tráfico de red saliente para garantizar que únicamente se utilicen los siguientes puertos permitidos:

* **53, 853, 443** → DNS
* **80** → HTTP
* **443** → HTTPS
* **22** → SSH (en red local)

Cualquier intento de comunicación hacia otros puertos será registrado como posible infracción.

---

### 2. Análisis de Resolución DNS

El sistema inspecciona las consultas DNS realizadas por el equipo para:

* Identificar los dominios a los que se intenta acceder.
* Comparar los dominios consultados con una **blacklist predefinida** de sitios no permitidos.
* Bloqueara IP de DNS conocidos para DoH o Analizar trafico hhts a dichas Ips

---

### 3. Detección por IP de Destino

Además del análisis por nombre de dominio:

* Se analizan las IPs de destino del tráfico.
* Si un dominio pertenece a la blacklist, sus direcciones IP se obtienen dinámicamente en el momento de la monitorización.
* Se comparan las IPs de destino activas con las IPs asociadas a dominios prohibidos.

Esto permite detectar accesos incluso cuando se intenta evitar la resolución DNS tradicional.

---

### 4. Detección de Nuevas Interfaces de Red

El sistema también monitoriza cambios en las interfaces de red del equipo, con el objetivo de detectar:

* Conexión de adaptadores USB de red.
* Activación de nuevas interfaces.
* Posibles intentos de conexión no autorizada (por ejemplo, tethering).

---

## Envío de datos por parte del agente 

Los equipos disponen de un archivo de configuración YAML llamado `agent/config/default.yaml` en el que se indica la URL del servidor WebSocket y cualquier aspecto de configuración oportuno.
Realizan la conexión mediante websocket con el servidor. En caso de no poder realizarla lo vuelven a intentar 30 segundos más tarde.
---

## Recepción y visualización de datos por parte del servidor
Se realizará con una aplicación en flask.
Cuando se arranca la aplicación aceptar conexiones dinámicamente a través de websockets.

  * Se recopilada por cada equipo en un archivo los datos enviados por los agentes. Cada archivo incluye en su nombre el nombre del agente y la fecha
  * A la información almacenada se le añade la hora minuto y segundo en que se ha obtenido.
  * La información se visualiza en tiempo real
  * Identificaa posibles infracciones.
  * Analizar el comportamiento de cada equipo.


---
## Eventos Detectados

El sistema puede generar alertas ante:

* Uso de puertos no autorizados.
* Acceso a dominios incluidos en la blacklist.
* Conexión a IPs asociadas a sitios prohibidos.
* Conexión de nuevas interfaces de red.

---

## Arquitectura General

```
[Equipo Aula]
    ↓
[Agente de Monitorización]
    ↓
[Servidor Central]
    ↓
[Interfaz de Supervisión]
```

---


