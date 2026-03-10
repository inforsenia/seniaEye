#!/usr/bin/env python3
"""
Script para verificar que la deduplicación de eventos de puertos está funcionando correctamente.
Ejecutar mientras el agente está corriendo.
"""

import time
import sys

def check_port_monitor_code():
    """Verificar que el código de deduplicación esté presente."""
    try:
        from agent.monitors.port_monitor import PortMonitor
        
        # Verificar que los atributos correctos existen
        if not hasattr(PortMonitor, 'DEDUP_WINDOW'):
            print("❌ FAIL: DEDUP_WINDOW no trovato")
            return False
        
        dedup_window = PortMonitor.DEDUP_WINDOW
        print(f"✅ PASS: DEDUP_WINDOW = {dedup_window}s")
        
        if dedup_window < 5:
            print(f"⚠️  WARNING: DEDUP_WINDOW muy corto ({dedup_window}s), recomendado 10s")
        
        # Verificar que el método de deduplicación existe
        if not hasattr(PortMonitor, '_deduplicate_event'):
            print("❌ FAIL: Método _deduplicate_event no trovato")
            return False
        
        print("✅ PASS: Método _deduplicate_event presente")
        
        # Verificar que event_cache existe
        monitor = PortMonitor(lambda x: None)
        if not hasattr(monitor, 'event_cache'):
            print("❌ FAIL: event_cache no trovato")
            return False
        
        print("✅ PASS: event_cache presente en instancia")
        
        return True
        
    except ImportError as e:
        print(f"❌ FAIL: No se puede importar PortMonitor: {e}")
        return False
    except Exception as e:
        print(f"❌ FAIL: Error durante verificación: {e}")
        return False


def test_deduplication_logic():
    """Test la lógica de deduplicación."""
    try:
        from agent.monitors.port_monitor import PortMonitor
        
        print("\n--- Test de Lógica de Deduplicación ---")
        
        # Crear monitor sin callback
        events_captured = []
        monitor = PortMonitor(lambda x: events_captured.append(x))
        
        # Simular eventos idénticos
        print("\n1. Generando 5 eventos IDÉNTICOS...")
        
        src_ip = "10.0.0.1"
        dst_ip = "192.168.2.33"
        port = 443
        protocol = "tcp"
        
        for i in range(5):
            is_unique = monitor._deduplicate_event(src_ip, dst_ip, port, protocol)
            status = "NUEVO" if is_unique else "DUPLICADO"
            print(f"   Evento {i+1}: {status}")
            time.sleep(0.01)  # Pequeño delay para simular paquetes reales
        
        # Verificar caché
        key = (src_ip, dst_ip, port, protocol)
        if key in monitor.event_cache:
            count = monitor.event_cache[key]["count"]
            print(f"\n✅ PASS: {count} paquetes agregados en caché")
            if count == 5:
                print("✅ PASS: Contador correcto (5)")
            else:
                print(f"❌ FAIL: Contador incorrecto (esperado 5, got {count})")
                return False
        else:
            print("❌ FAIL: Clave no trovata en caché")
            return False
        
        # Test ventana expirada
        print("\n2. Test de ventana expirada...")
        time.sleep(monitor.DEDUP_WINDOW + 0.5)
        
        is_unique = monitor._deduplicate_event(src_ip, dst_ip, port, protocol)
        if is_unique:
            print("✅ PASS: Nueva ventana detectada correctamente (después de expiración)")
        else:
            print("❌ FAIL: Nueva ventana NO detectada")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ FAIL: Error en test de lógica: {e}")
        import traceback
        traceback.print_exc()
        return False


def analyze_logs():
    """Buscar evidencia de deduplicación en logs."""
    try:
        print("\n--- Análisis de Logs ---")
        print("\nBuscando logs en agent/logs/...")
        
        from pathlib import Path
        import os
        
        # Buscar archivos de log más recientes
        logs_dir = Path("./logs")
        if not logs_dir.exists():
            logs_dir = Path("./agent/logs")
        
        if not logs_dir.exists():
            print("⚠️  No se encontró directorio de logs")
            return None
        
        # Buscar archivos .log más recientes
        log_files = sorted(logs_dir.glob("*.log"), key=os.path.getmtime, reverse=True)
        
        if not log_files:
            print("⚠️  No se encontraron archivos .log")
            return None
        
        latest_log = log_files[0]
        print(f"✅ Analizando: {latest_log}")
        
        # Buscar evidencia de deduplicación
        with open(latest_log, 'r') as f:
            lines = f.readlines()
        
        # Buscar líneas con [PORT]
        port_lines = [l for l in lines if '[PORT]' in l]
        
        if not port_lines:
            print("⚠️  No se encontraron líneas [PORT] en logs recientes")
            return None
        
        print(f"✅ Encontrados {len(port_lines)} eventos de puertos")
        
        # Contar NEW vs DUP
        new_count = sum(1 for l in port_lines if '[PORT] NEW:' in l)
        dup_count = sum(1 for l in port_lines if '[PORT] DUP:' in l)
        
        print(f"   NEW: {new_count} eventos nuevos")
        print(f"   DUP: {dup_count} eventos duplicados (NO reportados)")
        
        if dup_count > 0:
            reduction = (dup_count / (new_count + dup_count)) * 100
            print(f"   Reducción: {reduction:.1f}% de eventos evitados")
            print("✅ PASS: Deduplicación está funcionando!")
            return True
        else:
            print("⚠️  No hay eventos duplicados detectados (aún no hay tráfico?)")
            return None
        
    except Exception as e:
        print(f"⚠️  Error analizando logs: {e}")
        return None


def main():
    """Ejecutar todas las verificaciones."""
    print("=" * 60)
    print("🔍 VERIFICACIÓN DE DEDUPLICACIÓN DE EVENTOS")
    print("=" * 60)
    
    results = {}
    
    # Test 1: Verificar código
    print("\n--- Test 1: Verificar Código ---")
    results['code'] = check_port_monitor_code()
    
    if not results['code']:
        print("\n❌ CRÍTICO: El código de deduplicación NO está presente")
        print("Pasos:")
        print("  1. Verificar que port_monitor.py esté actualizado")
        print("  2. Limpiar bytecode: find . -name '*.pyc' -delete")
        print("  3. Reiniciar agente: make agent")
        sys.exit(1)
    
    # Test 2: Test lógica
    print("\n--- Test 2: Lógica de Deduplicación ---")
    results['logic'] = test_deduplication_logic()
    
    if not results['logic']:
        print("\n❌ ERROR: La lógica de deduplicación NO funciona correctamente")
        sys.exit(1)
    
    # Test 3: Analizar logs
    print("\n--- Test 3: Evidencia en Logs ---")
    results['logs'] = analyze_logs()
    
    # Resumen
    print("\n" + "=" * 60)
    print("📊 RESUMEN")
    print("=" * 60)
    
    if results['code'] and results['logic']:
        print("✅ Sistema listo para producción")
        print("\nPróximos pasos:")
        print("  1. Verificar que agente está corriendo")
        print("  2. Generar tráfico de red (ej: intentos SSH)")
        print("  3. Revisar logs: tail -f logs/*.log | grep PORT")
        print("  4. Verificar dashboard para eventos agregados")
    else:
        print("❌ Verificación falló - ver detalles arriba")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupción del usuario")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error crítico: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
