"""
Vistas relacionadas con coordinación de turnos y generación de tickets.

Este módulo maneja todo el flujo de coordinación de turnos médicos:
- Pre-coordinación y edición de datos del paciente
- Coordinación final y generación de órdenes
- Generación de tickets para extracción y retiro
- Control de órdenes generadas
"""

import json
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.urls import reverse
from turnos.models import Turno, Coordinados
from turnos.services import ASTMService, PDFService, DeterminacionService
from datetime import date


@login_required
def precoordinacion_turno(request: HttpRequest, turno_id: int) -> HttpResponse:
    """
    Vista de pre-coordinación para editar datos del turno antes de coordinar.

    Esta es la vista principal de preparación antes de la coordinación final.
    Permite al usuario:
    1. Editar/completar datos personales del paciente (DNI, nombre, fecha nacimiento, etc.)
    2. Modificar datos del turno (agenda, fecha, determinaciones)
    3. Asignar o cambiar médico solicitante
    4. Agregar notas internas
    5. Eliminar el turno si es necesario
    6. Avanzar a coordinación final

    Los cambios se persisten en ambas tablas: Paciente y Turno.

    Args:
        request: Objeto HttpRequest (requiere autenticación).
            - GET: Muestra formulario de pre-coordinación con datos actuales
            - POST: Procesa cambios y ejecuta acción según parámetro "accion":
                - "eliminar": Elimina el turno y redirige a búsqueda
                - "coordinar": Guarda cambios y redirige a coordinación
                - otro/vacío: Guarda cambios y redirige a búsqueda
        turno_id: ID del turno a pre-coordinar.

    Returns:
        HttpResponse:
            - GET: Render de precoordinacion_turno.html con formulario
            - POST "eliminar": Redirect a turnos:buscar
            - POST "coordinar": Redirect a turnos:coordinar_turno
            - POST otro: Redirect a turnos:buscar

    Raises:
        Http404: Si el turno_id no existe.

    Note:
        El campo sexo se mapea automáticamente entre formatos del formulario
        y el modelo Paciente (Hombre→Masculino, Mujer→Femenino, etc.)

    Example:
        GET /turnos/123/precoordinacion/
        POST /turnos/123/precoordinacion/ con accion=coordinar
        → Actualiza datos y redirige a coordinación final
    """
    from turnos.models import Agenda
    from pacientes.models import Paciente
    from medicos.models import Medico
    from datetime import datetime

    turno = get_object_or_404(
        Turno.objects.select_related("medico", "dni", "agenda"), id=turno_id
    )

    paciente_obj = turno.dni
    paciente_data = None
    if paciente_obj:
        paciente_data = {
            "nombre": paciente_obj.nombre,
            "apellido": paciente_obj.apellido,
            "dni": paciente_obj.iden,
            "fecha_nacimiento": paciente_obj.fecha_nacimiento,
            "sexo": paciente_obj.sexo,
            "telefono": paciente_obj.telefono,
            "email": paciente_obj.email,
            "observaciones": paciente_obj.observaciones or "",
        }

    if request.method == "POST":
        accion = request.POST.get("accion")
        if accion == "eliminar":
            turno.delete()
            return redirect("turnos:buscar")

        # Actualizar datos personales
        dni_nuevo = request.POST.get("dni", "").strip()
        apellido_nuevo = request.POST.get("apellido", "").strip()
        nombre_nuevo = request.POST.get("nombre", "").strip()
        fecha_nac_nueva = request.POST.get("fecha_nacimiento", "")
        sexo_nuevo = request.POST.get("sexo", "")
        telefono = request.POST.get("telefono", "")
        email = request.POST.get("email", "")
        observaciones_paciente = request.POST.get("observaciones_paciente", "")

        # Validar que el DNI no esté vacío
        if not dni_nuevo:
            from django.contrib import messages

            messages.error(request, "El DNI es obligatorio y no puede estar vacío")
            agendas = Agenda.objects.all()
            context = {
                "turno": turno,
                "paciente": paciente_data,
                "agendas": agendas,
                "es_precoordinacion": True,
            }
            return render(request, "turnos/precoordinacion_turno.html", context)

        # Mapear sexo a opciones del modelo Paciente
        sexo_map = {
            "Hombre": "Masculino",
            "Mujer": "Femenino",
            "Generico": "Sin asignar",
            "": "Sin asignar",
            None: "Sin asignar",
        }
        sexo_model = sexo_map.get(sexo_nuevo, sexo_nuevo or "Sin asignar")

        # Parsear fecha de nacimiento
        fecha_nac_parsed = None
        if fecha_nac_nueva:
            try:
                fecha_nac_parsed = datetime.strptime(fecha_nac_nueva, "%Y-%m-%d").date()
            except Exception:
                fecha_nac_parsed = (
                    paciente_obj.fecha_nacimiento if paciente_obj else None
                )

        # Crear o actualizar Paciente
        paciente_obj, _ = Paciente.objects.update_or_create(
            iden=dni_nuevo,
            defaults={
                "nombre": nombre_nuevo,
                "apellido": apellido_nuevo,
                "fecha_nacimiento": fecha_nac_parsed or date.today(),
                "sexo": sexo_model,
                "telefono": telefono or None,
                "email": email or None,
                "observaciones": observaciones_paciente or "",
            },
        )

        # Asignar paciente al turno
        turno.dni = paciente_obj

        # Actualizar datos del turno
        turno.agenda_id = request.POST.get("agenda")
        turno.fecha = request.POST.get("fecha")
        turno.determinaciones = request.POST.get("determinaciones", "")

        # Manejar el médico
        medico_nombre = request.POST.get("medico", "")
        if medico_nombre:
            try:
                turno.medico = Medico.objects.get(nombre=medico_nombre)
            except Medico.DoesNotExist:
                medicos = Medico.objects.filter(nombre__icontains=medico_nombre)
                if medicos.exists():
                    turno.medico = medicos.first()
                else:
                    turno.medico = None
        else:
            turno.medico = None

        turno.nota_interna = request.POST.get("nota_interna", "")
        turno.save()

        # Si se presionó coordinar, redirigir a la acción de coordinación
        if accion == "coordinar":
            return redirect(reverse("turnos:coordinar_turno", args=[turno.id]))

        return redirect("turnos:buscar")

    agendas = Agenda.objects.all()
    context = {
        "turno": turno,
        "paciente": paciente_data,
        "agendas": agendas,
        "es_precoordinacion": True,
    }
    return render(request, "turnos/precoordinacion_turno.html", context)


