from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponseBadRequest
from django.contrib.auth.decorators import login_required, user_passes_test
from django.urls import reverse
from .models import Cupo, Turno, CapacidadDia, Agenda
from .forms import TurnoForm, CupoForm
from django.db import IntegrityError, transaction
from django.core.exceptions import ValidationError
import json
from django.contrib import messages
from django.contrib.auth import logout
from django.conf import settings


@login_required
def calendario(request):
    # Mostrar todos los Cupos de todas las agendas en el mismo calendario
    # Usar Cupo explícitos + disponibilidad semanal para construir eventos
    eventos = []

    # 1) Eventos por Cupo explícito
    cupos = Cupo.objects.select_related('agenda').all().order_by('fecha')
    for cupo in cupos:
        libres = cupo.disponibles()
        usados = Turno.objects.filter(fecha=cupo.fecha, agenda=cupo.agenda).count()
        color = "#f44336" if libres == 0 else (cupo.agenda.color if cupo.agenda.color else "#4caf50")
        eventos.append({
            "title": f"{cupo.agenda.name}: {libres}/{cupo.cantidad_total} libres",
            "start": cupo.fecha.isoformat(),
            "allDay": True,
            "color": color,
            "extendedProps": {
                "fecha": cupo.fecha.isoformat(),
                "disponibles": libres,
                "total": cupo.cantidad_total,
                "usados": usados,
                "has_cupo": True,
                "agenda_id": cupo.agenda.id,
                "agenda_name": cupo.agenda.name
            }
        })

    # 2) Generar eventos calculados para los próximos X días según WeeklyAvailability
    from datetime import date, timedelta
    horizon_days = 60
    today = date.today()
    agendas = Agenda.objects.all()
    for delta in range(horizon_days):
        d = today + timedelta(days=delta)
        for ag in agendas:
            # saltar si ya existe un Cupo explícito para esa agenda+fecha
            if Cupo.objects.filter(agenda=ag, fecha=d).exists():
                continue
            capacidad = ag.get_capacity_for_date(d)
            if capacidad <= 0:
                continue
            usados = Turno.objects.filter(fecha=d, agenda=ag).count()
            libres = max(capacidad - usados, 0)
            color = "#f44336" if libres == 0 else (ag.color if ag.color else "#4caf50")
            eventos.append({
                "title": f"{ag.name}: {libres}/{capacidad} libres",
                "start": d.isoformat(),
                "allDay": True,
                "color": color,
                "extendedProps": {
                    "fecha": d.isoformat(),
                    "disponibles": libres,
                    "total": capacidad,
                    "usados": usados,
                    "has_cupo": False,
                    "agenda_id": ag.id,
                    "agenda_name": ag.name
                }
            })

    agendas = Agenda.objects.all()
    return render(request, "turnos/calendario.html", {"eventos": eventos, 'agendas': agendas})



@user_passes_test(lambda u: u.is_superuser)
def nuevo_cupo(request):
    """Crear un Cupo nuevo desde la UI. Accesible solo para superusuarios."""
    if request.method == 'POST':
        form = CupoForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect(reverse('turnos:calendario'))
    else:
        form = CupoForm()
    return render(request, 'turnos/cupo_form.html', {'form': form})



@login_required
def eventos_calendario(request):
    eventos = []
    cupos = Cupo.objects.select_related('agenda').all()
    for c in cupos:
        libres = c.disponibles()
        eventos.append({
            "title": f"{c.agenda.name}: {libres} libres" if libres > 0 else f"{c.agenda.name}: Completo",
            "start": c.fecha.isoformat(),
            "allDay": True,
            "color": c.agenda.color if c.agenda and c.agenda.color else ("green" if libres > 0 else "red"),
            "extendedProps": {"agenda_id": c.agenda.id, "agenda_name": c.agenda.name}
        })
    return JsonResponse(eventos, safe=False)


