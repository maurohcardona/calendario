@echo on
echo ====================================
echo Iniciando Agenda en modo produccion
echo ====================================
echo.
echo Servidor: http://192.168.1.250:8000
echo.

echo Estoy en:
cd

cd /d C:\Users\Admin\Documents\Agenda\calendario
echo Cambio de carpeta OK

echo Probando Python:
py --version

echo Lanzando waitress...
py -m waitress --listen=0.0.0.0:8000 Agenda.wsgi:application


echo FIN DEL SCRIPT
pause
