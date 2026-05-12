from datetime import date
from typing import Any, Dict

from django.http import JsonResponse, HttpRequest
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.db.models import Q

from turnos.models import Turno
from pacientes.models import Paciente


@login_required
@require_http_methods(["GET"])
def buscar_paciente_api(request: HttpRequest) -> JsonResponse:
    """API para buscar paciente por número de identificación y tipo.

    Args:
        request: HttpRequest con los parámetros 'dni' y 'tipo_iden' en GET

    Returns:
        JsonResponse con los datos del paciente si se encuentra,
        o {'found': False} si no existe.

    Example:
        GET /api/pacientes/buscar/?dni=12345678&tipo_iden=DNI
    """
    dni = request.GET.get("dni", "").strip()
    tipo_iden = request.GET.get("tipo_iden", "").strip()

    if not dni:
        return JsonResponse({"found": False, "error": "DNI no proporcionado"})

    try:
        # Si se proporciona tipo_iden, buscar por combinación exacta
        if tipo_iden:
            paciente = Paciente.objects.filter(tipo_iden=tipo_iden, iden=dni).first()
        else:
            # Backward compatible: buscar solo por iden (puede retornar el primero)
            paciente = Paciente.objects.filter(iden=dni).first()

        if not paciente:
            return JsonResponse({"found": False})

        # Construir respuesta con datos del paciente
        response_data: Dict[str, Any] = {
            "found": True,
            "tipo_iden": paciente.tipo_iden,
            "nombre": paciente.nombre,
            "apellido": paciente.apellido,
            "fecha_nacimiento": paciente.fecha_nacimiento.isoformat()
            if paciente.fecha_nacimiento
            else "",
            "sexo": paciente.sexo,
            "telefono": paciente.telefono or "",
            "email": paciente.email or "",
            "observaciones": paciente.observaciones or "",
        }

        # Buscar turno pendiente (fecha >= hoy)
        turnos_pendientes = (
            Turno.objects.filter(dni=paciente, fecha__gte=date.today())
            .order_by("fecha")
            .select_related("agenda")
        )

        if turnos_pendientes.exists():
            proximo = turnos_pendientes.first()
            response_data["tiene_turno_pendiente"] = True
            response_data["proximo_turno"] = proximo.fecha.strftime("%d-%m-%y")
            response_data["agenda_proximo_turno"] = (
                proximo.agenda.name if proximo.agenda else ""
            )
        else:
            response_data["tiene_turno_pendiente"] = False
            response_data["proximo_turno"] = None

        return JsonResponse(response_data)

    except Exception as e:
        return JsonResponse(
            {"found": False, "error": f"Error al buscar paciente: {str(e)}"}, status=500
        )


@login_required
@require_http_methods(["GET"])
def buscar_pacientes_parcial_api(request: HttpRequest) -> JsonResponse:
    """API para buscar pacientes por número de identificación, apellido o nombre (parcial).

    Busca automáticamente por número si el texto contiene solo dígitos,
    o por apellido/nombre si contiene letras.

    Args:
        request: HttpRequest con el parámetro 'q' en GET (mínimo 2 caracteres)

    Returns:
        JsonResponse con lista de hasta 10 pacientes que coincidan:
        [
            {
                "id": 123,
                "tipo_iden": "DNI",
                "iden": "12345678",
                "nombre": "Juan",
                "apellido": "Pérez",
                "nombre_completo": "PÉREZ, Juan",
                "display": "DNI 12345678 - PÉREZ, Juan"
            },
            ...
        ]

    Example:
        GET /pacientes/api/buscar-pacientes/?q=12345
        GET /pacientes/api/buscar-pacientes/?q=Perez
    """
    q = request.GET.get("q", "").strip()

    if len(q) < 2:
        return JsonResponse([], safe=False)

    try:
        # Si es solo dígitos, buscar por número de identificación
        if q.isdigit():
            pacientes = Paciente.objects.filter(iden__icontains=q).order_by(
                "apellido", "nombre"
            )[:10]
        else:
            # Si tiene letras, buscar por apellido o nombre
            pacientes = Paciente.objects.filter(
                Q(apellido__icontains=q) | Q(nombre__icontains=q)
            ).order_by("apellido", "nombre")[:10]

        resultado = [
            {
                "id": p.id,
                "tipo_iden": p.tipo_iden,
                "iden": p.iden,
                "nombre": p.nombre,
                "apellido": p.apellido,
                "nombre_completo": f"{p.apellido.upper()}, {p.nombre}",
                "display": f"{p.tipo_iden} {p.iden} - {p.apellido.upper()}, {p.nombre}",
            }
            for p in pacientes
        ]

        return JsonResponse(resultado, safe=False)

    except Exception as e:
        return JsonResponse(
            {"error": f"Error en la búsqueda: {str(e)}"}, status=500
        )
