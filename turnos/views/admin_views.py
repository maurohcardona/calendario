"""
Vistas administrativas y de auditoría.

Este módulo contiene vistas para administración del sistema, auditoría de cambios
y gestión de médicos. Incluye control de acceso mediante superusuario.
"""

import json
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import redirect, render
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.urls import reverse
from django.core.paginator import Paginator
from django.contrib.contenttypes.models import ContentType
from django.views.decorators.csrf import csrf_exempt
from django.db import models
from medicos.models import Medico


@user_passes_test(lambda u: u.is_superuser)
def administrar_tablas(request: HttpRequest) -> HttpResponse:
    """
    Redirige al panel de administración de Django.

    Args:
        request: Objeto HttpRequest (requiere superusuario).

    Returns:
        HttpResponse: Redirección al índice del admin de Django.
    """
    return redirect(reverse("admin:index"))


@user_passes_test(lambda u: u.is_superuser)
def administrar_tabla_detalle(request: HttpRequest, tabla: str) -> HttpResponse:
    """
    Redirige al panel de administración de Django.

    Args:
        request: Objeto HttpRequest (requiere superusuario).
        tabla: Nombre de la tabla a administrar (no utilizado).

    Returns:
        HttpResponse: Redirección al índice del admin de Django.
    """
    return redirect(reverse("admin:index"))


@user_passes_test(lambda u: u.is_superuser)
def crear_registro(request: HttpRequest, tabla: str) -> HttpResponse:
    """
    Redirige al panel de administración de Django.

    Args:
        request: Objeto HttpRequest (requiere superusuario).
        tabla: Nombre de la tabla para crear registro (no utilizado).

    Returns:
        HttpResponse: Redirección al índice del admin de Django.
    """
    return redirect(reverse("admin:index"))


@user_passes_test(lambda u: u.is_superuser)
def editar_registro(request: HttpRequest, tabla: str, id: int) -> HttpResponse:
    """
    Redirige al panel de administración de Django.

    Args:
        request: Objeto HttpRequest (requiere superusuario).
        tabla: Nombre de la tabla (no utilizado).
        id: ID del registro a editar (no utilizado).

    Returns:
        HttpResponse: Redirección al índice del admin de Django.
    """
    return redirect(reverse("admin:index"))


@user_passes_test(lambda u: u.is_superuser)
def eliminar_registro(request: HttpRequest, tabla: str, id: int) -> HttpResponse:
    """
    Redirige al panel de administración de Django.

    Args:
        request: Objeto HttpRequest (requiere superusuario).
        tabla: Nombre de la tabla (no utilizado).
        id: ID del registro a eliminar (no utilizado).

    Returns:
        HttpResponse: Redirección al índice del admin de Django.
    """
    return redirect(reverse("admin:index"))


@user_passes_test(lambda u: u.is_superuser)
def aplicar_feriados(request: HttpRequest) -> HttpResponse:
    """
    Redirige al panel de administración de Django.

    Args:
        request: Objeto HttpRequest (requiere superusuario).

    Returns:
        HttpResponse: Redirección al índice del admin de Django.
    """
    return redirect(reverse("admin:index"))


