#!/usr/bin/env python
"""
Script para ejecutar el procesamiento de informes médicos
Compatible con Windows y Linux

Uso:
    python ejecutar_procesamiento.py
    python ejecutar_procesamiento.py --horas 48
"""
import os
import sys
import subprocess
from pathlib import Path

def main():
    # Detectar el directorio del script
    script_dir = Path(__file__).parent.absolute()
    os.chdir(script_dir)
    
    # Detectar el ejecutable de Python del venv
    if sys.platform == 'win32':
        python_exe = script_dir / '.venv' / 'Scripts' / 'python.exe'
    else:
        python_exe = script_dir / '.venv' / 'bin' / 'python'
    
    # Verificar que existe
    if not python_exe.exists():
        print(f"❌ Error: No se encontró Python en {python_exe}")
        print("   Asegúrate de que el entorno virtual esté creado.")
        sys.exit(1)
    
    # Construir el comando
    cmd = [str(python_exe), 'manage.py', 'procesar_informes']
    
    # Pasar argumentos adicionales si los hay
    if len(sys.argv) > 1:
        cmd.extend(sys.argv[1:])
    
    # Ejecutar el comando
    try:
        result = subprocess.run(cmd, capture_output=False, text=True)
        sys.exit(result.returncode)
    except Exception as e:
        print(f"❌ Error al ejecutar: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
