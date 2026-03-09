# 📋 Resumen de Cambios - SèniaEye v2.0

## ✨ Cambios Principales Implementados

### 1️⃣ Gestión de Dominios desde Base de Datos
```
ANTES: blocked_domains.txt → Archivo estático
AHORA: SQLite (blocked_domains table) → Dinámico y sincronizable
```

### 2️⃣ API REST de Dominios (CRUD Completo)
```
GET    /api/blocked-domains
POST   /api/blocked-domains?domain=...
DELETE /api/blocked-domains/{domain}
POST   /api/blocked-domains/reload
```

### 3️⃣ Nueva Página de Gestión de Dominios
```
URL: http://servidor/domains
- Agregar dominios
- Eliminar dominios
- Ver lista completa
- Ver estadísticas (total dominios, IPs resueltas)
- Recargar y resolver dominios
```

### 4️⃣ Visualización de Eventos sin Claves
```
ANTES: {"machine_name": "LAB-01", "port": 443, "status": "active"}
AHORA: LAB-01 · 443 · active
```

---

## 📁 Archivos Modificados

### Backend Python

#### `server/database.py` ✏️
- ✅ Nueva tabla `blocked_domains`
- ✅ 8 funciones CRUD para dominios
- Líneas agregadas: ~80

#### `server/main.py` ✏️
- ✅ Imports actualizados
- ✅ Nuevos endpoints REST (4)
- ✅ Nueva función `_load_blocked_domains_from_db()`
- Líneas agregadas: ~110

### Frontend JavaScript

#### `server/static/js/utils/formatting.js` ✏️
- ✅ Nueva función `extractValuesOnly()`
- ✅ Modificación en `formatEventData()`
- Líneas agregadas: ~50

### HTML

#### `server/static/index.html` ✏️
- ✅ Enlace a `/domains` en header
- Líneas agregadas: 1

---

## 📄 Archivos Creados

### `server/static/domains.html` (390 líneas) ✨
Panel de gestión CRUD de dominios con:
- Formulario de agregar dominio
- Lista de dominios con eliminar
- Estadísticas en tiempo real
- Botón recargar/resolver
- Diseño coherente con SèniaEye

### `server/migrate_domains_to_db.py` (70 líneas) ✨
Script para migrar datos del archivo `.txt` a la BD:
```bash
python3 server/migrate_domains_to_db.py
```

### `CAMBIOS_DOMINIOS.md` (documentación) 📖
Documentación completa de todos los cambios

---

## 🔄 Flujo de Operación

### Al Iniciar el Servidor
```
1. init_db()  → Crea tablas si no existen
2. _load_blocked_domains_from_db()  → Carga y resuelve dominios
3. Dominios disponibles en /api/block-list (caché)
```

### Agregar Dominio desde Dashboard
```
Usuario Input → Validación → POST /api/blocked-domains
          ↓
      Agregar a BD → Resolver IPs → Actualizar caché
          ↓
   Mostrar IPs resueltas ✓
```

### Eliminar Dominio
```
Usuario Click "ELIMINAR" → Confirmación
          ↓
   DELETE /api/blocked-domains/{domain}
          ↓
   Eliminar de BD → Actualizar caché → Actualizar UI
```

### Recargar Dominios
```
POST /api/blocked-domains/reload
          ↓
Carga todos desde BD → Resuelve IPs → Actualiza caché
          ↓
Muestra estadísticas
```

---

## 🗄️ Esquema de Base de Datos

### Nueva Tabla: `blocked_domains`
```sql
CREATE TABLE blocked_domains (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  domain     TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX idx_blocked_domains_domain ON blocked_domains(domain);
```

### Ejemplo de Datos:
| id | domain | created_at | updated_at |
|----|--------|-----------|-----------|
| 1 | chatgpt.com | 2026-03-06 10:15:30 | 2026-03-06 10:15:30 |
| 2 | claude.ai | 2026-03-06 10:16:45 | 2026-03-06 10:16:45 |

---

## 🎯 Validaciones Implementadas

### En Cliente (JavaScript)
- ✅ Formato de dominio: `/^[a-z0-9.-]+\.[a-z]{2,}$/`
- ✅ No permite vacíos
- ✅ Confirmación antes de eliminar

### En Servidor (Python)
- ✅ Validación de formato
- ✅ Rechazo de duplicados (409 Conflict)
- ✅ Validación de objeto no nulo (404 Not Found)

---

## 🖼️ Interfaz de Dominios

```
╔═══════════════════════════════════════════════════════════════╗
║  SèniaEye  |  Gestión de Dominios Bloqueados  [ DASHBOARD ]  ║
╠════════════════════════════╦════════════════════════════════╣
║ ➕ AGREGAR DOMINIO          ║ 🔒 DOMINIOS BLOQUEADOS        ║
║ [Input: ejemplo.com] [+]   ║ ┌──────────────────────────┐  ║
║                             ║ │ chatgpt.com        ELIM  │  ║
║ 📊 ESTADÍSTICAS            ║ │ claude.ai          ELIM  │  ║
║ ┌──────────┐ ┌──────────┐  ║ │ example.com        ELIM  │  ║
║ │ DOMINIOS │ │   IPS    │  ║ │                         │  ║
║ │    3     │ │   12     │  ║ │                         │  ║
║ └──────────┘ └──────────┘  ║ └──────────────────────────┘  ║
║                             ║                                ║
║ [⟲ RECARGAR]               ║                                ║
╚════════════════════════════╩════════════════════════════════╝
```

---

## 📊 Estadísticas de Cambios

| Métrica | Valor |
|---------|-------|
| Archivos modificados | 4 |
| Archivos creados | 3 |
| Líneas de código agregado | ~700 |
| Nuevos endpoints REST | 4 |
| Nuevas funciones BD | 8 |
| Nuevas tablas BD | 1 |

---

## ✅ Checklist de Implementación

- [x] Tabla de dominios en BD
- [x] Funciones CRUD en Python
- [x] Endpoints REST API
- [x] Carga desde BD al iniciar
- [x] Página HTML de gestión
- [x] JavaScript para CRUD
- [x] Estilos CSS
- [x] Validaciones cliente/servidor
- [x] Manejo de errores
- [x] Script de migración
- [x] Documentación
- [x] Visualización de eventos (solo valores)

---

## 🚀 Próximos Pasos Opcionales

1. **Backup automático de dominios**
   - Exportar BD a JSON periódicamente

2. **Historial de cambios**
   - Nueva tabla para auditar agr/elim de dominios

3. **Búsqueda de dominios**
   - Filtro en la lista

4. **Importar múltiples dominios**
   - CSV o lista de texto

5. **Estadísticas de resoluciones**
   - Cuándo se resolvió por última vez
   - Cantidad de IPs por dominio

---

**Versión**: 2.0  
**Fecha**: 6 de març de 2026  
**Estado**: ✅ Completado  
