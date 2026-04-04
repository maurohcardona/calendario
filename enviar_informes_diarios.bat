@echo off
REM ============================================================
REM Script: Backup diario PostgreSQL + Google Drive + Notificacion
REM ============================================================

setlocal EnableDelayedExpansion

REM ==========================================
REM CONFIGURACION
REM ==========================================
set "PG_BIN=C:\Program Files\PostgreSQL\17\bin"
set "DB_NAME=laboratorio2"
set "DB_USER=postgres"
set "BACKUP_DIR=C:\Users\Admin\Documents\backups"
set "GDRIVE_FOLDER=backups_db"
set "NOTIFY_EMAIL=maurohcardona@gmail.com"
set "DIAS_RETENCION=30"
set "PROYECTO_DIR=C:\Users\Admin\Documents\Agenda\calendario"
set "ENV_FILE=%PROYECTO_DIR%\.env"

REM ==========================================
REM LEER CONTRASEÑA DE POSTGRESQL DESDE .env
REM ==========================================
for /f "tokens=1,* delims==" %%a in ('type "%ENV_FILE%" ^| findstr /i "DB_PASSWORD"') do set "PGPASSWORD=%%b"
REM Limpiar espacios y comillas
set "PGPASSWORD=%PGPASSWORD: =%"
set "PGPASSWORD=%PGPASSWORD:"=%"

REM ==========================================
REM LEER CREDENCIALES SMTP DESDE .env
REM ==========================================
for /f "tokens=1,* delims==" %%a in ('type "%ENV_FILE%" ^| findstr /i "SMTP_HOST"') do set "SMTP_SERVER=%%b"
for /f "tokens=1,* delims==" %%a in ('type "%ENV_FILE%" ^| findstr /i "SMTP_PORT"') do set "SMTP_PORT=%%b"
for /f "tokens=1,* delims==" %%a in ('type "%ENV_FILE%" ^| findstr /i "SENDER_EMAIL"') do set "SMTP_EMAIL=%%b"
for /f "tokens=1,* delims==" %%a in ('type "%ENV_FILE%" ^| findstr /i "SENDER_PASSWORD"') do set "SMTP_PASSWORD=%%b"

REM Limpiar espacios y comillas
set "SMTP_SERVER=%SMTP_SERVER: =%"
set "SMTP_PORT=%SMTP_PORT: =%"
set "SMTP_EMAIL=%SMTP_EMAIL: =%"
set "SMTP_PASSWORD=%SMTP_PASSWORD: =%"
set "SMTP_SERVER=%SMTP_SERVER:"=%"
set "SMTP_EMAIL=%SMTP_EMAIL:"=%"
set "SMTP_PASSWORD=%SMTP_PASSWORD:"=%"

REM ==========================================
REM GENERAR NOMBRE DE ARCHIVO CON FECHA
REM ==========================================
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set datetime=%%I
set "BACKUP_DATE=%datetime:~0,4%-%datetime:~4,2%-%datetime:~6,2%"
set "BACKUP_FILE=backup_%BACKUP_DATE%.sql"
set "BACKUP_PATH=%BACKUP_DIR%\%BACKUP_FILE%"
set "LOG_FILE=%BACKUP_DIR%\backup_log.txt"

REM Crear directorio si no existe
if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

REM Variable para rastrear errores
set "HAY_ERROR=0"
set "MENSAJE_ERROR="

echo ============================================ >> "%LOG_FILE%"
echo %date% %time% - Iniciando backup >> "%LOG_FILE%"

REM ==========================================
REM PASO 1: GENERAR BACKUP POSTGRESQL
REM ==========================================
echo Generando backup de la base de datos...
"%PG_BIN%\pg_dump" -U %DB_USER% -F p %DB_NAME% > "%BACKUP_PATH%" 2>> "%LOG_FILE%"

if %ERRORLEVEL% NEQ 0 (
    set "HAY_ERROR=1"
    set "MENSAJE_ERROR=Error al generar backup de PostgreSQL"
    echo %date% %time% - ERROR: !MENSAJE_ERROR! >> "%LOG_FILE%"
    goto :notificar
)

REM Verificar que el archivo no este vacio
for %%A in ("%BACKUP_PATH%") do set "BACKUP_SIZE=%%~zA"
if "%BACKUP_SIZE%"=="0" (
    set "HAY_ERROR=1"
    set "MENSAJE_ERROR=El archivo de backup esta vacio"
    echo %date% %time% - ERROR: !MENSAJE_ERROR! >> "%LOG_FILE%"
    goto :notificar
)

echo %date% %time% - Backup generado: %BACKUP_FILE% (%BACKUP_SIZE% bytes) >> "%LOG_FILE%"

REM ==========================================
REM PASO 2: SUBIR A GOOGLE DRIVE
REM ==========================================
echo Subiendo backup a Google Drive...
rclone copy "%BACKUP_PATH%" gdrive:%GDRIVE_FOLDER%/ 2>> "%LOG_FILE%"

if %ERRORLEVEL% NEQ 0 (
    set "HAY_ERROR=1"
    set "MENSAJE_ERROR=Error al subir backup a Google Drive"
    echo %date% %time% - ERROR: !MENSAJE_ERROR! >> "%LOG_FILE%"
    goto :notificar
)

