# Cambios Realizados - Sistema de Dominios Bloqueados

## Resumen de Modificaciones

Se han implementado las siguientes mejoras al proyecto SèniaEye:

### 1. **Gestión de Dominios desde Base de Datos** ✅
Los dominios bloqueados ahora se cargan y gestionan desde la base de datos SQLite, en lugar de desde un archivo de texto.

#### Cambios en `server/database.py`:
- **Nueva tabla `blocked_domains`**: Almacena los dominios bloqueados con timestamps de creación y actualización
- **Nuevas funciones CRUD**:
  - `add_blocked_domain(domain)`: Agrega un nuevo dominio
  - `remove_blocked_domain(domain)`: Elimina un dominio
  - `list_blocked_domains()`: Lista todos los dominios con metadatos
  - `get_blocked_domain_list()`: Obtiene solo los strings de dominios
  - `domain_exists(domain)`: Verifica disponibilidad
  - `clear_all_blocked_domains()`: Limpia todos los dominios

#### Cambios en `server/main.py`:
- **Nueva función `_load_blocked_domains_from_db()`**: Carga dominios desde BD en el inicio
- **Nueva función `_resolve_domains()`**: Resuelve dominios a IPs

### 2. **API REST para Gestión de Dominios** ✅

Se han agregado nuevos endpoints en `server/main.py`:

```
GET  /api/blocked-domains              → Lista todos los dominios de la BD
POST /api/blocked-domains              → Agrega un nuevo dominio
DELETE /api/blocked-domains/{domain}   → Elimina un dominio
POST /api/blocked-domains/reload       → Recarga todos los dominios y los resuelve
```

#### Respuestas esperadas:

**POST /api/blocked-domains?domain=example.com**
```json
{
  "success": true,
  "domain": "example.com",
  "ips": ["1.2.3.4", "1.2.3.5"],
  "timestamp": "2026-03-06 10:30:45"
}
```

**GET /api/blocked-domains**
```json
{
  "timestamp": "2026-03-06 10:30:45",
  "domains": [
    {"id": 1, "domain": "example.com", "created_at": "...", "updated_at": "..."},
    {"id": 2, "domain": "test.com", "created_at": "...", "updated_at": "..."}
  ],
  "total": 2
}
```

### 3. **Interfaz CRUD en Dashboard** ✅

Nueva página web `server/static/domains.html` con interfaz completa para:
- ➕ **Agregar dominios**: Input con validación de formato (regex)
- 🔒 **Lista de dominios**: Tabla con eliminar individual
- 📊 **Estadísticas**: Contador de dominios y IPs resueltas
- ⟲ **Recarga**: Botón para resolver todos los dominios

**Características**:
- Validación de formato de dominio
- Confirmación antes de eliminar
- Mensajes toast para feedback del usuario
- Diseño consistente con el resto de la aplicación
- Carga automática de dominios al iniciar

**Acceso**: `/domains` (también hay enlace en el header del dashboard)

### 4. **Visualización de Eventos Mejorada** ✅

Modificación en `server/static/js/utils/formatting.js`:

- **Nueva función `extractValuesOnly()`**: Extrae solo los valores de los datos del evento, ignorando las claves
- **Modificación `formatEventData()`**: Implementa la nueva lógica de visualización

#### Antes:
```
{"machine_name": "LAB-01", "event": "connection", "port": 443}
```

#### Después:
```
LAB-01 · connection · 443
```

**Comportamiento**:
- Para objetos: Une los valores con " · " (punto centrado)
- Para arrays: Une los elementos con ", " (comas)
- Filtra valores nulos, indefinidos y vacíos automáticamente
- Maneja objetos anidados recursivamente
- Preserva el almacenamiento completo en BD (sin cambios)

---

## Scripts de Utilidad

### `server/migrate_domains_to_db.py`
Script para migrar los dominios existentes en `blocked_domains.txt` a la base de datos.

**Uso**:
```bash
cd /home/j.garciabenlloch/Documents/seniaEye
python3 server/migrate_domains_to_db.py
```

**Output esperado**:
```
[*] Base de datos inicializada
[*] Encontrados 2 dominio(s) en el archivo
[*] Ya existen 0 dominio(s) en la BD
[+] Agregado: chatgpt.com
[+] Agregado: claude.ai

[✓] Migración completada:
    Nuevos: 2
    Duplicados: 0
    Total en BD: 2
```

---

## Flujo de Trabajo

### Inicialización del Servidor
1. Al iniciar, `main.py` llama a `init_db()` (crea tablas si no existen)
2. Luego llama a `_load_blocked_domains_from_db()` para cargar y resolver dominios
3. Los dominios se almacenan en memoria en `resolved_domains` para acceso rápido
4. El endpoint `/api/block-list` sigue disponible para consultar el caché

