# Script de Validación de Configuración de Rutas de Red
# Verifica que la configuración de INFORMES_PENDIENTES_DIR esté correcta

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "VALIDACIÓN DE CONFIGURACIÓN - RUTAS DE RED" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

$ErrorCount = 0
$WarningCount = 0
$ProjectDir = "C:\Users\Admin\Documents\Agenda\calendario"
$EnvFile = "$ProjectDir\.env"

# ==========================================
# VALIDACIÓN 1: Archivo .env existe
# ==========================================
Write-Host "1. Verificando archivo .env..." -ForegroundColor Yellow

if (Test-Path $EnvFile) {
    Write-Host "   ✓ Archivo .env encontrado" -ForegroundColor Green
} else {
    Write-Host "   ✗ ERROR: Archivo .env no encontrado en $EnvFile" -ForegroundColor Red
    $ErrorCount++
    Write-Host ""
    Write-Host "Presiona Enter para salir..."
    Read-Host
    exit 1
}

# ==========================================
# VALIDACIÓN 2: Leer configuración INFORMES_PENDIENTES_DIR
# ==========================================
Write-Host "2. Leyendo configuración INFORMES_PENDIENTES_DIR..." -ForegroundColor Yellow

$InformesDirLine = Get-Content $EnvFile | Select-String "INFORMES_PENDIENTES_DIR"

if ($InformesDirLine) {
    $InformesDir = ($InformesDirLine -split "=", 2)[1].Trim()
    Write-Host "   Valor configurado: $InformesDir" -ForegroundColor White
    
    # Verificar si usa I:\ (incorrecto)
    if ($InformesDir -like "I:\*") {
        Write-Host "   ✗ ERROR: Todavía usa la unidad I:\" -ForegroundColor Red
        Write-Host "   → Cambiar a: \\Srv-navify\informes pdf" -ForegroundColor Yellow
        $ErrorCount++
    }
    # Verificar si usa ruta UNC (correcto)
    elseif ($InformesDir -like "\\*") {
        Write-Host "   ✓ Usa ruta UNC (correcto)" -ForegroundColor Green
    }
    # Verificar si usa ruta relativa (aceptable)
    elseif ($InformesDir -notlike "*:*") {
        Write-Host "   ✓ Usa ruta relativa (aceptable)" -ForegroundColor Green
    }
    else {
        Write-Host "   ⚠ ADVERTENCIA: Formato de ruta no reconocido" -ForegroundColor Yellow
        $WarningCount++
    }
} else {
    Write-Host "   ⚠ ADVERTENCIA: Variable INFORMES_PENDIENTES_DIR no encontrada" -ForegroundColor Yellow
    Write-Host "   → Se usará valor por defecto del proyecto" -ForegroundColor Gray
    $InformesDir = "$ProjectDir\informes\pendientes"
    $WarningCount++
}

Write-Host ""

# ==========================================
# VALIDACIÓN 3: Verificar acceso a la ruta configurada
# ==========================================
Write-Host "3. Verificando acceso a la ruta configurada..." -ForegroundColor Yellow

if (Test-Path $InformesDir) {
    Write-Host "   ✓ Ruta accesible: $InformesDir" -ForegroundColor Green
    
    # Contar PDFs en la carpeta
    $PdfCount = (Get-ChildItem -Path $InformesDir -Filter "*.pdf" -ErrorAction SilentlyContinue).Count
    Write-Host "   → PDFs encontrados: $PdfCount" -ForegroundColor Gray
} else {
    Write-Host "   ✗ ERROR: No se puede acceder a la ruta: $InformesDir" -ForegroundColor Red
    $ErrorCount++
}

Write-Host ""

# ==========================================
# VALIDACIÓN 4: Verificar acceso a servidor de red
# ==========================================
Write-Host "4. Verificando acceso al servidor de red..." -ForegroundColor Yellow

$NetworkPath = "\\Srv-navify\informes pdf"

if (Test-Path $NetworkPath) {
    Write-Host "   ✓ Servidor de red accesible: $NetworkPath" -ForegroundColor Green
    
    # Verificar permisos de escritura
    $TestFile = "$NetworkPath\test_permisos_$(Get-Date -Format 'yyyyMMdd_HHmmss').txt"
    try {
        "Test" | Out-File -FilePath $TestFile -ErrorAction Stop
        Remove-Item $TestFile -ErrorAction SilentlyContinue
        Write-Host "   ✓ Permisos de escritura: OK" -ForegroundColor Green
    } catch {
        Write-Host "   ✗ ERROR: Sin permisos de escritura" -ForegroundColor Red
        $ErrorCount++
    }
} else {
    Write-Host "   ✗ ERROR: No se puede acceder al servidor de red" -ForegroundColor Red
    Write-Host "   → Verificar conectividad: ping Srv-navify" -ForegroundColor Yellow
    $ErrorCount++
}

