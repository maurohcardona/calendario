@echo off
title Django Agenda - Produccion

echo =========================================
echo  INICIANDO SERVIDOR DJANGO - AGENDA
echo =========================================
echo.

REM Ir al proyecto
cd /d C:\Users\Admin\Documents\Agenda\calendario

REM Usar SIEMPRE el python del venv correcto
C:\Users\Admin\Documents\Agenda\calendario\.venv\Scripts\python.exe -m waitress --listen=0.0.0.0:8000 Agenda.wsgi:application

pause
