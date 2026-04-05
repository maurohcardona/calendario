# Corrección de Ruta de Red para Tarea Programada

## 📋 Resumen

**Problema:** La tarea programada falla al procesar informes con error `FileNotFoundError: I:\`

**Causa:** La unidad `I:\` es un mapeo de red que NO está disponible cuando la tarea programada se ejecuta en contexto de sistema.

**Solución:** Usar ruta UNC `\\Srv-navify\informes pdf` en lugar de letra de unidad `I:\`

---

## 🔧 IMPLEMENTACIÓN EN WINDOWS

### Paso 1: Hacer Backup del .env Actual

```powershell
# En PowerShell (como Admin)
cd C:\Users\Admin\Documents\Agenda\calendario
Copy-Item .env .env.backup
```

### Paso 2: Editar el Archivo .env

**Ubicación:** `C:\Users\Admin\Documents\Agenda\calendario\.env`

**Abrir con:** Notepad, Notepad++, o cualquier editor de texto

**Buscar la línea:**
```
INFORMES_PENDIENTES_DIR = I:\
```

**Cambiar por:**
```
INFORMES_PENDIENTES_DIR = \\Srv-navify\informes pdf
```

**IMPORTANTE:**
- NO agregar `\` al final de la ruta
- NO usar comillas
- La ruta puede contener espacios (como "informes pdf")
- Guardar el archivo con codificación UTF-8

### Paso 3: Guardar y Cerrar

Guardar el archivo y cerrar el editor.

---

## ✅ VALIDACIÓN DE CAMBIOS

### Validación 1: Verificar Configuración

```powershell
cd C:\Users\Admin\Documents\Agenda\calendario

# Ver la configuración actualizada
Get-Content .env | Select-String "INFORMES_PENDIENTES_DIR"
```

**Salida esperada:**
```
INFORMES_PENDIENTES_DIR = \\Srv-navify\informes pdf
```

### Validación 2: Verificar Acceso a la Ruta UNC

```powershell
# Verificar que la ruta es accesible
Test-Path "\\Srv-navify\informes pdf"

# Ver PDFs disponibles
dir "\\Srv-navify\informes pdf\*.pdf"
```

**Salida esperada:**
```
True
[Lista de PDFs si existen]
```

### Validación 3: Ejecución Manual del Script

```batch
cd C:\Users\Admin\Documents\Agenda\calendario
.\enviar_informes_diarios.bat
```

**Verificar durante la ejecución:**
- ✅ Generando backup de la base de datos...
- ✅ Subiendo backup a Google Drive...
- ✅ Limpiando backups locales antiguos...
- ✅ Limpiando backups antiguos en Google Drive...
- ✅ Procesamiento de informes (sin errores de Python)
- ✅ Enviando notificación de ÉXITO por email...

**Verificar después:**
1. **Email recibido:** maurohcardona@gmail.com
   - Subject: `[EXITO] Backup y Procesamiento de Informes - 2026-04-XX`
   - Contenido: Debe decir "Informes procesados correctamente"

2. **Logs sin errores:**
   - Ubicación: `C:\Users\Admin\Documents\Agenda\calendario\logs\`
   - Archivo más reciente: `tarea_programada_YYYYMMDD_HHMM.log`
   - NO debe contener: "FileNotFoundError: I:\\"

3. **Backup generado:**
   - `C:\Users\Admin\Documents\backups\backup_YYYY-MM-DD.sql`
   - Tamaño: ~4.8 MB

### Validación 4: Ejecución Manual de Tarea Programada

```powershell
# Ejecutar la tarea programada manualmente
Start-ScheduledTask -TaskName "Backup BD y Procesamiento de Informes Diarios"

# Esperar 30 segundos
Start-Sleep -Seconds 30