### Agregar un Dominio desde la Dashboard
1. Usuario entra a `/domains`
2. Ingresa dominio y presiona "AGREGAR"
3. Validación en cliente (formato)
4. POST a `/api/blocked-domains?domain=...`
5. El servidor:
   - Valida el dominio
   - Lo agrega a la BD
   - Lo resuelve a IPs
   - Actualiza el caché `resolved_domains`
   - Retorna las IPs resueltas
6. Se actualiza la lista en la UI

### Eliminar un Dominio
1. Usuario presiona ELIMINAR en la lista
2. Confirmación (popup)
3. DELETE a `/api/blocked-domains/{domain}`
4. El servidor elimina de BD y del caché
5. Se actualiza la lista

### Recargar Dominios
1. Usuario presiona ⟲ RECARGAR
2. POST a `/api/blocked-domains/reload`
3. El servidor recarga todos desde BD, resuelve IPs
4. Actualiza estadísticas y caché
5. Se mostran las nuevas IPs resueltas

---

## Cambios en Archivos Existentes

### `server/database.py`
- Agregada tabla `blocked_domains` al esquema
- 8 nuevas funciones CRUD para dominios
- Total: +80 líneas

### `server/main.py`
- Imports actualizados para incluir funciones de dominios
- Función `_load_blocked_domains()` reemplazada por `_load_blocked_domains_from_db()`
- Nueva función `_resolve_domains()`
- 4 nuevos endpoints REST
- Link a `/domains` en el header
- Total: +110 líneas

### `server/static/js/utils/formatting.js`
- Nueva función `extractValuesOnly()`
- Función `formatEventData()` modificada
- Total: +50 líneas

### `server/static/index.html`
- Enlace `<a href="/domains" class="nav-btn">🔒 DOMINIOS</a>` agregado al header

---

## Archivos Nuevos

1. **`server/static/domains.html`** (390 líneas)
   - Interfaz CRUD completa para dominios
   - Estilos coherentes con el diseño de SèniaEye
   - Manejo de errores y feedback visual

2. **`server/migrate_domains_to_db.py`** (70 líneas)
   - Script de migración de datos
   - Detecta duplicados automáticamente
   - Reporte detallado

---

## Base de Datos

### Tabla `blocked_domains`
```sql
CREATE TABLE blocked_domains (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  domain      TEXT    NOT NULL UNIQUE,
  created_at  TEXT    NOT NULL,
  updated_at  TEXT    NOT NULL
);

CREATE INDEX idx_blocked_domains_domain ON blocked_domains(domain);
```

### Datos Existentes
Los dominios actuales en `blocked_domains.txt` se pueden migrar ejecutando:
```bash
python3 server/migrate_domains_to_db.py
```

---

## Consideraciones Técnicas

1. **Thread-Safety**: Se mantiene el lock global de SQLite para operaciones concurrentes
2. **Resolución de DNS**: Se cachea en memoria para evitar resoluciones repetidas
3. **Validación**: Se valida en cliente (regex) y servidor (duplicados)
4. **Tratamiento de Errores**: Se retornan códigos HTTP apropiados (409 para duplicados, 404 para no encontrado)
5. **Datos Completos**: La BD almacena todos los datos del evento, solo la visualización cambia

---

## Testing Recomendado

### 1. Migración
```bash
python3 server/migrate_domains_to_db.py
```

### 2. Endpoints API
```bash
# Listar dominios
curl http://localhost:8000/api/blocked-domains

# Agregar dominio
curl -X POST "http://localhost:8000/api/blocked-domains?domain=example.com"

# Eliminar dominio
curl -X DELETE "http://localhost:8000/api/blocked-domains/example.com"

# Recargar
curl -X POST http://localhost:8000/api/blocked-domains/reload
```

### 3. Dashboard
1. Acceder a `http://localhost:8000/domains`
2. Agregar dominio
3. Verificar en lista
4. Eliminar
5. Verificar desaparece

### 4. Visualización de Eventos
1. Observar un evento en el dashboard
2. Los datos deben mostrar solo valores, sin claves

---

## Compatibilidad

- ✅ Base de datos SQLite existente se actualiza automáticamente
- ✅ Archivo `blocked_domains.txt` se mantiene (se puede usar como respaldo)
- ✅ API anterior `/api/block-list` sigue funcionando igual
- ✅ Dashboard existente no se ve afectado (solo se agrega botón)
- ✅ Eventos se almacenan completos en BD (-sin cambios-)

---

**Versión**: 1.0  
**Fecha**: 6 de març de 2026  
**Autor**: Implementación automatizada