@login_required
def ver_coordinacion(request: HttpRequest, turno_id: int) -> HttpResponse:
    """
    Vista de consulta de turno coordinado (solo lectura).

    Muestra todos los detalles de un turno coordinado incluyendo:
    - Datos completos del paciente (con cálculo de edad)
    - Información del médico solicitante
    - Lista expandida de determinaciones solicitadas
    - Estado de coordinación y usuario coordinador
    - Fechas de turno y coordinación

    Args:
        request: Objeto HttpRequest (requiere autenticación).
        turno_id: ID del turno a visualizar.

    Returns:
        HttpResponse: Render de ver_coordinacion.html con contexto completo:
        {
            "turno": Turno object,
            "coordinacion": Coordinados object o None,
            "paciente": dict con datos del paciente,
            "medico": dict con datos del médico,
            "determinaciones_nombres": list[str] con códigos y nombres,
            "hoy": date.today()
        }

    Raises:
        Http404: Si el turno_id no existe.

    Example:
        GET /turnos/123/ver-coordinacion/
        Muestra vista de solo lectura del turno coordinado 123
    """
    turno = get_object_or_404(
        Turno.objects.select_related("dni", "medico", "agenda"), id=turno_id
    )

    # Verificar que el turno esté coordinado
    coordinacion = Coordinados.objects.filter(id_turno=turno_id).first()

    # Obtener datos del paciente
    paciente_data = None
    if turno.dni:
        paciente_data = {
            "nombre": turno.dni.nombre,
            "apellido": turno.dni.apellido,
            "dni": turno.dni.iden,
            "fecha_nacimiento": turno.dni.fecha_nacimiento,
            "sexo": turno.dni.sexo,
            "telefono": turno.dni.telefono or "",
            "email": turno.dni.email or "",
        }

    # Obtener datos del médico
    medico_data = None
    if turno.medico:
        medico_data = {
            "matricula": turno.medico.matricula,
            "nombre": turno.medico.nombre,
        }

    # Obtener nombres de determinaciones
    determinaciones_nombres = []
    if turno.determinaciones:
        codigos = [c.strip() for c in turno.determinaciones.split(",") if c.strip()]

        from determinaciones.models import (
            Determinacion,
            PerfilDeterminacion,
            DeterminacionCompleja,
        )

        for codigo in codigos:
            if codigo.startswith("/"):
                # Es un perfil o determinación compleja
                compleja = DeterminacionCompleja.objects.filter(codigo=codigo).first()
                if compleja:
                    determinaciones_nombres.append(f"{codigo} - {compleja.nombre}")
                    continue

                codigo_sin_slash = codigo.lstrip("/")
                perfil = PerfilDeterminacion.objects.filter(
                    codigo=codigo_sin_slash
                ).first()
                if perfil:
                    determinaciones_nombres.append(f"{codigo} - {perfil.nombre}")
            else:
                # Es una determinación simple
                det = Determinacion.objects.filter(codigo=codigo).first()
                if det:
                    determinaciones_nombres.append(f"{codigo} - {det.nombre}")
                else:
                    determinaciones_nombres.append(codigo)

    context = {
        "turno": turno,
        "coordinacion": coordinacion,
        "paciente": paciente_data,
        "medico": medico_data,
        "determinaciones_nombres": determinaciones_nombres,
        "hoy": date.today(),
    }

    return render(request, "turnos/ver_coordinacion.html", context)


