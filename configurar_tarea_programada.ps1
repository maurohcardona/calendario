#Requires -RunAsAdministrator

<#
.SYNOPSIS
    Configura tarea programada para backup y procesamiento de informes diarios
    
.DESCRIPTION
    Crea una tarea en el Programador de Tareas de Windows que ejecuta
    enviar_informes_diarios.bat todos los días a las 8:00 AM
    
    La tarea:
    - Se ejecuta diariamente a las 8:00 AM
    - Funciona aunque el usuario no esté logueado
    - Tiene privilegios elevados para acceder a PostgreSQL y rclone
    - Reintentar 3 veces si falla (cada 10 minutos)
    - Envía notificación por email siempre (éxito y error)
    
.NOTES
    - Debe ejecutarse con privilegios de Administrador
    - Requiere que el script ejecutar_tarea_programada.bat exista
    - Solicitará la contraseña del usuario Admin
    
.EXAMPLE
    .\configurar_tarea_programada.ps1
    Crea la tarea programada con configuración por defecto
#>

# ==========================================
# CONFIGURACION
# ==========================================
$TaskName = "Backup BD y Procesamiento de Informes Diarios"
$TaskDescription = "Ejecuta backup de PostgreSQL, procesa informes PDF y envía emails diariamente a las 8:00 AM"
$ScriptPath = "C:\Users\Admin\Documents\Agenda\calendario\ejecutar_tarea_programada.bat"
$WorkingDir = "C:\Users\Admin\Documents\Agenda\calendario"
$ExecutionTime = "08:00"
$UserName = "Admin"

# ==========================================
# BANNER INICIAL
# ==========================================
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "CONFIGURACIÓN DE TAREA PROGRAMADA" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "📝 Nombre: $TaskName" -ForegroundColor Yellow
Write-Host "📂 Script: $ScriptPath" -ForegroundColor Yellow
Write-Host "⏰ Hora: $ExecutionTime (diaria)" -ForegroundColor Yellow
Write-Host "👤 Usuario: $UserName" -ForegroundColor Yellow
Write-Host ""

# ==========================================
# VALIDACIONES
# ==========================================
# Verificar que se ejecuta como Administrador
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "❌ ERROR: Este script debe ejecutarse como Administrador" -ForegroundColor Red
    Write-Host ""
    Write-Host "Por favor:" -ForegroundColor Yellow
    Write-Host "  1. Cierra esta ventana de PowerShell" -ForegroundColor White
    Write-Host "  2. Clic derecho en PowerShell > 'Ejecutar como administrador'" -ForegroundColor White
    Write-Host "  3. Ejecuta nuevamente: .\configurar_tarea_programada.ps1" -ForegroundColor White
    Write-Host ""
    Read-Host "Presiona Enter para salir"
    exit 1
}

# Verificar que el script existe
if (-not (Test-Path $ScriptPath)) {
    Write-Host "❌ ERROR: No se encuentra el script en $ScriptPath" -ForegroundColor Red
    Write-Host ""
    Write-Host "Por favor verifica:" -ForegroundColor Yellow
    Write-Host "  - Que el archivo ejecutar_tarea_programada.bat existe" -ForegroundColor White
    Write-Host "  - Que la ruta es correcta" -ForegroundColor White
    Write-Host ""
    Read-Host "Presiona Enter para salir"
    exit 1
}

Write-Host "✓ Script encontrado: $ScriptPath" -ForegroundColor Green
Write-Host ""

# ==========================================
# ELIMINAR TAREA EXISTENTE (SI EXISTE)
# ==========================================
$ExistingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($ExistingTask) {
    Write-Host "⚠️  Tarea existente encontrada. ¿Deseas reemplazarla? (S/N): " -ForegroundColor Yellow -NoNewline
    $Response = Read-Host
    
    if ($Response -eq 'S' -or $Response -eq 's') {
        Write-Host "Eliminando tarea anterior..." -ForegroundColor Gray
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "✓ Tarea anterior eliminada" -ForegroundColor Green
        Write-Host ""
    } else {
        Write-Host "Operación cancelada por el usuario" -ForegroundColor Yellow
        exit 0
    }
}

