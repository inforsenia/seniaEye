# Especificación de Formatos de Configuración

## 📋 Estándar Adoptado: YAML

Este proyecto usa **YAML** como formato único para todos los archivos de configuración.

---

## 📁 Archivos de Configuración

### 1. Servidor

| Archivo | Formato | Propósito | Ubicación |
|---------|---------|----------|----------|
| `server/config.yaml` | YAML | Configuración central del servidor | `server/` |
| `server/allowed_ports_config.yaml` | YAML | Reglas de puertos permitidos | `server/` |

### 2. Agente

| Archivo | Formato | Propósito | Ubicación |
|---------|---------|----------|----------|
| `agent/config/default.yaml` | YAML | Configuración central del agente | `agent/config/` |

---

## ✅ Por qué YAML

1. **Legibilidad**: Sintaxis clara y fácil de entender
2. **Consistencia**: Un único formato para todo el proyecto
3. **Flexibilidad**: Soporta estructuras complejas (listas, objetos anidados)
4. **Estándar industrial**: Ampliamente usado en DevOps y proyectos modernos
5. **Parsing sencillo**: `yaml.safe_load()` en Python es simple y seguro

---

## 🏗️ Estructura Recomendada para Nuevos Archivos

### Plantilla Básica

```yaml
# ============================================================================
# TÍTULO DEL COMPONENTE - CONFIGURACIÓN
# ============================================================================
# Descripción breve del propósito del archivo.
# ============================================================================

component:
  setting1: value1
  setting2: value2
  nested:
    setting3: value3
```

### Ejemplo: Nuevo Monitor

```yaml
# ============================================================================
# NUEVO MONITOR - CONFIGURACIÓN
# ============================================================================
# Configuración para el nuevo monitor de ejemplo.
# ============================================================================

monitor:
  enabled: true
  interval: 60
  
  connection:
    host: "127.0.0.1"
    port: 1984
    timeout: 30
  
  logging:
    level: "INFO"
    file: "logs/monitor.log"
```

---

## 📝 Reglas de Estilo YAML

### 1. Indentación
```yaml
# ✅ CORRECTO: 2 espacios
server:
  host: "0.0.0.0"
  port: 1984

# ❌ INCORRECTO: Usar tabs o 4 espacios
server:
    host: "0.0.0.0"
    port: 1984
```

### 2. Comentarios de Sección
```yaml
# ============================================================================
# SECCIÓN IMPORTANTE
# ============================================================================
```

### 3. Strings con Comillas
```yaml
# ✅ CORRECTO: Comillas simples o dobles para claridad
url: "ws://127.0.0.1:1984/events"
path: 'C:\Windows\Path'

# ⚠️ Opcional para valores simples
log_level: INFO
```

### 4. Listas
```yaml
# ✅ CORRECTO: Array style
allowed_sources:
  - "192.168.0.0/16"
  - "10.0.0.0/8"
  - "127.0.0.1"

# O inline para valores simples
tags: ["production", "monitoring"]
```

### 5. Nulos y Booleanos
```yaml
# ✅ CORRECTO
empty_value: null
enabled: true
disabled: false

# ❌ EVITAR
empty_value: ~
enabled: yes
disabled: no
```

---

## 🔄 Cargar Configuración en Python

### Patrón Estándar

```python
import yaml
from pathlib import Path

def load_config(config_file: str) -> dict:
    """Load YAML configuration file."""
    config_path = Path(config_file)
    
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    return config or {}

# Uso
config = load_config("server/config.yaml")
server_config = config.get("server", {})
host = server_config.get("host", "0.0.0.0")
port = server_config.get("port", 1984)
```

---

## 📦 Dependencias Requeridas

Asegúrate de que `requirements.txt` incluya:

```
PyYAML>=6.0
```

Para instalar:
```bash
pip install PyYAML
```

---

## 🚀 Migración de Formatos Anteriores

Si hay archivos `.conf`, `.ini` u otro formato que necesiten migración a YAML:

1. **Convertir manualmente** al formato YAML
2. **Actualizar el código** para usar `yaml.safe_load()` en lugar de `configparser`
3. **Actualizar documentación** que haga referencia al formato anterior
4. **Eliminar archivos antiguos** una vez migrado todo

---

## 📋 Checklist para Nuevas Configuraciones

Al crear un nuevo archivo de configuración:

- [ ] Usar extensión `.yaml`
- [ ] Iniciar con comentario de sección `# ============================================================================`
- [ ] Usar indentación de 2 espacios
- [ ] Incluir comentarios explicativos para valores importantes
- [ ] Usar `null` para valores nulos, no `~`
- [ ] Actualizar este documento si el patrón es diferente
- [ ] Actualizar código de carga de configuración si es necesario
- [ ] Documentar en el README o guía de configuración

---

## 📚 Referencias

- [YAML Specification](https://yaml.org/spec/1.2/spec.html)
- [PyYAML Documentation](https://pyyaml.org/)
- [YAML Best Practices](https://macsisive.wordpress.com/2015/06/07/yaml-best-practices/)
