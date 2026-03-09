# 🚀 Guía de Uso - Gestión de Dominios Bloqueados

## 📍 Acceso a la Interfaz

### Opción 1: Desde el Dashboard Principal
1. Accede a `http://localhost:8000/` (Dashboard principal)
2. En el header superior derecho, haz clic en **🔒 DOMINIOS**
3. Se abrirá la página de gestión

### Opción 2: Acceso Directo
- Dirección: `http://localhost:8000/domains`

---

## 💻 Operaciones Disponibles

### ➕ Agregar un Dominio Bloqueado

**Pasos:**
1. En el campo "AGREGAR DOMINIO", escribe el nombre del dominio (ej: `ejemplo.com`)
2. Presiona **AGREGAR** o usa Enter
3. El sistema:
   - ✅ Valida el formato
   - ✅ Verifica que no exista
   - ✅ Lo agrega a la BD
   - ✅ Resuelve el dominio a IPs
   - ✅ Actualiza la lista

**Formatos válidos:**
- `example.com` ✅
- `sub.example.com` ✅
- `test.co.uk` ✅

**Formatos inválidos:**
- `example` ❌ (falta extensión)
- `example.` ❌ (punto incompleto)
- `.com` ❌ (vacío)

### 🗑️ Eliminar un Dominio

**Pasos:**
1. En la lista de "DOMINIOS BLOQUEADOS", busca el dominio
2. Presiona el botón **ELIMINAR** de ese dominio
3. Confirma la eliminación en el popup
4. El sistema:
   - ✅ Elimina de la BD
   - ✅ Actualiza el caché
   - ✅ Refresca la lista

### 📋 Ver Lista de Dominios

**La lista muestra:**
- Nombre del dominio
- Fecha de creación
- Botón para eliminar

**Nota:** La lista se actualiza automáticamente al agregar/eliminar dominios

### 📊 Ver Estadísticas

**Panel de Estadísticas:**
- **DOMINIOS TOTAL**: Cantidad de dominios en la BD
- **IPS RESUELTAS**: Total de direcciones IP a bloquear

**Actualización:** Se actualiza en tiempo real

### ⟲ Recargar y Resolver Dominios

**Pasos:**
1. Presiona el botón **⟲ RECARGAR**
2. El sistema:
   - ✅ Lee todos los dominios de la BD
   - ✅ Resuelve cada dominio a IPs (mediante `dig`)
   - ✅ Actualiza el caché del servidor
   - ✅ Muestra las nuevas estadísticas

**Cuándo usar:**
- Después de agregar nuevos dominios
- Si cambiaron las IPs de los dominios
- Para sincronizar cambios hechos en otra sesión

---

## 🔧 API REST (Para Programadores)

### Endpoints Disponibles

#### 1. Listar Dominios
```bash
curl http://localhost:8000/api/blocked-domains
```

**Respuesta:**
```json
{
  "timestamp": "2026-03-06 10:30:45",
  "domains": [
    {
      "id": 1,
      "domain": "alertsites.com",
      "created_at": "2026-03-06 10:15:30",
      "updated_at": "2026-03-06 10:15:30"
    }
  ],
  "total": 1
}
```

#### 2. Agregar Dominio
```bash
curl -X POST "http://localhost:8000/api/blocked-domains?domain=example.com"
```

**Respuesta (éxito):**
```json
{
  "success": true,
  "domain": "example.com",
  "ips": ["93.184.216.34"],
  "timestamp": "2026-03-06 10:35:20"
}
```

**Respuesta (error - duplicado):**
```json
{
  "detail": "Domain example.com already exists"
}
```

#### 3. Eliminar Dominio
```bash
curl -X DELETE "http://localhost:8000/api/blocked-domains/example.com"
```

**Respuesta:**
```json
{
  "success": true,
  "deleted_domain": "example.com",
  "timestamp": "2026-03-06 10:40:15"
}
```

#### 4. Recargar Todos
```bash
curl -X POST "http://localhost:8000/api/blocked-domains/reload"
```

**Respuesta:**
```json
{
  "success": true,
  "total_domains": 3,
  "total_ips": 12,
  "timestamp": "2026-03-06 10:45:00"
}
```

---

## 📈 Migración desde Archivo

### Importar Dominios Existentes

Si ya tienes dominios en `server/blocked_domains.txt`, puedes migrarlos:

```bash
cd /home/j.garciabenlloch/Documents/seniaEye
python3 server/migrate_domains_to_db.py
```

**Output esperado:**
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

## ⚠️ Casos Especiales

### ¿Qué pasa si no se resuelve un dominio?

- El dominio se agrega a la BD correctamente
- Pero el campo de IPs resueltas estará vacío
- Se mostrará un mensaje informativo
- Puedes hacer clic en ⟲ RECARGAR más tarde

**Motivos comunes:**
- Dominio no existe
- Sin conexión a Internet
- Servidor DNS no disponible

### ¿Cómo sincronizar cambios entre múltiples usuarios?

1. Un usuario agrega/elimina un dominio
2. Otro usuario presiona ⟲ RECARGAR
3. Se carga la versión más reciente de BD

### ¿Se pierden los dominios si reinicio el servidor?

**NO** - Los dominios se guardan en la BD SQLite (`server/seniaeye.db`)

Al reiniciar:
- La BD se mantiene
- Los dominios se cargan automáticamente
- El caché se reconstruye

---

## 🔍 Visualización de Eventos

### Formato Antiguo (Antes)
```
{
  "machine_name": "LAB-01",
  "event_type": "port_scan",
  "port": 443,
  "status": "active"
}
```

### Formato Nuevo (Ahora)
```
LAB-01 · port_scan · 443 · active
```

**Beneficios:**
- ✅ Más legible
- ✅ Menos desorden visual
- ✅ Los datos completos aún se guardan en BD
- ✅ Puedes ver detalles en la BD si lo necesitas

---

## 🐛 Solución de Problemas

### "Error: Dominio inválido"
- Verifica el formato del dominio
- Debe tener al menos 2 partes (ej: `dominio.com`)
- Usa solo letras, números, puntos y guiones

### "Error: Dominio ya existe"
- El dominio ya está en la lista
- Si quieres actualizarlo, elimina primero y agrega de nuevo

### "No se resolvió a IPs"
- Comprueba que el dominio exista
- Verifica conexión a Internet
- Intenta hacer clic en ⟲ RECARGAR

### "La lista no se actualiza"
- Recarga la página (F5 o Cmd+R)
- Verifica que los cambios están en la BD
- Abre las herramientas de desarrollador (F12) para ver errores

---

## 💡 Consejos Prácticos

1. **Agrupa dominios relacionados**
   - Agrégalos por categoría (redes sociales, IA, etc.)

2. **Verifica antes de agregar**
   - Copia exactamente el dominio que quieres bloquear

3. **Usa el botón recargar regularmente**
   - Si los dominios cambian de IP, así se actualizan

4. **Respalda la BD periódicamente**
   - Haz copias de `server/seniaeye.db`

5. **Observa los eventos en el dashboard**
   - Verifica que los bloques funcionan correctamente

---

## 📞 Soporte

Para reportar problemas o sugerencias:

1. Revisa la sección de "Solución de Problemas" arriba
2. Comprueba los logs del servidor en `/logs/`
3. Verifica la consola del navegador (F12)

---

**Última actualización**: 6 de março de 2026  
**Versión**: 2.0