@login_required
@user_passes_test(lambda u: u.is_superuser)
def audit_log(request: HttpRequest) -> HttpResponse:
    """
    Vista de auditoría que muestra el registro de cambios del sistema.

    Permite consultar el historial completo de cambios con filtros por:
    - Acción (creación, modificación, eliminación)
    - Tipo de modelo (turno, paciente, etc.)
    - Usuario que realizó el cambio
    - DNI del paciente
    - Número de turno

    Acceso restringido solo para superusuarios.

    Args:
        request: Objeto HttpRequest con parámetros GET opcionales:
            - action: Tipo de acción realizada
            - model: Modelo afectado
            - user: Nombre de usuario
            - dni: DNI del paciente
            - turno_id: ID del turno
            - page: Número de página para paginación

    Returns:
        HttpResponse: Render de la plantilla audit_log.html con logs paginados.

    Example:
        GET /admin/audit-log/?dni=12345678&page=2
        Muestra página 2 de logs relacionados con DNI 12345678
    """
    from auditlog.models import LogEntry
    from pacientes.models import Paciente
    import json

    # Obtener todos los logs
    logs = LogEntry.objects.select_related("content_type", "actor").all()

    # Filtros
    action = request.GET.get("action", "")
    model = request.GET.get("model", "")
    user = request.GET.get("user", "")
    dni = request.GET.get("dni", "")
    turno_id = request.GET.get("turno_id", "")

    if action:
        logs = logs.filter(action=action)

    if model:
        try:
            content_type = ContentType.objects.get(model=model.lower())
            logs = logs.filter(content_type=content_type)
        except ContentType.DoesNotExist:
            pass

    if user:
        logs = logs.filter(actor__username__icontains=user)

    # Filtro por número de turno
    if turno_id:
        try:
            # Buscar logs del turno mismo
            turno_ct = ContentType.objects.get(model="turno")
            turno_filters = models.Q(content_type=turno_ct, object_id=turno_id)

            # También buscar logs de coordinaciones de este turno
            try:
                coordinados_ct = ContentType.objects.get(model="coordinados")
                from turnos.models import Coordinados

                # Buscar todos los coordinados de este turno
                coordinados_ids = Coordinados.objects.filter(
                    id_turno_id=turno_id
                ).values_list("id", flat=True)
                if coordinados_ids:
                    turno_filters |= models.Q(
                        content_type=coordinados_ct, object_id__in=coordinados_ids
                    )
            except:
                pass

            logs = logs.filter(turno_filters)
        except:
            pass

    # Filtro por DNI del paciente
    if dni:
        # Buscar paciente por DNI
        pacientes = Paciente.objects.filter(iden__icontains=dni)
        if pacientes.exists():
            # Filtrar logs que contengan el DNI del paciente en los cambios
            # o que sean del modelo Turno y referencien al paciente
            dni_filters = models.Q()
            for paciente in pacientes:
                # Filtrar por object_id si es un Turno
                try:
                    turno_ct = ContentType.objects.get(model="turno")
                    # Buscar turnos de este paciente
                    from turnos.models import Turno

                    turnos_paciente = Turno.objects.filter(dni=paciente).values_list(
                        "id", flat=True
                    )
                    dni_filters |= models.Q(
                        content_type=turno_ct, object_id__in=turnos_paciente
                    )
                except:
                    pass

                # También buscar en el campo changes que contenga el DNI
                dni_filters |= models.Q(changes__icontains=paciente.iden)

            logs = logs.filter(dni_filters)

    # Ordenar por más reciente primero
    logs = logs.order_by("-timestamp")

    # Paginación
    paginator = Paginator(logs, 20)
    page_number = request.GET.get("page", 1)
    logs_page = paginator.get_page(page_number)

    context = {
        "logs": logs_page,
        "action": action,
        "model": model,
        "user": user,
        "dni": dni,
        "turno_id": turno_id,
    }

    return render(request, "turnos/audit_log.html", context)


@csrf_exempt
@login_required
def crear_medico_api(request: HttpRequest) -> JsonResponse:
    """
    API para crear un nuevo médico en el sistema.

    Recibe datos JSON con nombre completo y matrícula provincial del médico.
    Valida que no exista un médico con la misma matrícula antes de crear.

    Note:
        Esta vista está exenta de CSRF (@csrf_exempt) para facilitar
        llamadas AJAX desde el frontend.

    Args:
        request: Objeto HttpRequest con body JSON:
            {
                "nombre_apellido": str,
                "matricula_provincial": str
            }

    Returns:
        JsonResponse con estructura:
        - Éxito: {"success": True, "message": "Médico creado correctamente"}
        - Error validación: {"success": False, "error": "mensaje de error"}
        - Error servidor: {"success": False, "error": "detalle excepción"}, status=500

    Example:
        POST /api/crear-medico/
        Body: {"nombre_apellido": "Dr. Juan Pérez", "matricula_provincial": "MP12345"}
        Response: {"success": true, "message": "Médico creado correctamente"}
    """
    if request.method != "POST":
        return JsonResponse(
            {"success": False, "error": "Método no permitido"}, status=400
        )

    try:
        data = json.loads(request.body)
        nombre = data.get("nombre_apellido", "").strip()
        matricula = data.get("matricula_provincial", "").strip()

        if not nombre or not matricula:
            return JsonResponse(
                {"success": False, "error": "Nombre y matrícula son requeridos"}
            )

        # Crear el médico
        medico, created = Medico.objects.get_or_create(
            matricula=matricula, defaults={"nombre": nombre}
        )

        if created:
            return JsonResponse(
                {"success": True, "message": "Médico creado correctamente"}
            )
        else:
            return JsonResponse({"success": False, "error": "La matrícula ya existe"})

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)
