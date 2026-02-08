"""
Vistas relacionadas con gestión de turnos (CRUD y búsqueda).
"""
from datetime import date, datetime
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponse
from django.urls import reverse
from django.db import transaction
from django.core.exceptions import ValidationError
from django.contrib import messages
from turnos.models import Turno, Cupo, Agenda, Coordinados, Feriados
from pacientes.models import Paciente
from medicos.models import Medico
from determinaciones.models import Determinacion, PerfilDeterminacion, DeterminacionCompleja
from turnos.forms import TurnoForm
from turnos.services import DeterminacionService, TurnoService


@login_required
def dia(request, fecha):
    """Vista principal para ver y crear turnos en una fecha específica."""
    # Convertir fecha a objeto date si viene como string
    if isinstance(fecha, str):
        fecha = datetime.strptime(fecha, '%Y-%m-%d').date()
    
    # Verificar si es feriado
    es_feriado = False
    descripcion_feriado = None
    try:
        feriado_obj = Feriados.objects.get(fecha=fecha)
        es_feriado = True
        descripcion_feriado = feriado_obj.descripcion
    except Feriados.DoesNotExist:
        es_feriado = False
    
    # Obtener turnos y cupos
    turnos_all = Turno.objects.filter(fecha=fecha).select_related('agenda')
    cupos_qs = Cupo.objects.select_related('agenda').filter(fecha=fecha)

    # Determinar modo de vista y agenda seleccionada
    agenda_id = request.GET.get('agenda')
    cupo = None
    disponibles = 0
    agenda_obj = None
    turnos = turnos_all
    modo_vista = 'todas_agendas'

    if agenda_id:
        try:
            agenda_obj = Agenda.objects.get(id=agenda_id)
            turnos = turnos_all.filter(agenda__id=agenda_id)
            modo_vista = 'agenda_seleccionada'
        except Agenda.DoesNotExist:
            agenda_obj = None

        if agenda_obj:
            # Calcular disponibilidad
            disponibilidad = TurnoService.calcular_disponibilidad_fecha(fecha, agenda_obj)
            disponibles = disponibilidad['disponibles']
            
            # Intentar obtener cupo explícito
            try:
                cupo = cupos_qs.get(agenda=agenda_obj)
            except Cupo.DoesNotExist:
                pass

    # Procesar formulario POST
    if request.method == 'POST':
        form = TurnoForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Validar que la fecha no sea feriado
                    if Feriados.objects.filter(fecha=fecha).exists():
                        feriado = Feriados.objects.get(fecha=fecha)
                        form.add_error(None, ValidationError(f"No se pueden asignar turnos en feriados: {feriado.descripcion}"))
                    else:
                        # Extraer datos del formulario
                        agenda_form = form.cleaned_data.get('agenda')
                        dni = form.cleaned_data.get('dni')
                        nombre = form.cleaned_data.get('nombre')
                        apellido = form.cleaned_data.get('apellido')
                        fecha_nacimiento = form.cleaned_data.get('fecha_nacimiento')
                        sexo = form.cleaned_data.get('sexo')
                        telefono = form.cleaned_data.get('telefono', '')
                        email = form.cleaned_data.get('email', '')
                        observaciones_paciente = form.cleaned_data.get('observaciones_paciente', '')
                        medico_nombre = form.cleaned_data.get('medico', '')
                        nota_interna = form.cleaned_data.get('nota_interna', '')
                        determinaciones = form.cleaned_data.get('determinaciones', '')
                        
                        # Usar el servicio para crear el turno
                        exito, turno_nuevo, mensaje_error = TurnoService.crear_turno(
                            fecha=fecha,
                            agenda=agenda_form,
                            dni=dni,
                            nombre=nombre,
                            apellido=apellido,
                            fecha_nacimiento=fecha_nacimiento,
                            sexo=sexo,
                            telefono=telefono,
                            email=email,
                            observaciones_paciente=observaciones_paciente,
                            medico_nombre=medico_nombre,
                            nota_interna=nota_interna,
                            determinaciones=determinaciones,
                            usuario=request.user
                        )
                        
                        if exito:
                            # Redirigir con parámetro para abrir PDF
                            return redirect(f"{reverse('turnos:dia', args=[fecha])}?agenda={agenda_form.id}&turno_creado={turno_nuevo.id}")
                        else:
                            form.add_error(None, ValidationError(mensaje_error))
                            
            except ValidationError as e:
                form.add_error(None, e)
    else:
        initial = {'fecha': fecha}
        if cupo:
            initial['agenda'] = cupo.agenda
        elif agenda_obj:
            initial['agenda'] = agenda_obj
        form = TurnoForm(initial=initial)

    # Agrupar turnos por agenda si estamos viendo todas las agendas
    if modo_vista == 'todas_agendas':
        turnos_por_agenda = {}
        agendas_disponibilidad = {}
        
        # Obtener todas las agendas que tienen capacidad o turnos para esta fecha
        all_agendas = Agenda.objects.all()
        for ag in all_agendas:
            disponibilidad_ag = TurnoService.calcular_disponibilidad_fecha(fecha, ag)
            
            # Incluir agenda si tiene capacidad O si tiene turnos (para fechas pasadas)
            if disponibilidad_ag['capacidad'] > 0 or disponibilidad_ag['usados'] > 0:
                agendas_disponibilidad[ag.id] = {
                    'agenda': ag,
                    **disponibilidad_ag
                }
        
        # Obtener IDs de turnos coordinados para la fecha
        turnos_coordinados_ids = set(Coordinados.objects.filter(
            id_turno__in=turnos_all.values_list('id', flat=True)
        ).values_list('id_turno', flat=True))

        # Agrupar turnos por agenda y por coordinación
        for turno in turnos_all:
            if turno.agenda.id not in turnos_por_agenda:
                turnos_por_agenda[turno.agenda.id] = {
                    'agenda': turno.agenda,
                    'coordinados': [],
                    'no_coordinados': [],
                    **agendas_disponibilidad.get(turno.agenda.id, {
                        'capacidad': 0, 'usados': 0, 'disponibles': 0
                    })
                }
            if turno.id in turnos_coordinados_ids:
                turnos_por_agenda[turno.agenda.id]['coordinados'].append(turno)
            else:
                turnos_por_agenda[turno.agenda.id]['no_coordinados'].append(turno)

        # Agregar agendas con disponibilidad pero sin turnos
        for agenda_id, info in agendas_disponibilidad.items():
            if agenda_id not in turnos_por_agenda and info['capacidad'] > 0:
                turnos_por_agenda[agenda_id] = {
                    'agenda': info['agenda'],
                    'coordinados': [],
                    'no_coordinados': [],
                    'capacidad': info['capacidad'],
                    'usados': info['usados'],
                    'disponibles': info['disponibles']
                }
    else:
        turnos_por_agenda = None

    context = {
        'fecha': fecha,
        'turnos': turnos,
        'turnos_por_agenda': turnos_por_agenda,
        'modo_vista': modo_vista,
        'form': form,
        'cupo': cupo,
        'disponibles': disponibles,
        'agenda_name': agenda_obj.name if agenda_obj else (cupo.agenda.name if cupo else ''),
        'show_form': (disponibles > 0 and agenda_obj and modo_vista == 'agenda_seleccionada' and not es_feriado),
        'es_feriado': es_feriado,
        'descripcion_feriado': descripcion_feriado
    }
    return render(request, 'turnos/dia.html', context)


