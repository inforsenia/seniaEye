#!/usr/bin/env python3
"""
Script para migrar dominios del archivo blocked_domains.txt a la base de datos.
Ejecutar: python3 migrate_domains_to_db.py
"""

import sys
from pathlib import Path

# Agregar el directorio raíz al path para importar los módulos
sys.path.insert(0, str(Path(__file__).parent.parent))

from server.database import init_db, add_blocked_domain, get_blocked_domain_list


def migrate_domains():
    """Migra dominios desde blocked_domains.txt a la base de datos."""
    
    # Inicializar la BD
    init_db()
    print("[*] Base de datos inicializada")
    
    # Ruta del archivo
    blocked_domains_file = Path(__file__).parent / "blocked_domains.txt"
    
    if not blocked_domains_file.exists():
        print(f"[!] Archivo no encontrado: {blocked_domains_file}")
        return
    
    # Leer dominios del archivo
    with open(blocked_domains_file, 'r') as f:
        file_domains = [line.strip() for line in f if line.strip()]
    
    if not file_domains:
        print("[!] El archivo está vacío")
        return
    
    print(f"[*] Encontrados {len(file_domains)} dominio(s) en el archivo")
    
    # Obtener dominios ya en la BD
    existing = get_blocked_domain_list()
    print(f"[*] Ya existen {len(existing)} dominio(s) en la BD")
    
    # Agregar nuevos dominios
    added = 0
    duplicated = 0
    
    for domain in file_domains:
        domain = domain.strip().lower()
        if not domain:
            continue
        
        if domain in existing:
            print(f"[~] Duplicado: {domain}")
            duplicated += 1
            continue
        
        success = add_blocked_domain(domain)
        if success:
            print(f"[+] Agregado: {domain}")
            added += 1
        else:
            print(f"[-] Error al agregar: {domain}")
    
    print(f"\n[✓] Migración completada:")
    print(f"    Nuevos: {added}")
    print(f"    Duplicados: {duplicated}")
    print(f"    Total en BD: {len(existing) + added}")


if __name__ == "__main__":
    migrate_domains()
