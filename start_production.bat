@echo off
echo ====================================
echo Iniciando Agenda en modo produccion
echo ====================================
echo.
echo Servidor: http://192.168.1.250:8000
echo.
cd C:\Users\LABORATORIO\Documents\Agenda\Agenda
python -m waitress --listen=192.168.1.250:8000 Agenda.wsgi:application