@login_required
def coordinar_turno(request: HttpRequest, turno_id: int) -> JsonResponse:
    """
    Ejecuta la coordinación final de un turno generando archivos ASTM.

    Procesa la coordinación completa del turno:
    1. Genera archivo ASTM con las órdenes para el equipo de laboratorio
    2. Registra la coordinación en la tabla Coordinados
    3. Asocia impresora y usuario coordinador
    4. Marca el turno como coordinado

    El archivo ASTM se guarda en la carpeta configurada del sistema y contiene
    todas las determinaciones expandidas en formato estándar.

    Args:
        request: Objeto HttpRequest (requiere autenticación) con datos POST:
            - impresora: Nombre de la impresora destino (requerido)
            Acepta tanto application/json como application/x-www-form-urlencoded
        turno_id: ID del turno a coordinar.

    Returns:
        JsonResponse con estructura:
        - Éxito: {"success": true, "message": "Turno coordinado...", "ruta": "..."}
        - Error: {"success": false, "error": "mensaje de error"}

    Raises:
        Http404: Si el turno_id no existe.

    Example:
        POST /turnos/123/coordinar/
        Body: {"impresora": "Epson_TM_T20"}
        Response: {"success": true, "message": "Turno coordinado exitosamente..."}
    """
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Método no permitido"})

    try:
        turno = get_object_or_404(Turno.objects.select_related("dni"), id=turno_id)

        # Obtener nombre de impresora
        if request.content_type == "application/json":
            try:
                data = json.loads(request.body)
                nombre_impresora = data.get("impresora", "")
            except:
                nombre_impresora = request.POST.get("impresora", "")
        else:
            nombre_impresora = request.POST.get("impresora", "")

        if not nombre_impresora:
            return JsonResponse(
                {"success": False, "error": "Debe seleccionar una impresora"}
            )

        nombre_impresora = nombre_impresora.strip()
        usuario = request.user.username if request.user.is_authenticated else ""

        # Generar archivo ASTM usando el servicio
        exito, ruta_archivo, mensaje_error = ASTMService.generar_archivo_astm(
            turno, nombre_impresora, usuario
        )

        if exito:
            return JsonResponse(
                {
                    "success": True,
                    "message": f"Turno coordinado exitosamente. Archivo: {ruta_archivo}",
                }
            )
        else:
            return JsonResponse({"success": False, "error": mensaje_error})

    except Exception as e:
        return JsonResponse({"success": False, "error": f"Error inesperado: {str(e)}"})


@login_required
def generar_ticket_turno(request: HttpRequest, turno_id: int) -> HttpResponse:
    """
    Genera ticket PDF de turno para impresora térmica.

    Crea un ticket físico con información del turno para que el paciente
    presente el día de la extracción de muestras. Incluye datos del turno,
    paciente, agenda y usuario que asignó el turno.

    Args:
        request: Objeto HttpRequest (requiere autenticación).
        turno_id: ID del turno para el cual generar el ticket.

    Returns:
        HttpResponse: PDF del ticket para impresión térmica con headers
        Content-Type: application/pdf y Content-Disposition: inline.

    Raises:
        Http404: Si el turno_id no existe.

    Example:
        GET /turnos/123/ticket/
        Descarga ticket PDF para el turno 123
    """
    turno = get_object_or_404(
        Turno.objects.select_related("agenda", "dni", "medico"), id=turno_id
    )

    # Obtener apellido y nombre del usuario
    if turno.usuario:
        usuario_asignador = (
            f"{turno.usuario.last_name}, {turno.usuario.first_name}"
            if turno.usuario.last_name and turno.usuario.first_name
            else turno.usuario.username
        )
    else:
        usuario_asignador = (
            f"{request.user.last_name}, {request.user.first_name}"
            if request.user.last_name and request.user.first_name
            else request.user.username
        )

    return PDFService.generar_ticket_turno(turno, usuario_asignador)


