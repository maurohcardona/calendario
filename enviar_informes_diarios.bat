@echo off
REM Script para enviar informes pendientes diariamente
REM Este script se ejecuta automáticamente via Programador de Tareas de Windows

cd /d "C:\Users\Usuario\Documents\Mauro\calendario"

REM Ejecutar el comando de Django para procesar informes usando uv
REM --horas 0 significa que procesará todos los archivos sin esperar
uv run python manage.py procesar_informes --horas 0

REM Registrar la ejecución en un log
echo %date% %time% - Procesamiento de informes ejecutado >> informes_log.txt

pause
