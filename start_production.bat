@echo off
title Django Agenda - Produccion

echo =========================================
echo  INICIANDO SERVIDOR DJANGO - AGENDA
echo =========================================
echo.

REM Ir al proyecto
cd /d C:\Users\Admin\Documents\Agenda\calendario

REM Usar SIEMPRE el python del venv correcto
REM C:\Users\Admin\Documents\Agenda\calendario\.venv\Scripts\python.exe -m waitress --listen=0.0.0.0:8000 Agenda.wsgi:application
C:\Users\Admin\Documents\Agenda\calendario\.venv\Scripts\python.exe start_waitress.py
pause
