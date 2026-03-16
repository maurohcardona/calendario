from datetime import date
from typing import Any, Dict

from django.http import JsonResponse, HttpRequest
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods

from turnos.models import Turno
from pacientes.models import Paciente


@login_required
@require_http_methods(["GET"])
def buscar_paciente_api(request: HttpRequest) -> JsonResponse:
    """API para buscar paciente por DNI.

    Args:
        request: HttpRequest con el parámetro 'dni' en GET

    Returns:
        JsonResponse con los datos del paciente si se encuentra,
        o {'found': False} si no existe.

    Example:
        GET /api/pacientes/buscar/?dni=12345678

        Response:
        {
            'found': True,
            'nombre': 'Juan',
            'apellido': 'Pérez',
            'fecha_nacimiento': '1990-01-15',
            'sexo': 'Masculino',
            'telefono': '1234567890',
            'email': 'juan@example.com',
            'observaciones': 'Alérgico a penicilina',
            'tiene_turno_pendiente': True,
            'proximo_turno': '15-03-26'
        }
    """
    dni = request.GET.get("dni", "").strip()

    if not dni:
        return JsonResponse({"found": False, "error": "DNI no proporcionado"})

    try:
        paciente = Paciente.objects.filter(iden=dni).first()

        if not paciente:
            return JsonResponse({"found": False})

        # Construir respuesta con datos del paciente
        response_data: Dict[str, Any] = {
            "found": True,
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