@login_required
def buscar(request):
    """Búsqueda de turnos por DNI, apellido o ID de turno."""
    q = request.GET.get('q', '').strip()
    turno_id = request.GET.get('turno_id', '').strip()
    apellido = request.GET.get('apellido', '').strip()
    resultados = []
    turnos_previos = []
    turnos_pendientes = []
    
    if q or turno_id or apellido:
        # Buscar por DNI, apellido o por ID de turno
        if turno_id:
            resultados = Turno.objects.filter(id=turno_id).select_related('dni', 'agenda')
        elif apellido:
            resultados = Turno.objects.filter(
                dni__apellido__icontains=apellido
            ).select_related('dni', 'agenda').order_by('-fecha')
        else:
            resultados = Turno.objects.filter(
                dni__iden__icontains=q
            ).select_related('dni', 'agenda').order_by('-fecha')
            
        hoy = date.today()
        
        # Obtener IDs de turnos coordinados
        turnos_coordinados_ids = set(Coordinados.objects.values_list('id_turno', flat=True))
        
        # Procesar cada turno
        for turno in resultados:
            turno.esta_coordinado = turno.id in turnos_coordinados_ids
            
            # Obtener nombres de determinaciones
            if turno.determinaciones:
                nombres = DeterminacionService.obtener_nombres_determinaciones(turno.determinaciones)
                turno.determinaciones_nombres = ', '.join(nombres) if nombres else turno.determinaciones
            else:
                turno.determinaciones_nombres = ''
            
            # Separar en previos y pendientes
            if turno.fecha < hoy:
                turnos_previos.append(turno)
            else:
                turnos_pendientes.append(turno)
    
    return render(request, 'turnos/buscar.html', {
        'turnos_previos': turnos_previos,
        'turnos_pendientes': turnos_pendientes,
        'q': q,
        'turno_id': turno_id,
        'apellido': apellido,
        'hoy': date.today()
    })


@login_required
def editar_turno(request, turno_id):
    """Editar un turno existente."""
    turno = get_object_or_404(Turno, id=turno_id)
    
    # Obtener datos del paciente
    paciente_data = TurnoService.obtener_datos_paciente(turno)
    
    if request.method == 'POST':
        # Usar el servicio para actualizar
        exito, mensaje = TurnoService.actualizar_turno(
            turno=turno,
            agenda_id=request.POST.get('agenda'),
            fecha=request.POST.get('fecha'),
            determinaciones=request.POST.get('determinaciones', ''),
            medico_nombre=request.POST.get('medico', ''),
            nota_interna=request.POST.get('nota_interna', ''),
            telefono=request.POST.get('telefono', ''),
            email=request.POST.get('email', ''),
            observaciones_paciente=request.POST.get('observaciones_paciente', '')
        )
        
        if exito:
            return redirect(reverse('turnos:dia', args=[turno.fecha]) + f'?agenda={turno.agenda.id}')
        else:
            messages.error(request, mensaje)
    
    # Obtener todas las agendas
    agendas = Agenda.objects.all()
    
    context = {
        'turno': turno,
        'paciente': paciente_data,
        'agendas': agendas,
        'es_edicion': True,
    }
    return render(request, 'turnos/editar_turno.html', context)


@login_required
def eliminar_turno(request, turno_id):
    """Eliminar un turno con confirmación."""
    turno = get_object_or_404(Turno, id=turno_id)
    fecha = turno.fecha
    agenda_id = turno.agenda.id
    
    if request.method == 'POST':
        turno.delete()
        return redirect(reverse('turnos:dia', args=[fecha]) + f'?agenda={agenda_id}')
    
    context = {
        'turno': turno,
    }
    return render(request, 'turnos/confirmar_eliminar.html', context)
