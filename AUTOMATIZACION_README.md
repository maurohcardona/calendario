# Automatización de Backups e Informes Diarios

## 📋 Descripción

Sistema automatizado que ejecuta diariamente a las **8:00 AM**:
1. **Backup de PostgreSQL** (base de datos `laboratorio2`)
2. **Subida a Google Drive** (carpeta `backups_db`)
3. **Limpieza de backups antiguos** (>30 días)
4. **Procesamiento de informes PDF**
5. **Envío de emails** a pacientes
6. **Notificación por email** del resultado (éxito o error)

---

## 🚀 Instalación Rápida

### En Windows (PC de Producción)

1. **Actualizar código desde GitHub**:
   ```bash
   cd C:\Users\Admin\Documents\Agenda\calendario
   git pull origin main
   ```

2. **Ejecutar script de configuración como Administrador**:
   - Clic derecho en PowerShell → "Ejecutar como administrador"
   - Ejecutar:
     ```powershell
     cd C:\Users\Admin\Documents\Agenda\calendario
     .\configurar_tarea_programada.ps1
     ```

3. **Ingresar contraseña** cuando se solicite (usuario Admin)

4. **Opcionalmente ejecutar prueba** cuando pregunte

¡Listo! La tarea programada está configurada.

---

## 📂 Estructura de Archivos

```
calendario/
├── enviar_informes_diarios.bat         # Script principal
├── ejecutar_tarea_programada.bat       # Wrapper con logs
├── configurar_tarea_programada.ps1     # Instalador de tarea
├── tarea_programada_backup.xml         # Exportación de config (auto-generado)
└── logs/                                # Directorio de logs
    ├── tarea_programada_YYYYMMDD_HHMM.log  # Log de cada ejecución
    └── historial.log                        # Historial acumulativo
```

---

## ⚙️ Configuración

### Horario de Ejecución

**Actual**: Todos los días a las **8:00 AM**

**Cambiar horario**:
1. Editar `configurar_tarea_programada.ps1` línea 29:
   ```powershell
   $ExecutionTime = "08:00"  # Cambiar a hora deseada (ej: "23:00")
   ```
2. Re-ejecutar el script de configuración

**O cambiar desde GUI**:
1. Abrir "Programador de tareas"
2. Buscar tarea: "Backup BD y Procesamiento de Informes Diarios"
3. Propiedades → Desencadenadores → Editar → Cambiar hora

---

### Notificaciones por Email

**Destinatario**: `maurohcardona@gmail.com`

**Cambiar destinatario**:
Editar `enviar_informes_diarios.bat` línea 16:
```batch
set "NOTIFY_EMAIL=nuevo_email@ejemplo.com"
```

**Tipo de notificaciones**:
- ✅ **Éxito**: Email con resumen de backup y estadísticas
- ❌ **Error**: Email con detalles del error

---

### Retención de Backups

**Actual**: **30 días** (local y Google Drive)

**Cambiar retención**:
Editar `enviar_informes_diarios.bat` línea 17:
```batch
set "DIAS_RETENCION=30"  # Cambiar a días deseados
```

---

## 🔍 Monitoreo y Logs

### Ver Logs de Ejecuciones

**Log individual** (cada ejecución):
```
C:\Users\Admin\Documents\Agenda\calendario\logs\tarea_programada_YYYYMMDD_HHMM.log
```

**Historial acumulativo**:
```
C:\Users\Admin\Documents\Agenda\calendario\logs\historial.log
```

**Log de backups PostgreSQL**:
```
C:\Users\Admin\Documents\backups\backup_log.txt
```

### Ver Historial en Programador de Tareas

1. Abrir "Programador de tareas"
2. Buscar: "Backup BD y Procesamiento de Informes Diarios"
3. Clic derecho → Propiedades → Pestaña **"Historial"**

### Ver Estado de la Tarea

**PowerShell**:
```powershell
Get-ScheduledTask -TaskName "Backup BD y Procesamiento de Informes Diarios" | Get-ScheduledTaskInfo
```

Muestra:
- Última ejecución
- Próxima ejecución
- Código de resultado (0 = éxito)

---

## 🛠️ Operaciones Comunes

### Ejecutar Manualmente (Prueba)

**Método 1 - GUI**:
1. Abrir "Programador de tareas"
2. Buscar tarea
3. Clic derecho → **"Ejecutar"**

**Método 2 - PowerShell**:
```powershell
Start-ScheduledTask -TaskName "Backup BD y Procesamiento de Informes Diarios"
```

**Método 3 - Ejecutar script directamente**:
```bash
cd C:\Users\Admin\Documents\Agenda\calendario
.\ejecutar_tarea_programada.bat
```

---

### Deshabilitar Temporalmente

**GUI**:
1. Programador de tareas → Buscar tarea
2. Clic derecho → **"Deshabilitar"**

**PowerShell**:
```powershell
Disable-ScheduledTask -TaskName "Backup BD y Procesamiento de Informes Diarios"
```

**Habilitar nuevamente**:
```powershell
Enable-ScheduledTask -TaskName "Backup BD y Procesamiento de Informes Diarios"
```

---

### Eliminar Tarea

**GUI**:
1. Programador de tareas → Buscar tarea
2. Clic derecho → **"Eliminar"**

**PowerShell**:
```powershell
Unregister-ScheduledTask -TaskName "Backup BD y Procesamiento de Informes Diarios" -Confirm:$false
```