@login_required
def dia(request, fecha):
    # Convertir fecha a objeto date si viene como string
    from datetime import datetime
    if isinstance(fecha, str):
        fecha = datetime.strptime(fecha, '%Y-%m-%d').date()
    
    # Mostrar turnos para la(s) agendas en la fecha.
    turnos_all = Turno.objects.filter(fecha=fecha).select_related('agenda')
    cupos_qs = Cupo.objects.select_related('agenda').filter(fecha=fecha)

    # Si se pasó ?agenda=<id>, trabajamos sobre esa agenda
    agenda_id = request.GET.get('agenda')
    cupo = None
    disponibles = 0
    agenda_obj = None
    turnos = turnos_all
    modo_vista = 'todas_agendas'  # por defecto mostrar todas las agendas

    if agenda_id:
        try:
            agenda_obj = Agenda.objects.get(id=agenda_id)
            turnos = turnos_all.filter(agenda__id=agenda_id)
            modo_vista = 'agenda_seleccionada'
        except Agenda.DoesNotExist:
            agenda_obj = None

        if agenda_obj:
            # Intentar obtener Cupo explícito
            try:
                cupo = cupos_qs.get(agenda=agenda_obj)
                disponibles = cupo.disponibles()
            except Cupo.DoesNotExist:
                # Si no hay Cupo explícito, usar WeeklyAvailability
                capacidad = agenda_obj.get_capacity_for_date(fecha)
                if capacidad > 0:
                    usados = Turno.objects.filter(fecha=fecha, agenda=agenda_obj).count()
                    disponibles = max(capacidad - usados, 0)
                else:
                    disponibles = 0
    # Si no hay agenda_id, modo_vista es 'todas_agendas' (sin formulario)

    if request.method == 'POST':
        form = TurnoForm(request.POST)
        if form.is_valid():
            try:
                # Usar transacción para evitar sobre-reservas concurrentes
                with transaction.atomic():
                    agenda_form = form.cleaned_data.get('agenda')
                    
                    # Intentar obtener Cupo explícito (con bloqueo)
                    cupo_lock = None
                    try:
                        cupo_lock = Cupo.objects.select_for_update().get(fecha=fecha, agenda=agenda_form)
                    except Cupo.DoesNotExist:
                        pass
                    
                    # Validar capacidad (Cupo explícito o WeeklyAvailability)
                    if cupo_lock:
                        capacidad = cupo_lock.cantidad_total
                    else:
                        capacidad = agenda_form.get_capacity_for_date(fecha)
                    
                    usados = Turno.objects.filter(fecha=fecha, agenda=agenda_form).count()
                    
                    if capacidad <= 0:
                        form.add_error(None, ValidationError("No hay disponibilidad para esta fecha y agenda."))
                    elif usados >= capacidad:
                        form.add_error(None, ValidationError("La fecha está completa para esta agenda."))
                    else:
                        # Crear el turno
                        nuevo = form.save(commit=False)
                        nuevo.fecha = fecha
                        nuevo.full_clean()
                        nuevo.save()
                        return redirect(f"{reverse('turnos:dia', args=[fecha])}?agenda={agenda_form.id}")
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
            # Calcular capacidad y disponibilidad
            try:
                cupo_ag = Cupo.objects.get(agenda=ag, fecha=fecha)
                capacidad = cupo_ag.cantidad_total
            except Cupo.DoesNotExist:
                capacidad = ag.get_capacity_for_date(fecha)
            
            if capacidad > 0:
                usados = Turno.objects.filter(fecha=fecha, agenda=ag).count()
                disponibles_ag = max(capacidad - usados, 0)
                
                agendas_disponibilidad[ag.id] = {
                    'agenda': ag,
                    'capacidad': capacidad,
                    'usados': usados,
                    'disponibles': disponibles_ag
                }
        
        # Agrupar turnos por agenda
        for turno in turnos_all:
            if turno.agenda.id not in turnos_por_agenda:
                turnos_por_agenda[turno.agenda.id] = {
                    'agenda': turno.agenda,
                    'turnos': [],
                    'capacidad': agendas_disponibilidad.get(turno.agenda.id, {}).get('capacidad', 0),
                    'usados': agendas_disponibilidad.get(turno.agenda.id, {}).get('usados', 0),
                    'disponibles': agendas_disponibilidad.get(turno.agenda.id, {}).get('disponibles', 0)
                }
            turnos_por_agenda[turno.agenda.id]['turnos'].append(turno)
        
        # Agregar agendas con disponibilidad pero sin turnos
        for agenda_id, info in agendas_disponibilidad.items():
            if agenda_id not in turnos_por_agenda:
                turnos_por_agenda[agenda_id] = {
                    'agenda': info['agenda'],
                    'turnos': [],
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
        # Mostrar formulario solo si hay disponibles Y una agenda específica seleccionada
        'show_form': True if (disponibles > 0 and agenda_obj and modo_vista == 'agenda_seleccionada') else False
    }
    return render(request, 'turnos/dia.html', context)


