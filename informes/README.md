# Sistema de Envío de Informes Médicos

## Descripción

Este módulo gestiona el envío automático de informes médicos en formato PDF a pacientes por correo electrónico.

## Estructura de Carpetas

```
informes/
├── pendientes/     # PDFs pendientes de envío
└── enviados/       # PDFs ya enviados
```

## Formato de Archivos

Los archivos PDF deben seguir este formato de nombre:

```
DNI-ORDEN-PROTOCOLO.pdf
```

**Ejemplo:** `12345678-1234-ABC123.pdf`

- **DNI**: Documento del paciente (debe estar registrado en la base de datos)
- **ORDEN**: Número de orden del estudio
- **PROTOCOLO**: Número de protocolo del informe

## Uso

### 1. Procesar Informes Pendientes

Para procesar y enviar todos los PDFs en la carpeta `pendientes`:

```bash
python manage.py procesar_informes
```

### 2. Modo Simulación (Dry-Run)

Para verificar qué archivos se procesarían sin enviar emails:

```bash
python manage.py procesar_informes --dry-run
```

## Flujo de Trabajo

1. **Colocar PDFs**: Los archivos PDF se colocan en la carpeta `informes/pendientes/`
2. **Ejecutar comando**: Se ejecuta `python manage.py procesar_informes`
3. **Procesamiento**:
   - El sistema parsea el nombre del archivo
   - Busca el paciente por DNI
   - Verifica que tenga email registrado
   - Crea/actualiza el registro en la base de datos
   - Envía el email con el PDF adjunto
   - Mueve el archivo a `informes/enviados/`

## Configuración de Email

El sistema utiliza las siguientes variables del archivo `.env`:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SENDER_EMAIL=tu_email@gmail.com
SENDER_PASSWORD=tu_contraseña_de_aplicación
```

## Modelo de Datos

### Informes

- **paciente**: Relación con el paciente (ForeignKey)
- **id_turno**: Turno relacionado (opcional)
- **numero_orden**: Número de orden del estudio
- **numero_protocolo**: Número de protocolo
- **nombre_archivo**: Nombre del archivo PDF
- **estado**: PENDIENTE | ENVIADO | ERROR
- **email_destino**: Email al que se envió
- **fecha_creacion**: Fecha de creación del registro
- **fecha_envio**: Fecha de envío exitoso
- **intentos_envio**: Contador de intentos
- **mensaje_error**: Mensaje de error si falló

## Administración Django

En el admin de Django (`/admin/informes/informes/`) puedes:

- Ver todos los informes procesados
- Filtrar por estado (PENDIENTE, ENVIADO, ERROR)
- Buscar por DNI, nombre del paciente o número de protocolo
- Ver detalles de cada envío
- **Acciones en lote**:
  - Marcar como pendiente
  - Reintentar envío (para informes con error)

## Manejo de Errores

El sistema maneja los siguientes errores:

- **Formato de archivo inválido**: El nombre no sigue el patrón DNI-ORDEN-PROTOCOLO.pdf
- **Paciente no encontrado**: No existe un paciente con ese DNI
- **Email no registrado**: El paciente no tiene email en la base de datos
- **Error de envío**: Fallo en el servidor SMTP o conexión
- **Archivo duplicado**: El informe ya fue enviado anteriormente

Los informes con error se marcan en la base de datos y pueden reintentarse desde el admin.

## Contenido del Email

El email enviado incluye:

- **Asunto**: Informe Médico - Orden {orden} - Protocolo {protocolo}
- **Cuerpo**: Mensaje personalizado con datos del paciente y del informe
- **Adjunto**: El archivo PDF

## Estadísticas

El comando muestra estadísticas antes y después del procesamiento:

- Total de registros
- Pendientes de envío
- Enviados exitosamente
- Con errores

## Automatización

Para automatizar el procesamiento, puedes crear un cron job:

```bash
# Ejecutar cada hora
0 * * * * cd /ruta/al/proyecto && /ruta/al/venv/bin/python manage.py procesar_informes >> /var/log/informes.log 2>&1
```

## Consideraciones de Seguridad

- Los archivos PDF se mueven (no se copian) para evitar duplicados
- El sistema verifica que el paciente exista antes de enviar
- Los registros con error no bloquean el procesamiento de otros archivos
- Las contraseñas de email se almacenan en `.env` (nunca en el código)

## Solución de Problemas

### "Paciente con DNI X no encontrado"
Verifica que el paciente esté registrado en la base de datos con ese DNI exacto.

### "Paciente no tiene email registrado"
Actualiza el email del paciente en el admin de Django.

### "Error al enviar email"
Verifica la configuración de SMTP en el archivo `.env` y que la contraseña de aplicación sea válida.

### "Formato de nombre de archivo inválido"
Asegúrate de que el archivo siga el formato: `DNI-ORDEN-PROTOCOLO.pdf`

## Soporte

Para más información, consulta el modelo en [informes/models.py](informes/models.py) o el servicio en [informes/services.py](informes/services.py).
