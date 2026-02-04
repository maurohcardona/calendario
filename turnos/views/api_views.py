"""
Vistas API (JSON responses) para el sistema de turnos.
"""
from datetime import datetime, date
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from turnos.models import Turno, Cupo, Agenda, Coordinados, Feriados
from medicos.models import Medico
from turnos.views.calendar_views import lighten_color


@login_required
def eventos_calendario(request):
    """API que devuelve eventos para el calendario (JSON)."""
    eventos = []
    hoy = date.today()
    
    # Obtener feriados
    feriados_dict = {}
    try:
        for feriado in Feriados.objects.all():
            feriados_dict[feriado.fecha] = feriado.descripcion
    except Exception as e:
        print(f"Error al cargar feriados: {e}")
    
    # Agregar eventos de feriados
    for fecha_fer, descripcion in feriados_dict.items():
        eventos.append({
            "title": f"🚫 {descripcion}",
            "start": fecha_fer.isoformat(),
            "allDay": True,
            "color": "#9e9e9e",
            "textColor": "#ffffff",
            "extendedProps": {
                "es_feriado": True,
                "descripcion": descripcion
            }
        })
    
    # Eventos por Cupo explícito
    cupos = Cupo.objects.select_related('agenda').all()
    for c in cupos:
        # No mostrar cupo si es feriado
        if c.fecha in feriados_dict:
            continue
            
        libres = c.disponibles()
        es_pasado = c.fecha < hoy
        
        # Determinar color y título según disponibilidad
        if libres == 0:
            color_claro = "#ff4444"
            titulo = f"{c.agenda.name}: Completo"
            texto_tachado = True
        else:
            color_original = c.agenda.color if c.agenda and c.agenda.color else "green"
            color_claro = lighten_color(color_original)
            titulo = f"{c.agenda.name}: {libres}/{c.cantidad_total}"
            texto_tachado = False
        
        eventos.append({
            "title": titulo,
            "start": c.fecha.isoformat(),
            "allDay": True,
            "color": color_claro,
            "textColor": "#000000",
            "extendedProps": {
                "agenda_id": c.agenda.id,
                "agenda_name": c.agenda.name,
                "fecha": c.fecha.isoformat(),
                "disponibles": libres,
                "es_pasado": es_pasado,
                "completo": libres == 0,
                "texto_tachado": texto_tachado,
                "es_feriado": False
            }
        })
    
    return JsonResponse(eventos, safe=False)


@login_required
def turnos_historicos_api(request, fecha):
    """Devuelve los turnos de un día pasado agrupados por agenda y coordinación."""
    fecha_obj = datetime.strptime(fecha, '%Y-%m-%d').date()
    
    turnos = Turno.objects.filter(fecha=fecha_obj).select_related('agenda').order_by(
        'agenda__name', 'apellido', 'nombre'
    )
    
    # Obtener IDs de turnos coordinados
    turnos_coordinados_ids = set(Coordinados.objects.values_list('id_turno', flat=True))
    
    # Agrupar por agenda
    agendas_dict = {}
    for turno in turnos:
        agenda_name = turno.agenda.name if turno.agenda else "Sin agenda"
        if agenda_name not in agendas_dict:
            agendas_dict[agenda_name] = {
                'coordinados': [],
                'no_coordinados': []
            }
        
        turno_data = {
            'id': turno.id,
            'dni': turno.paciente_dni,
            'nombre': turno.nombre,
            'apellido': turno.apellido,
            'determinaciones': turno.determinaciones,
        }
        
        # Verificar si está coordinado
        if turno.id in turnos_coordinados_ids:
            agendas_dict[agenda_name]['coordinados'].append(turno_data)
        else:
            agendas_dict[agenda_name]['no_coordinados'].append(turno_data)
    
    return JsonResponse({
        'fecha': fecha,
        'agendas': agendas_dict,
        'total_turnos': turnos.count()
    })


@login_required
def listar_medicos_api(request):
    """API para listar todos los médicos."""
    try:
        medicos = Medico.objects.all().order_by('nombre').values('id', 'nombre', 'matricula')
        
        items = []
        for medico in medicos:
            items.append({
                'id': medico['id'],
                'nombre_apellido': medico['nombre'],
                'matricula_provincial': medico['matricula']
            })
        
        return JsonResponse(items, safe=False)
            
    except Exception as e:
        return JsonResponse([], safe=False)