# Verificar estado
Get-ScheduledTaskInfo -TaskName "Backup BD y Procesamiento de Informes Diarios" | Select-Object LastTaskResult, LastRunTime
```

**Verificar:**
- ✅ Email de [EXITO] recibido (no [ERROR])
- ✅ Log en `logs\` sin "FileNotFoundError"
- ✅ LastTaskResult: 0 (éxito)

---

## 🎯 RESULTADO ESPERADO

### Antes de la Corrección:
```
Ejecución Manual:              ✅ FUNCIONA (usa I:\ mapeada)
Ejecución Automática 8:00 AM:  ❌ FALLA (I:\ no disponible)
Email:                         ❌ [ERROR] Error al procesar informes de Django
Log:                           ❌ FileNotFoundError: [WinError 3] ... 'I:\\'
```

### Después de la Corrección:
```
Ejecución Manual:              ✅ FUNCIONA (usa ruta UNC)
Ejecución Automática 8:00 AM:  ✅ FUNCIONA (ruta UNC siempre disponible)
Email:                         ✅ [EXITO] Proceso completado correctamente
Log:                           ✅ Sin errores
```

---

## 📂 COMPORTAMIENTO DEL SISTEMA

### Carpetas de Lectura (Servidor de Red):
```
\\Srv-navify\informes pdf\
├── Ambulatorio_12345678_001_T001.pdf  ← Django lee PDFs desde aquí
├── Ambulatorio_87654321_002_T002.pdf
└── ...
```

### Carpetas de Escritura (Locales):
```
C:\Users\Admin\Documents\Agenda\calendario\informes\
├── enviados\        ← PDFs enviados exitosamente
├── sin_email\       ← PDFs de pacientes sin email
├── Guardia\         ← Informes de Guardia
└── Internación\     ← Informes de Internación
```

### Flujo de Procesamiento:
1. Django lee PDF desde `\\Srv-navify\informes pdf\archivo.pdf`
2. Busca paciente en base de datos
3. Envía email si tiene email registrado
4. **Mueve** el PDF a carpeta local según resultado:
   - Éxito → `informes/enviados/archivo.pdf`
   - Sin email → `informes/sin_email/archivo.pdf`
   - Otros orígenes → `informes/Guardia/` o `informes/Internación/`

**IMPORTANTE:** Los PDFs se **mueven** (no se copian), por lo que desaparecen del servidor después de procesarse.

---

## 🚨 TROUBLESHOOTING

### Error: "No se encuentra la ruta de acceso de red"

**Síntoma:**
```
[WinError 53] No se encuentra la ruta de acceso de red: '\\Srv-navify\informes pdf'
```

**Causas posibles:**
1. Servidor de red apagado o no accesible
2. Permisos insuficientes del usuario Admin
3. Firewall bloqueando acceso

**Solución:**
```powershell
# Verificar conectividad al servidor
ping Srv-navify

# Verificar acceso a carpeta compartida
net view \\Srv-navify

# Intentar acceder manualmente
explorer.exe "\\Srv-navify\informes pdf"
```

### Error: "Acceso denegado"

**Síntoma:**
```
[WinError 5] Acceso denegado: '\\Srv-navify\informes pdf'
```

**Causa:** Usuario Admin no tiene permisos en la carpeta de red

**Solución:**
1. Contactar administrador de red/sistemas
2. Solicitar permisos de Lectura y Modificación para usuario Admin
3. Verificar permisos: `icacls "\\Srv-navify\informes pdf"`

### Los PDFs No Se Procesan

**Verificar:**
1. ¿Existen PDFs en `\\Srv-navify\informes pdf\`?
   ```powershell
   dir "\\Srv-navify\informes pdf\*.pdf"
   ```

2. ¿Los PDFs tienen el formato correcto?
   - Formato esperado: `Ambulatorio_DNI_NumOrden_NumProtocolo.pdf`
   - Ejemplo: `Ambulatorio_12345678_001_T001.pdf`

3. ¿Los PDFs tienen antigüedad suficiente?
   - Por defecto: 0 horas (se procesan inmediatamente)
   - Ver línea 119 en `enviar_informes_diarios.bat`: `--horas 0`

---

## 📅 PRÓXIMA EJECUCIÓN AUTOMÁTICA

**Fecha:** 6 de abril de 2026  
**Hora:** 08:00 AM  
**Qué esperar:**

1. La tarea programada se ejecutará automáticamente
2. Recibirás email de [EXITO] (si todo funciona correctamente)
3. Los logs se guardarán en: `C:\Users\Admin\Documents\Agenda\calendario\logs\`

**Monitoreo:**
- Revisar email en maurohcardona@gmail.com después de las 8:00 AM
- Si no llega email, revisar logs manualmente
- Si el email dice [ERROR], revisar el log para detalles del error

---

## 📞 SOPORTE

Si después de seguir todos estos pasos el problema persiste:

1. **Recopilar información:**
   - Log más reciente en `logs\tarea_programada_YYYYMMDD_HHMM.log`
   - Email de error completo
   - Resultado de `net use I:`
   - Resultado de `Test-Path "\\Srv-navify\informes pdf"`

2. **Restaurar configuración anterior (si es necesario):**
   ```powershell
   cd C:\Users\Admin\Documents\Agenda\calendario
   Copy-Item .env.backup .env
   ```

---

## ✅ CHECKLIST DE IMPLEMENTACIÓN

- [ ] Backup del archivo .env realizado
- [ ] Archivo .env modificado (I:\ → \\Srv-navify\informes pdf)
- [ ] Validación 1: Configuración verificada
- [ ] Validación 2: Acceso UNC verificado
- [ ] Validación 3: Ejecución manual exitosa
- [ ] Validación 4: Tarea programada manual exitosa
- [ ] Email de [EXITO] recibido
- [ ] Logs sin errores verificados
- [ ] Esperando ejecución automática del 6 de abril

---

**Fecha de implementación:** 5 de abril de 2026  
**Implementado por:** Usuario Admin  
**Última actualización:** 5 de abril de 2026