# ==========================================
# CREAR COMPONENTES DE LA TAREA
# ==========================================
Write-Host "Configurando tarea programada..." -ForegroundColor Cyan
Write-Host ""

# 1. Acción (qué ejecutar)
$Action = New-ScheduledTaskAction `
    -Execute $ScriptPath `
    -WorkingDirectory $WorkingDir

Write-Host "✓ Acción configurada: ejecutar $ScriptPath" -ForegroundColor Green

# 2. Trigger (cuándo ejecutar)
$Trigger = New-ScheduledTaskTrigger `
    -Daily `
    -At $ExecutionTime

Write-Host "✓ Trigger configurado: diariamente a las $ExecutionTime" -ForegroundColor Green

# 3. Settings (configuraciones avanzadas)
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -DontStopOnIdleEnd `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 10)

Write-Host "✓ Configuraciones avanzadas establecidas:" -ForegroundColor Green
Write-Host "  - Ejecutar incluso con batería" -ForegroundColor Gray
Write-Host "  - Iniciar si se perdió una ejecución programada" -ForegroundColor Gray
Write-Host "  - Timeout: 2 horas máximo" -ForegroundColor Gray
Write-Host "  - Reintentar 3 veces cada 10 minutos si falla" -ForegroundColor Gray

# ==========================================
# SOLICITAR CREDENCIALES
# ==========================================
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "AUTENTICACIÓN REQUERIDA" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Se necesita la contraseña del usuario '$UserName' para:" -ForegroundColor Yellow
Write-Host "  ✓ Ejecutar la tarea aunque no esté logueado" -ForegroundColor White
Write-Host "  ✓ Acceder a PostgreSQL con privilegios" -ForegroundColor White
Write-Host "  ✓ Usar rclone para subir a Google Drive" -ForegroundColor White
Write-Host ""
Write-Host "La contraseña se almacenará de forma SEGURA y ENCRIPTADA" -ForegroundColor Gray
Write-Host "en el Programador de Tareas de Windows." -ForegroundColor Gray
Write-Host ""

$Credential = Get-Credential -UserName $UserName -Message "Ingrese la contraseña del usuario $UserName"

if (-not $Credential) {
    Write-Host ""
    Write-Host "❌ ERROR: Credenciales no proporcionadas. Abortando." -ForegroundColor Red
    Write-Host ""
    Read-Host "Presiona Enter para salir"
    exit 1
}

# 4. Principal (usuario que ejecuta)
$Principal = New-ScheduledTaskPrincipal `
    -UserId $Credential.UserName `
    -LogonType Password `
    -RunLevel Highest

Write-Host ""
Write-Host "✓ Credenciales recibidas correctamente" -ForegroundColor Green

# ==========================================
# REGISTRAR TAREA
# ==========================================
Write-Host ""
Write-Host "Registrando tarea en el sistema..." -ForegroundColor Cyan