@login_required
def generar_ticket_retiro(request: HttpRequest, turno_id: int) -> HttpResponse:
    """
    Genera ticket PDF de retiro de resultados para impresora térmica.

    Crea un ticket que el paciente debe presentar al retirar los resultados
    de sus estudios. Incluye información del turno coordinado y el usuario
    que realizó la coordinación.

    Args:
        request: Objeto HttpRequest (requiere autenticación).
        turno_id: ID del turno coordinado para generar ticket de retiro.

    Returns:
        HttpResponse: PDF del ticket de retiro con headers
        Content-Type: application/pdf y Content-Disposition: inline.

    Raises:
        Http404: Si el turno_id no existe.

    Note:
        Si existe coordinación, usa el usuario coordinador. Si no, usa
        el usuario actual como fallback.

    Example:
        GET /turnos/123/ticket-retiro/
        Descarga ticket de retiro para turno coordinado 123
    """
    turno = get_object_or_404(
        Turno.objects.select_related("agenda", "dni"), id=turno_id
    )

    # Obtener el usuario que coordinó el turno desde Coordinados
    coordinacion = Coordinados.objects.filter(id_turno=turno_id).first()

    if coordinacion and coordinacion.usuario:
        # Usar el usuario que coordinó
        usuario_asignador = (
            f"{coordinacion.usuario.last_name}, {coordinacion.usuario.first_name}"
            if coordinacion.usuario.last_name and coordinacion.usuario.first_name
            else coordinacion.usuario.username
        )
    else:
        # Fallback: usar el usuario actual
        usuario_asignador = (
            f"{request.user.last_name}, {request.user.first_name}"
            if request.user.last_name and request.user.first_name
            else request.user.username
        )

    return PDFService.generar_ticket_retiro(turno, usuario_asignador)


@login_required
def control_ordenes(request: HttpRequest) -> HttpResponse:
    """
    Vista de control de órdenes coordinadas por fecha.

    Muestra un listado de todas las órdenes (turnos) coordinadas para una
    fecha específica. Permite supervisión y control de las extracciones
    programadas. Por defecto muestra el día actual.

    La vista expande las determinaciones compactadas mostrando el detalle
    completo de cada estudio solicitado.

    Args:
        request: Objeto HttpRequest (requiere autenticación) con parámetro
            GET opcional:
            - fecha: Fecha en formato 'YYYY-MM-DD' (default: hoy)

    Returns:
        HttpResponse: Render de control.html con contexto:
        {
            "fecha": date object,
            "ordenes": lista de dict {"turno": Turno, "determinaciones": list},
            "total_ordenes": int
        }

    Example:
        GET /control-ordenes/?fecha=2024-03-15
        Muestra órdenes coordinadas del 15 de marzo de 2024
    """
    from datetime import datetime

    # Obtener fecha del parámetro GET o usar hoy por defecto
    fecha_str = request.GET.get("fecha")
    if fecha_str:
        try:
            fecha_control = datetime.strptime(fecha_str, "%Y-%m-%d").date()
        except ValueError:
            fecha_control = date.today()
    else:
        fecha_control = date.today()

    # Obtener IDs de turnos coordinados
    turnos_coordinados_ids = Coordinados.objects.values_list("id_turno", flat=True)

    # Filtrar turnos de la fecha seleccionada que estén coordinados
    turnos = (
        Turno.objects.filter(id__in=turnos_coordinados_ids, fecha=fecha_control)
        .select_related("dni", "agenda", "medico")
        .order_by("agenda__name", "creado")
    )

    # Preparar datos de turnos con determinaciones expandidas
    ordenes = []
    for turno in turnos:
        determinaciones_detalle = (
            DeterminacionService.obtener_determinaciones_detalladas(
                turno.determinaciones
            )
        )

        ordenes.append({"turno": turno, "determinaciones": determinaciones_detalle})

    context = {
        "fecha": fecha_control,
        "ordenes": ordenes,
        "total_ordenes": len(ordenes),
    }

    return render(request, "turnos/control.html", context)
