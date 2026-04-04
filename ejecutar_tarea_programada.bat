@echo off
REM ============================================
REM WRAPPER PARA TAREA PROGRAMADA
REM ============================================
REM Este script:
REM 1. Captura logs detallados de cada ejecución
REM 2. Mantiene historial acumulativo
REM 3. Facilita debugging de problemas
REM ============================================

setlocal enabledelayedexpansion

REM Obtener timestamp para log (formato: YYYYMMDD_HHMM)
set timestamp=%date:~-4,4%%date:~-7,2%%date:~-10,2%_%time:~0,2%%time:~3,2%
set timestamp=%timestamp: =0%

REM Crear directorio de logs si no existe
if not exist "logs" mkdir logs

REM Cambiar al directorio del proyecto
cd /d C:\Users\Admin\Documents\Agenda\calendario

REM Registrar inicio en historial
echo ============================================ >> logs\historial.log
echo Ejecucion iniciada: %date% %time% >> logs\historial.log
echo ============================================ >> logs\historial.log

REM Ejecutar script principal y capturar toda la salida
call enviar_informes_diarios.bat > logs\tarea_programada_%timestamp%.log 2>&1

REM Capturar código de salida
set EXIT_CODE=%ERRORLEVEL%

REM Registrar resultado en historial
if %EXIT_CODE% equ 0 (
    echo RESULTADO: EXITO ^(codigo 0^) >> logs\historial.log
) else (
    echo RESULTADO: ERROR ^(codigo %EXIT_CODE%^) >> logs\historial.log
)

echo Ejecucion finalizada: %date% %time% >> logs\historial.log
echo. >> logs\historial.log

REM Salir con el mismo código de error del script principal
exit /b %EXIT_CODE%