try {
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Description $TaskDescription `
        -Action $Action `
        -Trigger $Trigger `
        -Settings $Settings `
        -Principal $Principal `
        -User $Credential.UserName `
        -Password $Credential.GetNetworkCredential().Password `
        -Force | Out-Null
    
    Write-Host ""
    Write-Host "============================================" -ForegroundColor Green
    Write-Host "✅ TAREA CREADA EXITOSAMENTE" -ForegroundColor Green
    Write-Host "============================================" -ForegroundColor Green
    Write-Host ""
    
    # Obtener información de la tarea
    $Task = Get-ScheduledTask -TaskName $TaskName
    $NextRun = (Get-ScheduledTaskInfo -TaskName $TaskName).NextRunTime
    
    # Mostrar detalles
    Write-Host "📋 DETALLES DE LA TAREA:" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Nombre:" -ForegroundColor White -NoNewline
    Write-Host " $TaskName" -ForegroundColor Yellow
    Write-Host "  Horario:" -ForegroundColor White -NoNewline
    Write-Host " Todos los días a las $ExecutionTime" -ForegroundColor Yellow
    Write-Host "  Script:" -ForegroundColor White -NoNewline
    Write-Host " $ScriptPath" -ForegroundColor Yellow
    Write-Host "  Usuario:" -ForegroundColor White -NoNewline
    Write-Host " $UserName (privilegios elevados)" -ForegroundColor Yellow
    Write-Host "  Reintentos:" -ForegroundColor White -NoNewline
    Write-Host " 3 intentos cada 10 minutos si falla" -ForegroundColor Yellow
    Write-Host "  Timeout:" -ForegroundColor White -NoNewline
    Write-Host " 2 horas máximo" -ForegroundColor Yellow
    Write-Host "  Notificación:" -ForegroundColor White -NoNewline
    Write-Host " Email siempre (éxito y error)" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "⏰ PRÓXIMA EJECUCIÓN:" -ForegroundColor Cyan
    Write-Host "  $NextRun" -ForegroundColor Yellow
    Write-Host ""
    
    # Información útil
    Write-Host "📖 INFORMACIÓN ÚTIL:" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Ver la tarea:" -ForegroundColor White
    Write-Host "    → Abrir 'Programador de tareas'" -ForegroundColor Gray
    Write-Host "    → Biblioteca del Programador de tareas" -ForegroundColor Gray
    Write-Host "    → Buscar: $TaskName" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  Ejecutar manualmente:" -ForegroundColor White
    Write-Host "    → Clic derecho en la tarea > 'Ejecutar'" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  Ver historial:" -ForegroundColor White
    Write-Host "    → Propiedades de la tarea > Pestaña 'Historial'" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  Ver logs:" -ForegroundColor White
    Write-Host "    → $WorkingDir\logs\" -ForegroundColor Gray
    Write-Host "    → C:\Users\Admin\Documents\backups\backup_log.txt" -ForegroundColor Gray
    Write-Host ""
    
    # Exportar configuración a XML
    $ExportPath = "$WorkingDir\tarea_programada_backup.xml"
    Export-ScheduledTask -TaskName $TaskName | Out-File $ExportPath -Encoding UTF8
    Write-Host "💾 Configuración exportada a:" -ForegroundColor Cyan
    Write-Host "  $ExportPath" -ForegroundColor Yellow
    Write-Host "  (Puedes usar este archivo para restaurar la tarea)" -ForegroundColor Gray
    Write-Host ""
    
    # Preguntar si desea ejecutar prueba
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host "¿EJECUTAR PRUEBA AHORA?" -ForegroundColor Cyan
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "¿Deseas ejecutar la tarea AHORA para probar que funciona? (S/N): " -ForegroundColor Yellow -NoNewline
    $Response = Read-Host
    
    if ($Response -eq 'S' -or $Response -eq 's') {
        Write-Host ""
        Write-Host "Ejecutando tarea de prueba..." -ForegroundColor Cyan
        Write-Host ""
        Start-ScheduledTask -TaskName $TaskName
        Write-Host "✓ Tarea iniciada" -ForegroundColor Green
        Write-Host ""
        Write-Host "Revisa:" -ForegroundColor Yellow
        Write-Host "  • Logs en: $WorkingDir\logs\" -ForegroundColor White
        Write-Host "  • Email de notificación en: maurohcardona@gmail.com" -ForegroundColor White
        Write-Host "  • Backup generado en: C:\Users\Admin\Documents\backups\" -ForegroundColor White
        Write-Host ""
    } else {
        Write-Host ""
        Write-Host "La tarea se ejecutará automáticamente a las $ExecutionTime" -ForegroundColor Green
        Write-Host ""
    }
    
    Write-Host "============================================" -ForegroundColor Green
    Write-Host "✅ CONFIGURACIÓN COMPLETADA" -ForegroundColor Green
    Write-Host "============================================" -ForegroundColor Green
    Write-Host ""
    
} catch {
    Write-Host ""
    Write-Host "============================================" -ForegroundColor Red
    Write-Host "❌ ERROR AL CREAR LA TAREA" -ForegroundColor Red
    Write-Host "============================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    Write-Host "Posibles soluciones:" -ForegroundColor Yellow
    Write-Host "  1. Verifica que ejecutaste PowerShell como Administrador" -ForegroundColor White
    Write-Host "  2. Verifica que la contraseña del usuario es correcta" -ForegroundColor White
    Write-Host "  3. Verifica que el archivo .bat existe en la ruta especificada" -ForegroundColor White
    Write-Host ""
    Read-Host "Presiona Enter para salir"
    exit 1
}

Read-Host "Presiona Enter para salir"
