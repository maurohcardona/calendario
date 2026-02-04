"""
Context processors para la aplicación turnos.
Proveen datos comunes a todos los templates.
"""
from datetime import date
from turnos.models import Agenda


def agendas_disponibles(request):
    """
    Agrega todas las agendas disponibles al contexto.
    """
    return {
        'agendas_disponibles': Agenda.objects.all().order_by('name')
    }


def fecha_actual(request):
    """
    Agrega la fecha actual al contexto.
    """
    return {
        'hoy': date.today()
    }


def configuracion_sistema(request):
    """
    Agrega configuración general del sistema.
    """
    return {
        'nombre_hospital': 'Hospital Balestrini',
        'email_contacto': 'admlabobalestrini@gmail.com',
        'horario_atencion': 'Lunes a Viernes de 7:00 a 9:00 hs',
        'horario_retiro': 'De lunes a viernes de 10 a 17 hs',
    }