@login_required
def buscar(request):
    q = request.GET.get('q', '').strip()
    resultados = []
    if q:
        resultados = Turno.objects.filter(dni__icontains=q).order_by('-fecha')
    return render(request, 'turnos/buscar.html', {'resultados': resultados, 'q': q})


@login_required
def editar_turno(request, turno_id):
    """Editar un turno existente."""
    turno = get_object_or_404(Turno, id=turno_id)
    
    if request.method == 'POST':
        form = TurnoForm(request.POST, instance=turno)
        if form.is_valid():
            form.save()
            return redirect(reverse('turnos:dia', args=[turno.fecha]) + f'?agenda={turno.agenda.id}')
    else:
        form = TurnoForm(instance=turno)
    
    context = {
        'form': form,
        'turno': turno,
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


def logout_view(request):
    """Accept GET and POST. POST logs out the user. GET redirects to login."""
    if request.method == 'POST':
        # No mostrar ningún mensaje al hacer logout (quitar notificación de 'Has cerrado sesión')
        logout(request)
        return redirect(settings.LOGOUT_REDIRECT_URL or '/accounts/login/')
    # For GET requests, just redirect to the login page (avoid 405)
    return redirect(settings.LOGOUT_REDIRECT_URL or '/accounts/login/')



@user_passes_test(lambda u: u.is_superuser)
def generar_cupos_masivo(request):
    """Vista para generar cupos masivamente. Solo superusuarios."""
    from datetime import datetime, timedelta
    
    agendas = Agenda.objects.all()
    
    if request.method == 'POST':
        try:
            agenda_id = request.POST.get('agenda')
            desde_fecha = request.POST.get('desde_fecha')
            hasta_fecha = request.POST.get('hasta_fecha')
            cantidad = request.POST.get('cantidad')
            por_dia_semana = request.POST.get('por_dia_semana') == 'on'
            dia_semana = request.POST.get('dia_semana')
            
            # Validaciones
            if not all([agenda_id, desde_fecha, hasta_fecha, cantidad]):
                messages.error(request, "Todos los campos obligatorios deben estar completos.")
                return render(request, 'turnos/generar_cupos.html', {'agendas': agendas})
            
            agenda = Agenda.objects.get(id=agenda_id)
            desde = datetime.strptime(desde_fecha, '%Y-%m-%d').date()
            hasta = datetime.strptime(hasta_fecha, '%Y-%m-%d').date()
            cantidad_int = int(cantidad)
            
            if desde > hasta:
                messages.error(request, "La fecha 'Desde' no puede ser posterior a 'Hasta'.")
                return render(request, 'turnos/generar_cupos.html', {'agendas': agendas})
            
            # Generar cupos
            cupos_creados = 0
            cupos_actualizados = 0
            fecha_actual = desde
            
            while fecha_actual <= hasta:
                # Verificar si es fin de semana (sábado=5, domingo=6)
                if fecha_actual.weekday() >= 5:
                    fecha_actual += timedelta(days=1)
                    continue
                
                # Si está activado "por día de semana", verificar el día
                if por_dia_semana:
                    if dia_semana and fecha_actual.weekday() != int(dia_semana):
                        fecha_actual += timedelta(days=1)
                        continue
                
                # Crear o actualizar cupo
                cupo, created = Cupo.objects.get_or_create(
                    agenda=agenda,
                    fecha=fecha_actual,
                    defaults={'cantidad_total': cantidad_int}
                )
                
                if created:
                    cupos_creados += 1
                else:
                    # Actualizar cantidad si ya existía
                    cupo.cantidad_total = cantidad_int
                    cupo.save()
                    cupos_actualizados += 1
                
                fecha_actual += timedelta(days=1)
            
            total = cupos_creados + cupos_actualizados
            if total > 0:
                msg = f"✅ Proceso completado: {cupos_creados} cupos creados"
                if cupos_actualizados > 0:
                    msg += f", {cupos_actualizados} actualizados"
                msg += f" para {agenda.name}."
                messages.success(request, msg)
            else:
                messages.warning(request, "No se generaron cupos. Verifica el rango de fechas y el día seleccionado.")
            
            return redirect('turnos:generar_cupos_masivo')
            
        except Agenda.DoesNotExist:
            messages.error(request, "La agenda seleccionada no existe.")
        except ValueError as e:
            messages.error(request, f"Error en los datos ingresados: {str(e)}")
        except Exception as e:
            messages.error(request, f"Error inesperado: {str(e)}")
    
    return render(request, 'turnos/generar_cupos.html', {'agendas': agendas})


@user_passes_test(lambda u: u.is_superuser)
def borrar_cupos_masivo(request):
    """Vista para borrar cupos masivamente. Solo superusuarios. Los turnos NO se borran."""
    from datetime import datetime, timedelta
    
    if request.method == 'POST':
        try:
            agenda_id = request.POST.get('agenda')
            desde_fecha = request.POST.get('desde_fecha')
            hasta_fecha = request.POST.get('hasta_fecha')
            por_dia_semana = request.POST.get('por_dia_semana') == 'on'
            dia_semana = request.POST.get('dia_semana')
            cantidad_a_borrar = request.POST.get('cantidad_a_borrar')
            
            # Convertir cantidad si existe
            cantidad_a_borrar = int(cantidad_a_borrar) if cantidad_a_borrar else None
            
            # Validaciones
            if not all([agenda_id, desde_fecha, hasta_fecha]):
                messages.error(request, "Todos los campos obligatorios deben estar completos.")
                return redirect('turnos:generar_cupos_masivo')
            
            agenda = Agenda.objects.get(id=agenda_id)
            desde = datetime.strptime(desde_fecha, '%Y-%m-%d').date()
            hasta = datetime.strptime(hasta_fecha, '%Y-%m-%d').date()
            
            if desde > hasta:
                messages.error(request, "La fecha 'Desde' no puede ser posterior a 'Hasta'.")
                return redirect('turnos:generar_cupos_masivo')
            
            # Borrar o reducir cupos
            cupos_eliminados = 0
            cupos_reducidos = 0
            fecha_actual = desde
            
            while fecha_actual <= hasta:
                # Verificar si es fin de semana
                if fecha_actual.weekday() >= 5:
                    fecha_actual += timedelta(days=1)
                    continue
                
                # Si está activado "por día de semana", verificar el día
                if por_dia_semana:
                    if dia_semana and fecha_actual.weekday() != int(dia_semana):
                        fecha_actual += timedelta(days=1)
                        continue
                
                # Obtener cupo existente
                try:
                    with transaction.atomic():
                        cupo = Cupo.objects.select_for_update().get(
                            agenda=agenda,
                            fecha=fecha_actual
                        )
                        
                        # Si no se especificó cantidad, o la cantidad es mayor o igual al total, eliminar el cupo
                        if cantidad_a_borrar is None or cantidad_a_borrar >= cupo.cantidad_total:
                            cupo.delete()
                            cupos_eliminados += 1
                        else:
                            # Reducir la cantidad total
                            cupo.cantidad_total -= cantidad_a_borrar
                            if cupo.cantidad_total <= 0:
                                cupo.delete()
                                cupos_eliminados += 1
                            else:
                                cupo.save()
                                cupos_reducidos += 1
                                
                except Cupo.DoesNotExist:
                    pass  # No hay cupo para esta fecha
                
                fecha_actual += timedelta(days=1)
            
            if cupos_eliminados > 0 or cupos_reducidos > 0:
                mensaje = []
                if cupos_eliminados > 0:
                    mensaje.append(f"{cupos_eliminados} cupo(s) eliminado(s)")
                if cupos_reducidos > 0:
                    mensaje.append(f"{cupos_reducidos} cupo(s) reducido(s)")
                messages.success(request, f"✅ {' y '.join(mensaje)} para {agenda.name}. Los turnos agendados se mantienen.")
            else:
                messages.warning(request, "No se encontraron cupos para modificar en el rango especificado.")
            
            return redirect('turnos:generar_cupos_masivo')
            
        except Agenda.DoesNotExist:
            messages.error(request, "La agenda seleccionada no existe.")
        except ValueError as e:
            messages.error(request, f"Error en los datos ingresados: {str(e)}")
        except Exception as e:
            messages.error(request, f"Error inesperado: {str(e)}")
    
    return redirect('turnos:generar_cupos_masivo')