echo %date% %time% - Backup subido a Google Drive: %GDRIVE_FOLDER%/%BACKUP_FILE% >> "%LOG_FILE%"

REM ==========================================
REM PASO 3: LIMPIAR BACKUPS ANTIGUOS
REM ==========================================
echo Limpiando backups locales antiguos...
forfiles /p "%BACKUP_DIR%" /m backup_*.sql /d -%DIAS_RETENCION% /c "cmd /c del @path && echo Eliminado: @file >> \"%LOG_FILE%\"" 2>nul

echo Limpiando backups antiguos en Google Drive...
rclone delete gdrive:%GDRIVE_FOLDER%/ --min-age %DIAS_RETENCION%d 2>> "%LOG_FILE%"

echo %date% %time% - Limpieza completada >> "%LOG_FILE%"

REM ==========================================
REM PASO 4: PROCESAMIENTO DE INFORMES DJANGO
REM ==========================================
cd /d "%PROYECTO_DIR%"
"C:\Users\Admin\.local\bin\uv.exe" run python manage.py procesar_informes --horas 0 2>> "%LOG_FILE%"

if %ERRORLEVEL% NEQ 0 (
    set "HAY_ERROR=1"
    set "MENSAJE_ERROR=Error al procesar informes de Django"
    echo %date% %time% - ERROR: !MENSAJE_ERROR! >> "%LOG_FILE%"
    goto :notificar
)

echo %date% %time% - Procesamiento de informes completado >> "%LOG_FILE%"
echo %date% %time% - BACKUP COMPLETADO EXITOSAMENTE >> "%LOG_FILE%"
REM Ir a notificar siempre (exito o error)
goto :notificar

REM ==========================================
REM NOTIFICACION POR EMAIL (SIEMPRE)
REM ==========================================
:notificar
REM Determinar tipo de notificacion
if "%HAY_ERROR%"=="1" (
    echo Enviando notificacion de ERROR por email...
    set "EMAIL_SUBJECT=[ERROR] Backup y Procesamiento de Informes - %BACKUP_DATE%"
    set "EMAIL_PRIORITY=High"
    set "EMAIL_BODY=Se produjo un error durante el proceso automatico.`n`nFecha: %date% %time%`nError: !MENSAJE_ERROR!`nServidor: %COMPUTERNAME%`nBase de datos: %DB_NAME%`n`nPor favor, revisa el log en: %LOG_FILE%"
) else (
    echo Enviando notificacion de EXITO por email...
    set "EMAIL_SUBJECT=[EXITO] Backup y Procesamiento de Informes - %BACKUP_DATE%"
    set "EMAIL_PRIORITY=Normal"
    set "EMAIL_BODY=El proceso automatico se ejecuto exitosamente:`n`n=== BACKUP POSTGRESQL ===`nBase de datos: %DB_NAME%`nArchivo: %BACKUP_FILE%`nTamano: %BACKUP_SIZE% bytes`nUbicacion local: %BACKUP_DIR%`n`n=== GOOGLE DRIVE ===`nSubido exitosamente a: %GDRIVE_FOLDER%/`nBackups antiguos eliminados (^>%DIAS_RETENCION% dias)`n`n=== PROCESAMIENTO DE INFORMES ===`nInformes procesados correctamente`n`n=== DETALLES ===`nFecha: %date%`nHora: %time%`nServidor: %COMPUTERNAME%`n`n---`nMensaje automatico del sistema de backups"
)

REM Crear script PowerShell temporal para enviar email
set "PS_SCRIPT=%TEMP%\send_email.ps1"

(
echo $smtpServer = "%SMTP_SERVER%"
echo $smtpPort = %SMTP_PORT%
echo $smtpUser = "%SMTP_EMAIL%"
echo $smtpPass = "%SMTP_PASSWORD%"
echo $to = "%NOTIFY_EMAIL%"
echo $subject = "!EMAIL_SUBJECT!"
echo $priority = "!EMAIL_PRIORITY!"
echo $body = "!EMAIL_BODY!"
echo $securePass = ConvertTo-SecureString $smtpPass -AsPlainText -Force
echo $cred = New-Object System.Management.Automation.PSCredential^($smtpUser, $securePass^)
echo Send-MailMessage -From $smtpUser -To $to -Subject $subject -Body $body -SmtpServer $smtpServer -Port $smtpPort -UseSsl -Credential $cred -Priority $priority -Encoding UTF8
) > "%PS_SCRIPT%"

powershell -ExecutionPolicy Bypass -File "%PS_SCRIPT%" 2>> "%LOG_FILE%"

if %ERRORLEVEL% EQU 0 (
    echo %date% %time% - Notificacion enviada a %NOTIFY_EMAIL% >> "%LOG_FILE%"
) else (
    echo %date% %time% - ERROR al enviar notificacion por email >> "%LOG_FILE%"
)

del "%PS_SCRIPT%" 2>nul
echo ============================================ >> "%LOG_FILE%"

:fin
endlocal
pause
