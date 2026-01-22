from datetime import date
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from turnos.models import Turno
from pacientes.models import Paciente


@login_required
def buscar_paciente_api(request):
    """API para buscar paciente por DNI en PostgreSQL"""
    dni = request.GET.get('dni', '').strip()
    if not dni:
        return JsonResponse({'found': False})
    
    try:
        paciente = Paciente.objects.filter(iden=dni).first()

        # Buscar si tiene turno pendiente (fecha >= hoy)
        tiene_turno_pendiente = False
        proximo_turno = None
        if paciente:
            turnos_pendientes = Turno.objects.filter(dni=dni, fecha__gte=date.today()).order_by('fecha')
            if turnos_pendientes.exists():
                tiene_turno_pendiente = True
                proximo_turno = turnos_pendientes.first().fecha.strftime('%d-%m-%y')

        if paciente:
            sexo_map = {
                'Masculino': 'Hombre',
                'Femenino': 'Mujer',
                'Sin asignar': 'Generico'
            }
            sexo_front = sexo_map.get(paciente.sexo, 'Generico')
            return JsonResponse({
                'found': True,
                'nombre': paciente.nombre,
                'apellido': paciente.apellido,
                'fecha_nacimiento': paciente.fecha_nacimiento.isoformat() if paciente.fecha_nacimiento else '',
                'sexo': sexo_front,
                'telefono': paciente.telefono or '',
                'email': paciente.email or '',
                'observaciones': paciente.observaciones or '',
                'tiene_turno_pendiente': tiene_turno_pendiente,
                'proximo_turno': proximo_turno
            })

        return JsonResponse({'found': False})

    except Exception as e:
        return JsonResponse({'found': False, 'error': str(e)})
