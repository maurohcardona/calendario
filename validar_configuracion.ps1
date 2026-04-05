# Script de Validacion de Configuracion de Rutas de Red
# Verifica que la configuracion de INFORMES_PENDIENTES_DIR este correcta

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "VALIDACION DE CONFIGURACION - RUTAS DE RED" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

$ErrorCount = 0
$WarningCount = 0
$ProjectDir = "C:\Users\Admin\Documents\Agenda\calendario"
$EnvFile = "$ProjectDir\.env"

# ==========================================
# VALIDACION 1: Archivo .env existe
# ==========================================
Write-Host "1. Verificando archivo .env..." -ForegroundColor Yellow

if (Test-Path $EnvFile) {
    Write-Host "   [OK] Archivo .env encontrado" -ForegroundColor Green
} else {
    Write-Host "   [ERROR] Archivo .env no encontrado en $EnvFile" -ForegroundColor Red
    $ErrorCount++
    Write-Host ""
    Write-Host "Presiona Enter para salir..."
    Read-Host
    exit 1
}

# ==========================================
# VALIDACION 2: Leer configuracion INFORMES_PENDIENTES_DIR
# ==========================================
Write-Host "2. Leyendo configuracion INFORMES_PENDIENTES_DIR..." -ForegroundColor Yellow

$InformesDirLine = Get-Content $EnvFile | Select-String "INFORMES_PENDIENTES_DIR"

if ($InformesDirLine) {
    $InformesDir = ($InformesDirLine -split "=", 2)[1].Trim()
    Write-Host "   Valor configurado: $InformesDir" -ForegroundColor White
    
    # Verificar si usa I:\ (incorrecto)
    if ($InformesDir -like "I:\*") {
        Write-Host "   [ERROR] Todavia usa la unidad I:\" -ForegroundColor Red
        Write-Host "   -> Cambiar a: \\Srv-navify\informes pdf" -ForegroundColor Yellow
        $ErrorCount++
    }
    # Verificar si usa ruta UNC (correcto)
    elseif ($InformesDir -like "\\*") {
        Write-Host "   [OK] Usa ruta UNC (correcto)" -ForegroundColor Green
    }
    # Verificar si usa ruta relativa (aceptable)
    elseif ($InformesDir -notlike "*:*") {
        Write-Host "   [OK] Usa ruta relativa (aceptable)" -ForegroundColor Green
    }
    else {
        Write-Host "   [WARN] Formato de ruta no reconocido" -ForegroundColor Yellow
        $WarningCount++
    }
} else {
    Write-Host "   [WARN] Variable INFORMES_PENDIENTES_DIR no encontrada" -ForegroundColor Yellow
    Write-Host "   -> Se usara valor por defecto del proyecto" -ForegroundColor Gray
    $InformesDir = "$ProjectDir\informes\pendientes"
    $WarningCount++
}

Write-Host ""

# ==========================================
# VALIDACION 3: Verificar acceso a la ruta configurada
# ==========================================
Write-Host "3. Verificando acceso a la ruta configurada..." -ForegroundColor Yellow

if (Test-Path $InformesDir) {
    Write-Host "   [OK] Ruta accesible: $InformesDir" -ForegroundColor Green
    
    # Contar PDFs en la carpeta
    $PdfCount = (Get-ChildItem -Path $InformesDir -Filter "*.pdf" -ErrorAction SilentlyContinue).Count
    Write-Host "   -> PDFs encontrados: $PdfCount" -ForegroundColor Gray
} else {
    Write-Host "   [ERROR] No se puede acceder a la ruta: $InformesDir" -ForegroundColor Red
    $ErrorCount++
}

Write-Host ""

# ==========================================
# VALIDACION 4: Verificar acceso a servidor de red
# ==========================================
Write-Host "4. Verificando acceso al servidor de red..." -ForegroundColor Yellow

$NetworkPath = "\\Srv-navify\informes pdf"

if (Test-Path $NetworkPath) {
    Write-Host "   [OK] Servidor de red accesible: $NetworkPath" -ForegroundColor Green
    
    # Verificar permisos de escritura
    $TestFile = "$NetworkPath\test_permisos_$(Get-Date -Format 'yyyyMMdd_HHmmss').txt"
    try {
        "Test" | Out-File -FilePath $TestFile -ErrorAction Stop
        Remove-Item $TestFile -ErrorAction SilentlyContinue
        Write-Host "   [OK] Permisos de escritura: OK" -ForegroundColor Green
    } catch {
        Write-Host "   [ERROR] Sin permisos de escritura" -ForegroundColor Red
        $ErrorCount++
    }
} else {
    Write-Host "   [ERROR] No se puede acceder al servidor de red" -ForegroundColor Red
    Write-Host "   -> Verificar conectividad: ping Srv-navify" -ForegroundColor Yellow
    $ErrorCount++
}

