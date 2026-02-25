#!/bin/bash
# Script para enviar informes pendientes diariamente
# Este script se puede programar con cron: crontab -e
# Ejemplo para ejecutar todos los días a las 8:00 hs:
# 0 8 * * * /home/mauro/Documentos/sistema_informatico/calendario/enviar_informes_diarios.sh

cd "$(dirname "$0")"

# Ejecutar el comando de Django para procesar informes usando uv
# --horas 0 significa que procesará todos los archivos sin esperar
uv run python manage.py procesar_informes --horas 0

# Registrar la ejecución en un log
echo "$(date '+%Y-%m-%d %H:%M:%S') - Procesamiento de informes ejecutado" >> informes_log.txt