**Recrear después**:
```powershell
.\configurar_tarea_programada.ps1
```

---

## 📧 Formato de Emails

### Email de Éxito (Normal)

```
Asunto: [EXITO] Backup y Procesamiento de Informes - 2026-04-04

El proceso automatico se ejecuto exitosamente:

=== BACKUP POSTGRESQL ===
Base de datos: laboratorio2
Archivo: backup_2026-04-04.sql
Tamaño: 4789980 bytes
Ubicacion local: C:\Users\Admin\Documents\backups

=== GOOGLE DRIVE ===
Subido exitosamente a: backups_db/
Backups antiguos eliminados (>30 dias)

=== PROCESAMIENTO DE INFORMES ===
Informes procesados correctamente

=== DETALLES ===
Fecha: 04/04/2026
Hora: 08:00:15
Servidor: DESKTOP-ABC123

---
Mensaje automatico del sistema de backups
```

### Email de Error (Alta Prioridad)

```
Asunto: [ERROR] Backup y Procesamiento de Informes - 2026-04-04

Se produjo un error durante el proceso automatico.

Fecha: 04/04/2026 08:00:15
Error: Error al generar backup de PostgreSQL
Servidor: DESKTOP-ABC123
Base de datos: laboratorio2

Por favor, revisa el log en: C:\Users\Admin\Documents\backups\backup_log.txt
```

---

## 🔧 Troubleshooting

### La tarea no se ejecuta

**Verificar**:
1. Tarea está habilitada:
   ```powershell
   Get-ScheduledTask -TaskName "Backup BD*" | Select State
   ```
   Debe decir: `Ready`

2. Próxima ejecución programada:
   ```powershell
   Get-ScheduledTaskInfo -TaskName "Backup BD*" | Select NextRunTime
   ```

3. Historial de ejecuciones (Programador de tareas → Historial)

---

### La tarea falla

**Revisar logs**:
1. `logs\tarea_programada_*.log` (más reciente)
2. `C:\Users\Admin\Documents\backups\backup_log.txt`
3. Programador de tareas → Historial → Buscar errores

**Errores comunes**:

| Error | Causa | Solución |
|-------|-------|----------|
| PostgreSQL no accesible | Servicio detenido | Iniciar servicio PostgreSQL |
| Contraseña incorrecta | `.env` corrupto | Verificar `DB_PASSWORD` en `.env` |
| rclone falla | No configurado | Ejecutar `rclone config` |
| Email no se envía | SMTP incorrecto | Verificar credenciales en `.env` |

---

### No llega el email

**Verificar**:
1. Credenciales SMTP en `.env`:
   ```
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SENDER_EMAIL=tu_email@gmail.com
   SENDER_PASSWORD=tu_contraseña_app
   ```

2. Carpeta de SPAM
3. Log del script: buscar "Notificacion enviada"

---

## 📚 Documentación Técnica

### Flujo de Ejecución

```
08:00 AM → Programador de Tareas inicia tarea
    ↓
ejecutar_tarea_programada.bat (wrapper)
    ↓
    ├─ Crea timestamp
    ├─ Crea directorio logs/ si no existe
    ├─ Registra inicio en historial.log
    ↓
enviar_informes_diarios.bat (script principal)
    ↓
    ├─ Lee credenciales desde .env
    ├─ 1. Backup PostgreSQL → .sql
    ├─ 2. Sube a Google Drive (rclone)
    ├─ 3. Limpia backups >30 días
    ├─ 4. Procesa informes PDF (Django)
    ├─ 5. Envía emails a pacientes
    ↓
    ├─ Determina: ¿Hubo errores?
    ├─   SI → Email de ERROR (alta prioridad)
    └─   NO → Email de ÉXITO (normal)
    ↓
Logs guardados:
    ├─ logs\tarea_programada_YYYYMMDD_HHMM.log
    ├─ logs\historial.log
    └─ C:\Users\Admin\Documents\backups\backup_log.txt
```

### Reintentos Automáticos

Si la tarea falla:
- **Reintenta automáticamente**: 3 veces
- **Intervalo entre reintentos**: 10 minutos
- **Timeout máximo**: 2 horas

### Requisitos

- ✅ Windows 10/11 o Windows Server
- ✅ PostgreSQL 17 instalado
- ✅ rclone configurado con remote "gdrive"
- ✅ Python + Django + uv
- ✅ Credenciales SMTP en `.env`
- ✅ Usuario con privilegios de administrador

---

## 🆘 Soporte

**Logs de diagnóstico**:
```powershell
# Ver última ejecución
Get-Content logs\historial.log -Tail 20

# Ver log completo de última ejecución
Get-ChildItem logs\tarea_programada_*.log | Sort-Object LastWriteTime -Descending | Select-Object -First 1 | Get-Content

# Ver estado de tarea
Get-ScheduledTask -TaskName "Backup BD*" | Format-List *
```

**Contacto**:
- Email: maurohcardona@gmail.com
- Revisar logs antes de reportar problema

---

## 📝 Notas

- La tarea se ejecuta aunque el usuario no esté logueado
- La contraseña se almacena de forma segura y encriptada en Windows
- Los backups locales y en Drive se limpian automáticamente después de 30 días
- Cada ejecución genera un log individual con timestamp
- El email de notificación se envía SIEMPRE (éxito o error)

---

**Última actualización**: Abril 2026  
**Versión**: 2.0 (con notificaciones siempre activas)
