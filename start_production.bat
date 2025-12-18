@echo off
echo ==========================================
echo  INICIANDO SERVIDOR DJANGO - AGENDA
echo ==========================================

REM Ir a la carpeta del proyecto
cd /d "%~dp0"

REM Activar entorno virtual (si usas venv)
REM Descomentá SOLO si tenés venv
REM call venv\Scripts\activate

REM Levantar servidor
python manage.py runserver 0.0.0.0:8000

pause