Write-Host ""

# ==========================================
# VALIDACIÓN 5: Verificar unidad I:\ (diagnóstico)
# ==========================================
Write-Host "5. Diagnóstico de unidad I:\..." -ForegroundColor Yellow

$NetUseOutput = net use I: 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "   ℹ Unidad I:\ está mapeada (uso manual OK)" -ForegroundColor Cyan
    $NetUseOutput | Select-String "Nombre remoto" | ForEach-Object {
        Write-Host "   → $_" -ForegroundColor Gray
    }
} else {
    Write-Host "   ℹ Unidad I:\ no está mapeada actualmente" -ForegroundColor Cyan
}

Write-Host ""

# ==========================================
# VALIDACIÓN 6: Verificar estructura de carpetas locales
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
        Write-Host "   ✓ Carpeta existe: $(Split-Path $dir -Leaf)" -ForegroundColor Green
    } else {
        Write-Host "   ⚠ Carpeta no existe (se creará automáticamente): $(Split-Path $dir -Leaf)" -ForegroundColor Yellow
        $WarningCount++
    }
}

Write-Host ""

# ==========================================
# VALIDACIÓN 7: Verificar logs de ejecuciones previas
# ==========================================
Write-Host "7. Verificando logs de ejecuciones previas..." -ForegroundColor Yellow

$LogsDir = "$ProjectDir\logs"
if (Test-Path $LogsDir) {
    $LatestLog = Get-ChildItem -Path $LogsDir -Filter "tarea_programada_*.log" -ErrorAction SilentlyContinue | 
                 Sort-Object LastWriteTime -Descending | 
                 Select-Object -First 1
    
    if ($LatestLog) {
        Write-Host "   ✓ Log más reciente: $($LatestLog.Name)" -ForegroundColor Green
        Write-Host "   → Fecha: $($LatestLog.LastWriteTime)" -ForegroundColor Gray
        
        # Buscar errores en el log
        $LogContent = Get-Content $LatestLog.FullName -Raw
        if ($LogContent -match "FileNotFoundError.*I:\\") {
            Write-Host "   ✗ Log contiene error de I:\ (requiere corrección)" -ForegroundColor Red
            $ErrorCount++
        } elseif ($LogContent -match "ERROR") {
            Write-Host "   ⚠ Log contiene errores (revisar manualmente)" -ForegroundColor Yellow
            $WarningCount++
        } else {
            Write-Host "   ✓ Log sin errores detectados" -ForegroundColor Green
        }
    } else {
        Write-Host "   ℹ No se encontraron logs de ejecuciones previas" -ForegroundColor Cyan
    }
} else {
    Write-Host "   ℹ Carpeta de logs no existe (se creará en primera ejecución)" -ForegroundColor Cyan
}

Write-Host ""

# ==========================================
# RESUMEN FINAL
# ==========================================
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "RESUMEN DE VALIDACIÓN" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

if ($ErrorCount -eq 0 -and $WarningCount -eq 0) {
    Write-Host "✅ CONFIGURACIÓN CORRECTA" -ForegroundColor Green
    Write-Host ""
    Write-Host "Todas las validaciones pasaron exitosamente." -ForegroundColor White
    Write-Host "El sistema está listo para ejecutarse automáticamente." -ForegroundColor White
} elseif ($ErrorCount -eq 0) {
    Write-Host "⚠️  CONFIGURACIÓN ACEPTABLE CON ADVERTENCIAS" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Advertencias encontradas: $WarningCount" -ForegroundColor Yellow
    Write-Host "El sistema debería funcionar, pero revisa las advertencias." -ForegroundColor White
} else {
    Write-Host "❌ CONFIGURACIÓN INCORRECTA" -ForegroundColor Red
    Write-Host ""
    Write-Host "Errores encontrados: $ErrorCount" -ForegroundColor Red
    Write-Host "Advertencias: $WarningCount" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Por favor, corrige los errores antes de ejecutar la tarea programada." -ForegroundColor White
}

Write-Host ""
Write-Host "Para más detalles, consulta: CORRECCION_RUTA_RED.md" -ForegroundColor Gray
Write-Host ""
Write-Host "Presiona Enter para salir..."
Read-Host