Write-Host ""

# ==========================================
# VALIDACION 5: Verificar unidad I:\ (diagnostico)
# ==========================================
Write-Host "5. Diagnostico de unidad I:\..." -ForegroundColor Yellow

$NetUseOutput = net use I: 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "   [INFO] Unidad I:\ esta mapeada (uso manual OK)" -ForegroundColor Cyan
    $NetUseOutput | Select-String "Nombre remoto" | ForEach-Object {
        Write-Host "   -> $_" -ForegroundColor Gray
    }
} else {
    Write-Host "   [INFO] Unidad I:\ no esta mapeada actualmente" -ForegroundColor Cyan
}

Write-Host ""

# ==========================================
# VALIDACION 6: Verificar estructura de carpetas locales
# ==========================================
Write-Host "6. Verificando estructura de carpetas locales..." -ForegroundColor Yellow

$RequiredDirs = @(
    "$ProjectDir\informes\enviados",
    "$ProjectDir\informes\sin_email",
    "$ProjectDir\informes\Guardia",
    "$ProjectDir\informes\Internación"
)

foreach ($dir in $RequiredDirs) {
    if (Test-Path $dir) {
        Write-Host "   [OK] Carpeta existe: $(Split-Path $dir -Leaf)" -ForegroundColor Green
    } else {
        Write-Host "   [WARN] Carpeta no existe (se creara automaticamente): $(Split-Path $dir -Leaf)" -ForegroundColor Yellow
        $WarningCount++
    }
}

Write-Host ""

# ==========================================
# VALIDACION 7: Verificar logs de ejecuciones previas
# ==========================================
Write-Host "7. Verificando logs de ejecuciones previas..." -ForegroundColor Yellow

$LogsDir = "$ProjectDir\logs"
if (Test-Path $LogsDir) {
    $LatestLog = Get-ChildItem -Path $LogsDir -Filter "tarea_programada_*.log" -ErrorAction SilentlyContinue | 
                 Sort-Object LastWriteTime -Descending | 
                 Select-Object -First 1
    
    if ($LatestLog) {
        Write-Host "   [OK] Log mas reciente: $($LatestLog.Name)" -ForegroundColor Green
        Write-Host "   -> Fecha: $($LatestLog.LastWriteTime)" -ForegroundColor Gray
        
        # Buscar errores en el log
        $LogContent = Get-Content $LatestLog.FullName -Raw
        if ($LogContent -match "FileNotFoundError.*I:\\") {
            Write-Host "   [ERROR] Log contiene error de I:\ (requiere correccion)" -ForegroundColor Red
            $ErrorCount++
        } elseif ($LogContent -match "ERROR") {
            Write-Host "   [WARN] Log contiene errores (revisar manualmente)" -ForegroundColor Yellow
            $WarningCount++
        } else {
            Write-Host "   [OK] Log sin errores detectados" -ForegroundColor Green
        }
    } else {
        Write-Host "   [INFO] No se encontraron logs de ejecuciones previas" -ForegroundColor Cyan
    }
} else {
    Write-Host "   [INFO] Carpeta de logs no existe (se creara en primera ejecucion)" -ForegroundColor Cyan
}

Write-Host ""

# ==========================================
# RESUMEN FINAL
# ==========================================
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "RESUMEN DE VALIDACION" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

if ($ErrorCount -eq 0 -and $WarningCount -eq 0) {
    Write-Host "[OK] CONFIGURACION CORRECTA" -ForegroundColor Green
    Write-Host ""
    Write-Host "Todas las validaciones pasaron exitosamente." -ForegroundColor White
    Write-Host "El sistema esta listo para ejecutarse automaticamente." -ForegroundColor White
} elseif ($ErrorCount -eq 0) {
    Write-Host "[WARN] CONFIGURACION ACEPTABLE CON ADVERTENCIAS" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Advertencias encontradas: $WarningCount" -ForegroundColor Yellow
    Write-Host "El sistema deberia funcionar, pero revisa las advertencias." -ForegroundColor White
} else {
    Write-Host "[ERROR] CONFIGURACION INCORRECTA" -ForegroundColor Red
    Write-Host ""
    Write-Host "Errores encontrados: $ErrorCount" -ForegroundColor Red
    Write-Host "Advertencias: $WarningCount" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Por favor, corrige los errores antes de ejecutar la tarea programada." -ForegroundColor White
}

Write-Host ""
Write-Host "Para mas detalles, consulta: CORRECCION_RUTA_RED.md" -ForegroundColor Gray
Write-Host ""
Write-Host "Presiona Enter para salir..."
Read-Host
