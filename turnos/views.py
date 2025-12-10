from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponse
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
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from io import BytesIO
from datetime import datetime


@login_required
def calendario(request):
    import psycopg2
    # Mostrar todos los Cupos de todas las agendas en el mismo calendario
    # Usar Cupo explícitos + disponibilidad semanal para construir eventos
    from datetime import date, timedelta
    eventos = []
    hoy = date.today()

    # 0) Obtener feriados desde PostgreSQL
    feriados_dict = {}
    try:
        conn = psycopg2.connect(
            dbname='Laboratorio',
            user='postgres',
            password='estufa10',
            host='localhost',
            port='5432'
        )
        cursor = conn.cursor()
        cursor.execute("SELECT fecha, descripcion FROM feriados")
        for fecha_fer, descripcion in cursor.fetchall():
            feriados_dict[fecha_fer] = descripcion
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error al cargar feriados: {e}")

    # Agregar eventos de feriados al calendario
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

    # 1) Eventos por Cupo explícito
    cupos = Cupo.objects.select_related('agenda').all().order_by('fecha')
    for cupo in cupos:
        # Saltar si es feriado
        if cupo.fecha in feriados_dict:
            continue
            
        libres = cupo.disponibles()
        usados = Turno.objects.filter(fecha=cupo.fecha, agenda=cupo.agenda).count()
        es_pasado = cupo.fecha < hoy
        
        # Determinar color y título según disponibilidad
        if libres == 0:
            color_claro = "#ff4444"  # Rojo fuerte para completo
            titulo = f"{cupo.agenda.name}: Completo"
            texto_tachado = True
        else:
            color_original = cupo.agenda.color if cupo.agenda.color else "#4caf50"
            color_claro = lighten_color(color_original)
            titulo = f"{cupo.agenda.name}: {libres}/{cupo.cantidad_total}"
            texto_tachado = False
        
        eventos.append({
            "title": titulo,
            "start": cupo.fecha.isoformat(),
            "allDay": True,
            "color": color_claro,
            "textColor": "#000000",
            "extendedProps": {
                "fecha": cupo.fecha.isoformat(),
                "disponibles": libres,
                "total": cupo.cantidad_total,
                "usados": usados,
                "has_cupo": True,
                "agenda_id": cupo.agenda.id,
                "agenda_name": cupo.agenda.name,
                "es_pasado": es_pasado,
                "completo": libres == 0,
                "texto_tachado": texto_tachado
            }
        })

    # 2) Generar eventos calculados para los próximos X días según WeeklyAvailability
    horizon_days = 60
    today = date.today()
    agendas = Agenda.objects.all()
    for delta in range(horizon_days):
        d = today + timedelta(days=delta)
        # Saltar si es feriado
        if d in feriados_dict:
            continue
        for ag in agendas:
            # saltar si ya existe un Cupo explícito para esa agenda+fecha
            if Cupo.objects.filter(agenda=ag, fecha=d).exists():
                continue
            capacidad = ag.get_capacity_for_date(d)
            if capacidad <= 0:
                continue
            usados = Turno.objects.filter(fecha=d, agenda=ag).count()
            libres = max(capacidad - usados, 0)
            es_pasado = d < hoy
            
            # Determinar color y título según disponibilidad
            if libres == 0:
                color_claro = "#ff4444"  # Rojo fuerte para completo
                titulo = f"{ag.name}: Completo"
                texto_tachado = True
            else:
                color_original = ag.color if ag.color else "#4caf50"
                color_claro = lighten_color(color_original)
                titulo = f"{ag.name}: {libres}/{capacidad}"
                texto_tachado = False
            
            eventos.append({
                "title": titulo,
                "start": d.isoformat(),
                "allDay": True,
                "color": color_claro,
                "textColor": "#000000",
                "extendedProps": {
                    "fecha": d.isoformat(),
                    "disponibles": libres,
                    "total": capacidad,
                    "usados": usados,
                    "has_cupo": False,
                    "agenda_id": ag.id,
                    "agenda_name": ag.name,
                    "es_pasado": es_pasado,
                    "completo": libres == 0,
                    "texto_tachado": texto_tachado
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


def lighten_color(color_hex, factor=0.6):
    """Aclara un color hexadecimal. factor: 0.0 (original) a 1.0 (blanco)"""
    if not color_hex or not color_hex.startswith('#'):
        return color_hex
    
    color_hex = color_hex.lstrip('#')
    try:
        r = int(color_hex[0:2], 16)
        g = int(color_hex[2:4], 16)
        b = int(color_hex[4:6], 16)
        
        r = int(r + (255 - r) * factor)
        g = int(g + (255 - g) * factor)
        b = int(b + (255 - b) * factor)
        
        return f'#{r:02x}{g:02x}{b:02x}'
    except:
        return color_hex


@login_required
def eventos_calendario(request):
    import psycopg2
    from datetime import date
    eventos = []
    hoy = date.today()
    
    # 1. Obtener feriados desde PostgreSQL
    feriados_dict = {}
    try:
        conn = psycopg2.connect(
            dbname='Laboratorio',
            user='postgres',
            password='estufa10',
            host='localhost',
            port='5432'
        )
        cursor = conn.cursor()
        cursor.execute("SELECT fecha, descripcion FROM feriados")
        for fecha_fer, descripcion in cursor.fetchall():
            feriados_dict[fecha_fer] = descripcion
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error al cargar feriados: {e}")
    
    # 2. Agregar eventos de feriados al calendario
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
    
    # 3. Eventos por Cupo explícito
    cupos = Cupo.objects.select_related('agenda').all()
    for c in cupos:
        # No mostrar cupo si es feriado
        if c.fecha in feriados_dict:
            continue
            
        libres = c.disponibles()
        es_pasado = c.fecha < hoy
        
        # Determinar color y título según disponibilidad
        if libres == 0:
            color_claro = "#ff4444"  # Rojo fuerte para completo
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
    """Devuelve los turnos de un día pasado agrupados por agenda y coordinación"""
    from datetime import datetime
    fecha_obj = datetime.strptime(fecha, '%Y-%m-%d').date()
    
    turnos = Turno.objects.filter(fecha=fecha_obj).select_related('agenda').order_by('agenda__name', 'coordinado', 'apellido', 'nombre')
    
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
            'dni': turno.dni,
            'nombre': turno.nombre,
            'apellido': turno.apellido,
            'determinaciones': turno.determinaciones,
            'coordinado': turno.coordinado
        }
        
        if turno.coordinado:
            agendas_dict[agenda_name]['coordinados'].append(turno_data)
        else:
            agendas_dict[agenda_name]['no_coordinados'].append(turno_data)
    
    return JsonResponse({
        'fecha': fecha,
        'agendas': agendas_dict,
        'total_turnos': turnos.count()
    })


@login_required
def dia(request, fecha):
    import psycopg2
    # Convertir fecha a objeto date si viene como string
    from datetime import datetime
    if isinstance(fecha, str):
        fecha = datetime.strptime(fecha, '%Y-%m-%d').date()
    
    # Verificar si es feriado
    es_feriado = False
    descripcion_feriado = None
    try:
        conn = psycopg2.connect(
            dbname='Laboratorio',
            user='postgres',
            password='estufa10',
            host='localhost',
            port='5432'
        )
        cursor = conn.cursor()
        cursor.execute("SELECT descripcion FROM feriados WHERE fecha = %s", (fecha,))
        resultado = cursor.fetchone()
        if resultado:
            es_feriado = True
            descripcion_feriado = resultado[0]
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error al verificar feriado: {e}")
    
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
                    import psycopg2
                    from django.conf import settings
                    
                    agenda_form = form.cleaned_data.get('agenda')
                    dni = form.cleaned_data.get('dni')
                    nombre = form.cleaned_data.get('nombre')
                    apellido = form.cleaned_data.get('apellido')
                    fecha_nacimiento = form.cleaned_data.get('fecha_nacimiento')
                    sexo = form.cleaned_data.get('sexo')
                    telefono = form.cleaned_data.get('telefono', '')
                    email = form.cleaned_data.get('email', '')
                    medico = form.cleaned_data.get('medico', '')  # Este va al turno, no al paciente
                    nota_interna = form.cleaned_data.get('nota_interna', '')  # Este va al turno
                    
                    # Guardar o actualizar paciente en PostgreSQL
                    conn = psycopg2.connect(
                        dbname=settings.DATABASES['default']['NAME'],
                        user=settings.DATABASES['default']['USER'],
                        password=settings.DATABASES['default']['PASSWORD'],
                        host=settings.DATABASES['default']['HOST'],
                        port=settings.DATABASES['default']['PORT']
                    )
                    cursor = conn.cursor()
                    
                    # Verificar si el paciente existe
                    cursor.execute("SELECT id FROM pacientes WHERE dni = %s", (dni,))
                    paciente_existe = cursor.fetchone()
                    
                    if paciente_existe:
                        # Actualizar paciente (no actualizamos usuario en updates)
                        cursor.execute("""
                            UPDATE pacientes 
                            SET nombre = %s, apellido = %s, fecha_nacimiento = %s, sexo = %s,
                                telefono = %s, email = %s
                            WHERE dni = %s
                        """, (nombre, apellido, fecha_nacimiento, sexo, telefono, email, dni))
                    else:
                        # Crear nuevo paciente
                        cursor.execute("""
                            INSERT INTO pacientes (nombre, apellido, dni, fecha_nacimiento, sexo, telefono, email, usuario)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """, (nombre, apellido, dni, fecha_nacimiento, sexo, telefono, email, request.user.username))
                    
                    conn.commit()
                    cursor.close()
                    conn.close()
                    
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
                        nuevo.medico = medico
                        nuevo.nota_interna = nota_interna
                        nuevo.usuario = request.user.username
                        nuevo.full_clean()
                        nuevo.save()
                        
                        # Redirigir con parámetro para abrir PDF
                        return redirect(f"{reverse('turnos:dia', args=[fecha])}?agenda={agenda_form.id}&turno_creado={nuevo.id}")
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
            
            # Contar turnos para esta agenda
            usados = Turno.objects.filter(fecha=fecha, agenda=ag).count()
            
            # Incluir agenda si tiene capacidad O si tiene turnos (para fechas pasadas)
            if capacidad > 0 or usados > 0:
                disponibles_ag = max(capacidad - usados, 0) if capacidad > 0 else 0
                
                agendas_disponibilidad[ag.id] = {
                    'agenda': ag,
                    'capacidad': capacidad if capacidad > 0 else usados,  # Mostrar al menos los usados si no hay capacidad
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
        
        # Agregar agendas con disponibilidad pero sin turnos (solo para fechas futuras con capacidad)
        for agenda_id, info in agendas_disponibilidad.items():
            if agenda_id not in turnos_por_agenda and info['capacidad'] > 0:
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
        # Mostrar formulario solo si hay disponibles Y una agenda específica seleccionada Y NO es feriado
        'show_form': True if (disponibles > 0 and agenda_obj and modo_vista == 'agenda_seleccionada' and not es_feriado) else False,
        'es_feriado': es_feriado,
        'descripcion_feriado': descripcion_feriado
    }
    return render(request, 'turnos/dia.html', context)


@login_required
def buscar(request):
    import psycopg2
    from datetime import date
    from .models import Coordinados
    
    q = request.GET.get('q', '').strip()
    resultados = []
    turnos_previos = []
    turnos_pendientes = []
    
    if q:
        resultados = Turno.objects.filter(dni__icontains=q).order_by('-fecha')
        hoy = date.today()
        
        # Obtener IDs de turnos coordinados
        turnos_coordinados_ids = set(Coordinados.objects.values_list('id_turno', flat=True))
        
        # Conectar a PostgreSQL para obtener nombres de determinaciones/perfiles
        conn = psycopg2.connect(
            dbname=settings.DATABASES['default']['NAME'],
            user=settings.DATABASES['default']['USER'],
            password=settings.DATABASES['default']['PASSWORD'],
            host=settings.DATABASES['default']['HOST'],
            port=settings.DATABASES['default']['PORT']
        )
        cursor = conn.cursor()
        
        # Separar turnos en previos y pendientes y agregar nombres de determinaciones
        for turno in resultados:
            # Verificar si está coordinado
            turno.esta_coordinado = turno.id in turnos_coordinados_ids
            
            # Procesar determinaciones para obtener nombres
            if turno.determinaciones:
                codigos = [c.strip() for c in turno.determinaciones.split(',') if c.strip()]
                nombres = []
                
                for codigo in codigos:
                    if codigo.startswith('/'):
                        # Es un perfil
                        cursor.execute("SELECT nombre FROM perfiles WHERE codigo = %s", (codigo,))
                        result = cursor.fetchone()
                        if result:
                            nombres.append(result[0])
                    else:
                        # Es una determinación
                        cursor.execute("SELECT nombre FROM determinaciones WHERE codigo = %s", (int(codigo),))
                        result = cursor.fetchone()
                        if result:
                            nombres.append(result[0])
                
                turno.determinaciones_nombres = ', '.join(nombres) if nombres else turno.determinaciones
            else:
                turno.determinaciones_nombres = ''
            
            if turno.fecha < hoy:
                turnos_previos.append(turno)
            else:
                turnos_pendientes.append(turno)
        
        cursor.close()
        conn.close()
    
    return render(request, 'turnos/buscar.html', {
        'turnos_previos': turnos_previos,
        'turnos_pendientes': turnos_pendientes,
        'q': q,
        'hoy': date.today()
    })


@login_required
def editar_turno(request, turno_id):
    """Editar un turno existente."""
    import psycopg2
    turno = get_object_or_404(Turno, id=turno_id)
    
    # Obtener datos del paciente desde PostgreSQL
    paciente_data = None
    try:
        conn = psycopg2.connect(
            dbname=settings.DATABASES['default']['NAME'],
            user=settings.DATABASES['default']['USER'],
            password=settings.DATABASES['default']['PASSWORD'],
            host=settings.DATABASES['default']['HOST'],
            port=settings.DATABASES['default']['PORT']
        )
        cursor = conn.cursor()
        cursor.execute(
            "SELECT nombre, apellido, dni, fecha_nacimiento, sexo, telefono, email FROM pacientes WHERE dni = %s",
            (turno.dni,)
        )
        result = cursor.fetchone()
        if result:
            paciente_data = {
                'nombre': result[0],
                'apellido': result[1],
                'dni': result[2],
                'fecha_nacimiento': result[3],
                'sexo': result[4],
                'telefono': result[5],
                'email': result[6]
            }
        cursor.close()
        conn.close()
    except Exception as e:
        pass
    
    if request.method == 'POST':
        # Actualizar turno (agenda, fecha, determinaciones, medico y nota_interna)
        turno.agenda_id = request.POST.get('agenda')
        turno.fecha = request.POST.get('fecha')
        turno.determinaciones = request.POST.get('determinaciones', '')
        turno.medico = request.POST.get('medico', '')
        turno.nota_interna = request.POST.get('nota_interna', '')
        turno.save()
        
        # Actualizar datos del paciente si se enviaron (telefono y email)
        telefono = request.POST.get('telefono', '')
        email = request.POST.get('email', '')
        
        if telefono or email:
            try:
                conn = psycopg2.connect(
                    dbname=settings.DATABASES['default']['NAME'],
                    user=settings.DATABASES['default']['USER'],
                    password=settings.DATABASES['default']['PASSWORD'],
                    host=settings.DATABASES['default']['HOST'],
                    port=settings.DATABASES['default']['PORT']
                )
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE pacientes 
                    SET telefono = %s, email = %s
                    WHERE dni = %s
                """, (telefono, email, turno.dni))
                conn.commit()
                cursor.close()
                conn.close()
            except Exception as e:
                pass
        
        return redirect(reverse('turnos:dia', args=[turno.fecha]) + f'?agenda={turno.agenda.id}')
    
    # Obtener todas las agendas
    from .models import Agenda
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
                    defaults={'cantidad_total': cantidad_int, 'usuario': request.user.username}
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


@login_required
def buscar_paciente_api(request):
    """API para buscar paciente por DNI en PostgreSQL"""
    import psycopg2
    from django.conf import settings
    
    dni = request.GET.get('dni', '').strip()
    if not dni:
        return JsonResponse({'found': False})
    
    try:
        conn = psycopg2.connect(
            dbname=settings.DATABASES['default']['NAME'],
            user=settings.DATABASES['default']['USER'],
            password=settings.DATABASES['default']['PASSWORD'],
            host=settings.DATABASES['default']['HOST'],
            port=settings.DATABASES['default']['PORT']
        )
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT nombre, apellido, fecha_nacimiento, sexo, telefono, email FROM pacientes WHERE dni = %s",
            (dni,)
        )
        result = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if result:
            return JsonResponse({
                'found': True,
                'nombre': result[0],
                'apellido': result[1],
                'fecha_nacimiento': result[2].isoformat() if result[2] else '',
                'sexo': result[3],
                'telefono': result[4] or '',
                'email': result[5] or ''
            })
        else:
            return JsonResponse({'found': False})
            
    except Exception as e:
        return JsonResponse({'found': False, 'error': str(e)})


@login_required
def buscar_determinacion_api(request):
    """API para buscar determinación por código en PostgreSQL"""
    import psycopg2
    from django.conf import settings
    
    codigo = request.GET.get('codigo', '').strip()
    if not codigo:
        return JsonResponse({'found': False})
    
    try:
        conn = psycopg2.connect(
            dbname=settings.DATABASES['default']['NAME'],
            user=settings.DATABASES['default']['USER'],
            password=settings.DATABASES['default']['PASSWORD'],
            host=settings.DATABASES['default']['HOST'],
            port=settings.DATABASES['default']['PORT']
        )
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT codigo, nombre FROM determinaciones WHERE codigo = %s",
            (int(codigo),)
        )
        result = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if result:
            return JsonResponse({
                'found': True,
                'codigo': result[0],
                'nombre': result[1]
            })
        else:
            return JsonResponse({'found': False})
            
    except Exception as e:
        return JsonResponse({'found': False, 'error': str(e)})


@login_required
def listar_determinaciones_api(request):
    """API para listar todas las determinaciones y perfiles"""
    import psycopg2
    from django.conf import settings
    
    try:
        conn = psycopg2.connect(
            dbname=settings.DATABASES['default']['NAME'],
            user=settings.DATABASES['default']['USER'],
            password=settings.DATABASES['default']['PASSWORD'],
            host=settings.DATABASES['default']['HOST'],
            port=settings.DATABASES['default']['PORT']
        )
        cursor = conn.cursor()
        
        # Obtener determinaciones
        cursor.execute("SELECT codigo, nombre FROM determinaciones ORDER BY nombre")
        dets = cursor.fetchall()
        
        # Obtener perfiles
        cursor.execute("SELECT codigo, nombre FROM perfiles ORDER BY nombre")
        perfs = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        items = []
        # Agregar determinaciones
        for row in dets:
            items.append({'codigo': str(row[0]), 'nombre': row[1], 'tipo': 'determinacion'})
        # Agregar perfiles
        for row in perfs:
            items.append({'codigo': row[0], 'nombre': row[1], 'tipo': 'perfil'})
        
        return JsonResponse(items, safe=False)
            
    except Exception as e:
        return JsonResponse([], safe=False)


@login_required
def listar_medicos_api(request):
    """API para listar todos los médicos"""
    import psycopg2
    from django.conf import settings
    
    try:
        conn = psycopg2.connect(
            dbname=settings.DATABASES['default']['NAME'],
            user=settings.DATABASES['default']['USER'],
            password=settings.DATABASES['default']['PASSWORD'],
            host=settings.DATABASES['default']['HOST'],
            port=settings.DATABASES['default']['PORT']
        )
        cursor = conn.cursor()
        
        # Obtener médicos ordenados por nombre
        cursor.execute("SELECT matricula_provincial, nombre_apellido FROM medicos ORDER BY nombre_apellido")
        medicos = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        items = []
        for row in medicos:
            items.append({'matricula_provincial': row[0], 'nombre_apellido': row[1]})
        
        return JsonResponse(items, safe=False)
            
    except Exception as e:
        return JsonResponse([], safe=False)


@login_required
def buscar_codigo_api(request):
    """API para buscar por código (determinación o perfil)"""
    import psycopg2
    from django.conf import settings
    
    codigo = request.GET.get('codigo', '').strip()
    if not codigo:
        return JsonResponse({'found': False})
    
    try:
        conn = psycopg2.connect(
            dbname=settings.DATABASES['default']['NAME'],
            user=settings.DATABASES['default']['USER'],
            password=settings.DATABASES['default']['PASSWORD'],
            host=settings.DATABASES['default']['HOST'],
            port=settings.DATABASES['default']['PORT']
        )
        cursor = conn.cursor()
        
        # Primero buscar en perfiles (empiezan con /)
        if codigo.startswith('/'):
            cursor.execute("SELECT codigo, nombre, determinaciones FROM perfiles WHERE codigo = %s", (codigo,))
            result = cursor.fetchone()
            if result:
                cursor.close()
                conn.close()
                return JsonResponse({
                    'found': True,
                    'tipo': 'perfil',
                    'codigo': result[0],
                    'nombre': result[1],
                    'determinaciones': result[2]
                })
        
        # Buscar en determinaciones
        try:
            codigo_int = int(codigo)
            cursor.execute("SELECT codigo, nombre FROM determinaciones WHERE codigo = %s", (codigo_int,))
            result = cursor.fetchone()
            if result:
                cursor.close()
                conn.close()
                return JsonResponse({
                    'found': True,
                    'tipo': 'determinacion',
                    'codigo': result[0],
                    'nombre': result[1]
                })
        except ValueError:
            pass
        
        cursor.close()
        conn.close()
        return JsonResponse({'found': False})
            
    except Exception as e:
        return JsonResponse({'found': False, 'error': str(e)})


@login_required
def buscar_perfil_api(request):
    """API para obtener detalles de un perfil"""
    import psycopg2
    from django.conf import settings
    
    codigo = request.GET.get('codigo', '').strip()
    if not codigo:
        return JsonResponse({'found': False})
    
    try:
        conn = psycopg2.connect(
            dbname=settings.DATABASES['default']['NAME'],
            user=settings.DATABASES['default']['USER'],
            password=settings.DATABASES['default']['PASSWORD'],
            host=settings.DATABASES['default']['HOST'],
            port=settings.DATABASES['default']['PORT']
        )
        cursor = conn.cursor()
        
        cursor.execute("SELECT codigo, nombre, determinaciones FROM perfiles WHERE codigo = %s", (codigo,))
        result = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if result:
            return JsonResponse({
                'found': True,
                'codigo': result[0],
                'nombre': result[1],
                'determinaciones': result[2]
            })
        else:
            return JsonResponse({'found': False})
            
    except Exception as e:
        return JsonResponse({'found': False, 'error': str(e)})


@login_required
def coordinar_turno(request, turno_id):
    """Genera archivo ASTM para coordinar turno y registra en Coordinados"""
    import psycopg2
    from datetime import datetime
    import os
    from .models import Coordinados
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'})
    
    try:
        # Verificar si el turno ya fue coordinado
        if Coordinados.objects.filter(id_turno=turno_id).exists():
            return JsonResponse({'success': False, 'error': 'Este turno ya fue coordinado anteriormente'})
        
        # Obtener el turno
        turno = get_object_or_404(Turno, id=turno_id)
        
        # Conectar a PostgreSQL para obtener datos del paciente
        conn = psycopg2.connect(
            dbname=settings.DATABASES['default']['NAME'],
            user=settings.DATABASES['default']['USER'],
            password=settings.DATABASES['default']['PASSWORD'],
            host=settings.DATABASES['default']['HOST'],
            port=settings.DATABASES['default']['PORT']
        )
        cursor = conn.cursor()
        
        # Buscar paciente por DNI
        cursor.execute(
            "SELECT nombre, apellido, dni, fecha_nacimiento, sexo, telefono, email FROM pacientes WHERE dni = %s",
            (turno.dni,)
        )
        paciente = cursor.fetchone()
        
        if not paciente:
            cursor.close()
            conn.close()
            return JsonResponse({'success': False, 'error': 'Paciente no encontrado'})
        
        nombre, apellido, dni, fecha_nacimiento, sexo, telefono, email = paciente
        
        # Convertir sexo al formato ASTM (M/F/U)
        sexo_astm = 'M' if sexo == 'Hombre' else ('F' if sexo == 'Mujer' else 'U')
        
        # Preparar telefono y email (sin comillas)
        telefono_astm = telefono if telefono else ''
        email_astm = email if email else ''
        
        # Formatear fechas
        ahora = datetime.now()
        timestamp = ahora.strftime('%Y%m%d%H%M%S')  # AAAAMMDDHHMMSS
        fecha_nac = fecha_nacimiento.strftime('%Y%m%d')  # AAAAMMDD
        
        # Procesar determinaciones/perfiles
        determinaciones_str = turno.determinaciones if turno.determinaciones else ''
        codigos = [c.strip() for c in determinaciones_str.split(',') if c.strip()]
        
        # Construir línea O con determinaciones/perfiles
        determinaciones_astm = []
        for codigo in codigos:
            if codigo.startswith('/'):
                # Es un perfil - expandir sus determinaciones individuales
                cursor.execute("SELECT determinaciones FROM perfiles WHERE codigo = %s", (codigo,))
                perfil_result = cursor.fetchone()
                if perfil_result and perfil_result[0]:
                    # Obtener determinaciones del perfil y agregarlas individualmente
                    dets_perfil = [d.strip() for d in perfil_result[0].split(',') if d.strip()]
                    for det in dets_perfil:
                        determinaciones_astm.append(f'^^^{det}\\')
            else:
                # Es una determinación individual
                determinaciones_astm.append(f'^^^{codigo}\\')
        
        # Preparar nota_interna (sin comillas)
        nota_interna_astm = turno.nota_interna if turno.nota_interna else ''
        
        # Obtener matrícula del médico si existe
        matricula_medico = ''
        if turno.medico:
            cursor_temp = conn.cursor()
            cursor_temp.execute("SELECT matricula_provincial FROM medicos WHERE nombre_apellido = %s", (turno.medico,))
            medico_result = cursor_temp.fetchone()
            if medico_result:
                matricula_medico = str(medico_result[0])
            cursor_temp.close()
        
        cursor.close()
        conn.close()
        
        # Construir el contenido del archivo ASTM
        lineas = []
        lineas.append(f'H|\\^&|||Balestrini|||||||P||{timestamp}')
        lineas.append(f'P|1||{dni}||{apellido}^{nombre}^||{fecha_nac}|{sexo_astm}|{email_astm}|{telefono_astm}|{nota_interna_astm}||||||| |||||{timestamp}||||||||||')
        
        # Construir línea O con todas las determinaciones/perfiles
        determinaciones_concatenadas = ''.join(determinaciones_astm)
        lineas.append(f'O|1|{turno_id}||{determinaciones_concatenadas}||||{matricula_medico}||A||||||||||||||O')
        lineas.append('L|1|F')
        
        # Crear nombre de archivo único
        nombre_archivo = f"mensaje_{turno_id}_{ahora.strftime('%Y%m%d_%H%M%S')}.pet"
        ruta_mensajes = os.path.join(settings.BASE_DIR, 'mensajes')
        
        # Asegurar que existe el directorio
        os.makedirs(ruta_mensajes, exist_ok=True)
        
        # Escribir archivo
        ruta_completa = os.path.join(ruta_mensajes, nombre_archivo)
        with open(ruta_completa, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lineas))
        
        # Crear registro en Coordinados
        Coordinados.objects.create(
            id_turno=turno_id,
            nombre=nombre,
            apellido=apellido,
            dni=dni,
            determinaciones=turno.determinaciones,
            usuario=request.user.username
        )
        
        return JsonResponse({
            'success': True,
            'mensaje': f'Turno coordinado exitosamente. Archivo generado: {nombre_archivo}'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def generar_ticket_turno(request, turno_id):
    """Genera un ticket PDF para impresora térmica de 8cm de ancho"""
    import psycopg2
    from datetime import date
    
    conn = psycopg2.connect(
        dbname='Laboratorio',
        user='postgres',
        password='estufa10',
        host='localhost',
        port='5432'
    )
    cursor = conn.cursor()
    
    # Obtener datos del turno
    cursor.execute("""
        SELECT 
            t.id,
            t.fecha,
            t.medico,
            t.nota_interna,
            t.nombre,
            t.apellido,
            t.dni,
            t.usuario,
            a.name as agenda_nombre,
            t.determinaciones
        FROM turnos_turno t
        JOIN turnos_agenda a ON t.agenda_id = a.id
        WHERE t.id = %s
    """, (turno_id,))
    
    row = cursor.fetchone()
    
    # Obtener datos adicionales del paciente de la tabla pacientes
    paciente_data = None
    if row:
        cursor.execute("""
            SELECT fecha_nacimiento, sexo, telefono, email
            FROM pacientes
            WHERE dni = %s
            ORDER BY id DESC
            LIMIT 1
        """, (row[6],))
        paciente_data = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    if not row:
        return HttpResponse("Turno no encontrado", status=404)
    
    # Calcular edad del paciente
    edad = None
    if paciente_data and paciente_data[0]:
        fecha_nacimiento = paciente_data[0]
        fecha_turno = row[1]
        edad = fecha_turno.year - fecha_nacimiento.year
        if (fecha_turno.month, fecha_turno.day) < (fecha_nacimiento.month, fecha_nacimiento.day):
            edad -= 1
    
    # Obtener determinaciones del campo de texto (son códigos separados por comas)
    determinaciones_texto = row[9] if row[9] else ""
    determinaciones_list = []
    perfiles_list = []
    
    if determinaciones_texto:
        # Dividir por comas y limpiar
        codigos = [d.strip() for d in determinaciones_texto.split(',') if d.strip()]
        
        # Separar códigos de perfiles (empiezan con /) y determinaciones (números)
        codigos_perfiles = []
        codigos_determinaciones = []
        
        for codigo in codigos:
            if codigo.startswith('/'):
                # Es un perfil, mantener el /
                codigos_perfiles.append(codigo)
            else:
                # Es una determinación
                try:
                    codigos_determinaciones.append(int(codigo))
                except:
                    pass
        
        # Buscar nombres de perfiles
        if codigos_perfiles:
            conn2 = psycopg2.connect(
                dbname='Laboratorio',
                user='postgres',
                password='estufa10',
                host='localhost',
                port='5432'
            )
            cursor2 = conn2.cursor()
            placeholders = ','.join(['%s'] * len(codigos_perfiles))
            cursor2.execute(f"""
                SELECT codigo, nombre 
                FROM perfiles 
                WHERE codigo IN ({placeholders})
                ORDER BY nombre
            """, codigos_perfiles)
            perfiles_list = cursor2.fetchall()
            cursor2.close()
            conn2.close()
        
        # Buscar nombres de determinaciones
        if codigos_determinaciones:
            conn3 = psycopg2.connect(
                dbname='Laboratorio',
                user='postgres',
                password='estufa10',
                host='localhost',
                port='5432'
            )
            cursor3 = conn3.cursor()
            placeholders = ','.join(['%s'] * len(codigos_determinaciones))
            cursor3.execute(f"""
                SELECT codigo, nombre 
                FROM determinaciones 
                WHERE codigo IN ({placeholders})
                ORDER BY nombre
            """, codigos_determinaciones)
            determinaciones_list = cursor3.fetchall()
            cursor3.close()
            conn3.close()
    
    # Crear PDF para impresora térmica (8cm = 226.77 puntos)
    buffer = BytesIO()
    ancho_papel = 8 * cm  # 8 cm
    alto_papel = 29 * cm  # Altura más larga para todo el contenido
    
    p = canvas.Canvas(buffer, pagesize=(ancho_papel, alto_papel))
    
    # Configuración
    margen = 0.3 * cm
    ancho_util = ancho_papel - (2 * margen)
    y = alto_papel - margen
    
    # ====== ENCABEZADO ======
    p.setFont("Helvetica-Bold", 11)
    p.drawCentredString(ancho_papel / 2, y, "Hospital Balestrini")
    y -= 0.5 * cm
    
    p.setFont("Helvetica", 9)
    p.drawCentredString(ancho_papel / 2, y, row[8] or "")  # Nombre de la agenda
    y -= 0.6 * cm
    
    # Línea separadora
    p.line(margen, y, ancho_papel - margen, y)
    y -= 0.5 * cm
    
    # ====== DATOS DEL PACIENTE ======
    p.setFont("Helvetica-Bold", 9)
    p.drawString(margen, y, "Paciente:")
    p.setFont("Helvetica", 9)
    nombre_completo = f"{row[4]} {row[5]}"
    p.drawString(margen + 2*cm, y, nombre_completo)
    y -= 0.45 * cm
    
    if edad is not None:
        p.setFont("Helvetica-Bold", 9)
        p.drawString(margen, y, "Edad:")
        p.setFont("Helvetica", 9)
        p.drawString(margen + 2*cm, y, f"{edad} años")
        y -= 0.45 * cm
    
    # ====== FECHA DEL TURNO (EN NEGRITA) ======
    p.setFont("Helvetica-Bold", 10)
    fecha_str = row[1].strftime('%d/%m/%Y')
    p.drawString(margen, y, f"Fecha de turno: {fecha_str}")
    y -= 0.6 * cm
    
    # Línea separadora
    p.line(margen, y, ancho_papel - margen, y)
    y -= 0.5 * cm
    
    # ====== DETERMINACIONES Y PERFILES ======
    p.setFont("Helvetica-Bold", 9)
    p.drawString(margen, y, "Estudios solicitados:")
    y -= 0.45 * cm
    
    # Mostrar perfiles primero
    if perfiles_list:
        p.setFont("Helvetica", 8)
        for perfil in perfiles_list:
            texto_perfil = f"• {perfil[1].upper()}"
            # Dividir si es muy largo
            if len(texto_perfil) > 40:
                p.drawString(margen + 0.2*cm, y, texto_perfil[:40])
                y -= 0.35 * cm
                p.drawString(margen + 0.4*cm, y, texto_perfil[40:])
                y -= 0.4 * cm
            else:
                p.drawString(margen + 0.2*cm, y, texto_perfil)
                y -= 0.4 * cm
    
    # Mostrar determinaciones individuales
    if determinaciones_list:
        p.setFont("Helvetica", 8)
        for det in determinaciones_list:
            texto_det = f"• {det[1].upper()}"
            # Dividir si es muy largo
            if len(texto_det) > 40:
                p.drawString(margen + 0.2*cm, y, texto_det[:40])
                y -= 0.35 * cm
                p.drawString(margen + 0.4*cm, y, texto_det[40:])
                y -= 0.4 * cm
            else:
                p.drawString(margen + 0.2*cm, y, texto_det)
                y -= 0.4 * cm
    
    # Si no hay ni perfiles ni determinaciones
    if not perfiles_list and not determinaciones_list:
        p.setFont("Helvetica", 8)
        p.drawString(margen + 0.2*cm, y, "(Sin estudios especificados)")
        y -= 0.4 * cm
    
    y -= 0.3 * cm
    
    # Línea separadora
    p.line(margen, y, ancho_papel - margen, y)
    y -= 0.5 * cm
    
    # ====== INDICACIONES FIJAS ======
    p.setFont("Helvetica-Bold", 8)
    p.drawCentredString(ancho_papel / 2, y, "INDICACIONES")
    y -= 0.45 * cm
    
    p.setFont("Helvetica", 7)
    indicaciones = [
        "Concurrir al laboratorio de 7:00 a 9:00 hs",
        "con su DNI, receta médica (autorizada por",
        "SAMO) y este ticket de turno con 8 o 12 hs",
        "de ayuno según corresponda.",
        "",
        "No tomar medicación antes de la extracción.",
        "",
        "Traer la primera orina de la mañana si",
        "corresponde."
    ]
    
    for linea in indicaciones:
        p.drawCentredString(ancho_papel / 2, y, linea)
        y -= 0.35 * cm
    
    y -= 0.3 * cm
    
    # Línea separadora
    p.line(margen, y, ancho_papel - margen, y)
    y -= 0.4 * cm
    
    # ====== PIE DE PÁGINA ======
    p.setFont("Helvetica", 7)
    p.drawCentredString(ancho_papel / 2, y, f"Ticket asignado por: {row[7]}")
    y -= 0.3 * cm
    p.drawCentredString(ancho_papel / 2, y, f"Ticket N° {turno_id}")
    y -= 0.3 * cm
    p.setFont("Helvetica", 6)
    p.drawCentredString(ancho_papel / 2, y, datetime.now().strftime('%d/%m/%Y %H:%M'))
    
    p.showPage()
    p.save()
    
    # Preparar respuesta HTTP
    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="ticket_turno_{turno_id}.pdf"'
    
    return response


@user_passes_test(lambda u: u.is_superuser)
def administrar_tablas(request):
    """Vista para administrar las tablas principales del sistema"""
    import psycopg2
    
    conn = psycopg2.connect(
        dbname='Laboratorio',
        user='postgres',
        password='estufa10',
        host='localhost',
        port='5432'
    )
    cursor = conn.cursor()
    
    # Obtener todas las tablas con sus conteos
    tablas_info = []
    
    # Determinaciones
    cursor.execute("SELECT COUNT(*) FROM determinaciones")
    count_det = cursor.fetchone()[0]
    tablas_info.append({
        'nombre': 'Determinaciones',
        'tabla': 'determinaciones',
        'cantidad': count_det,
        'descripcion': 'Estudios de laboratorio individuales'
    })
    
    # Perfiles
    cursor.execute("SELECT COUNT(*) FROM perfiles")
    count_perf = cursor.fetchone()[0]
    tablas_info.append({
        'nombre': 'Perfiles',
        'tabla': 'perfiles',
        'cantidad': count_perf,
        'descripcion': 'Grupos de determinaciones'
    })
    
    # Pacientes
    cursor.execute("SELECT COUNT(*) FROM pacientes")
    count_pac = cursor.fetchone()[0]
    tablas_info.append({
        'nombre': 'Pacientes',
        'tabla': 'pacientes',
        'cantidad': count_pac,
        'descripcion': 'Información de pacientes'
    })
    
    # Médicos
    cursor.execute("SELECT COUNT(*) FROM medicos")
    count_med = cursor.fetchone()[0]
    tablas_info.append({
        'nombre': 'Médicos',
        'tabla': 'medicos',
        'cantidad': count_med,
        'descripcion': 'Médicos registrados en el sistema'
    })
    
    # Usuarios
    cursor.execute("SELECT COUNT(*) FROM auth_user")
    count_user = cursor.fetchone()[0]
    tablas_info.append({
        'nombre': 'Usuarios',
        'tabla': 'usuarios',
        'cantidad': count_user,
        'descripcion': 'Usuarios del sistema'
    })
    
    # Cupos
    cursor.execute("SELECT COUNT(*) FROM turnos_cupo")
    count_cupo = cursor.fetchone()[0]
    tablas_info.append({
        'nombre': 'Cupos',
        'tabla': 'cupos',
        'cantidad': count_cupo,
        'descripcion': 'Cupos configurados por fecha'
    })
    
    # Turnos
    cursor.execute("SELECT COUNT(*) FROM turnos_turno")
    count_turno = cursor.fetchone()[0]
    tablas_info.append({
        'nombre': 'Turnos',
        'tabla': 'turnos',
        'cantidad': count_turno,
        'descripcion': 'Turnos registrados en el sistema'
    })
    
    # Feriados
    cursor.execute("SELECT COUNT(*) FROM feriados")
    count_feriados = cursor.fetchone()[0]
    tablas_info.append({
        'nombre': 'Feriados',
        'tabla': 'feriados',
        'cantidad': count_feriados,
        'descripcion': 'Días feriados y no laborables'
    })
    
    cursor.close()
    conn.close()
    
    return render(request, 'turnos/administrar_tablas.html', {
        'tablas': tablas_info
    })


@user_passes_test(lambda u: u.is_superuser)
def administrar_tabla_detalle(request, tabla):
    """Vista detallada para administrar una tabla específica"""
    import psycopg2
    
    conn = psycopg2.connect(
        dbname='Laboratorio',
        user='postgres',
        password='estufa10',
        host='localhost',
        port='5432'
    )
    cursor = conn.cursor()
    
    # Configuración según la tabla
    config = {
        'determinaciones': {
            'nombre': 'Determinaciones',
            'columnas': ['id', 'codigo', 'nombre', 'descripcion'],
            'columnas_display': ['ID', 'Código', 'Nombre', 'Descripción'],
            'query': 'SELECT id, codigo, nombre, descripcion FROM determinaciones ORDER BY codigo'
        },
        'perfiles': {
            'nombre': 'Perfiles',
            'columnas': ['id', 'codigo', 'nombre', 'descripcion'],
            'columnas_display': ['ID', 'Código', 'Nombre', 'Descripción'],
            'query': 'SELECT id, codigo, nombre, descripcion FROM perfiles ORDER BY codigo'
        },
        'pacientes': {
            'nombre': 'Pacientes',
            'columnas': ['id', 'dni', 'apellido', 'nombre', 'fecha_nacimiento', 'sexo', 'telefono', 'email'],
            'columnas_display': ['ID', 'DNI', 'Apellido', 'Nombre', 'Fecha Nac.', 'Sexo', 'Teléfono', 'Email'],
            'query': 'SELECT id, dni, apellido, nombre, fecha_nacimiento, sexo, telefono, email FROM pacientes ORDER BY apellido, nombre'
        },
        'medicos': {
            'nombre': 'Médicos',
            'columnas': ['id', 'matricula_provincial', 'nombre_apellido'],
            'columnas_display': ['ID', 'Matrícula Provincial', 'Nombre y Apellido'],
            'query': 'SELECT id, matricula_provincial, nombre_apellido FROM medicos ORDER BY nombre_apellido'
        },
        'usuarios': {
            'nombre': 'Usuarios',
            'columnas': ['id', 'username', 'first_name', 'last_name', 'email', 'is_staff', 'is_superuser', 'is_active'],
            'columnas_display': ['ID', 'Usuario', 'Nombre', 'Apellido', 'Email', 'Staff', 'Superuser', 'Activo'],
            'query': 'SELECT id, username, first_name, last_name, email, is_staff, is_superuser, is_active FROM auth_user ORDER BY username',
            'readonly': True
        },
        'cupos': {
            'nombre': 'Cupos',
            'columnas': ['id', 'fecha', 'cantidad_total', 'agenda_id', 'usuario'],
            'columnas_display': ['ID', 'Fecha', 'Cantidad Total', 'Agenda ID', 'Usuario'],
            'query': 'SELECT id, fecha, cantidad_total, agenda_id, usuario FROM turnos_cupo ORDER BY fecha DESC',
            'readonly': True
        },
        'turnos': {
            'nombre': 'Turnos',
            'columnas': ['id', 'fecha', 'dni', 'apellido', 'nombre', 'medico', 'agenda_id'],
            'columnas_display': ['ID', 'Fecha', 'DNI', 'Apellido', 'Nombre', 'Médico', 'Agenda'],
            'query': 'SELECT id, fecha, dni, apellido, nombre, medico, agenda_id FROM turnos_turno ORDER BY fecha DESC, id DESC',
            'readonly': True
        },
        'feriados': {
            'nombre': 'Feriados',
            'columnas': ['id', 'fecha', 'descripcion'],
            'columnas_display': ['ID', 'Fecha', 'Descripción'],
            'query': 'SELECT id, fecha, descripcion FROM feriados ORDER BY fecha DESC'
        }
    }
    
    if tabla not in config:
        messages.error(request, 'Tabla no válida')
        return redirect('turnos:administrar_tablas')
    
    tabla_config = config[tabla]
    
    # Obtener datos
    cursor.execute(tabla_config['query'])
    registros = cursor.fetchall()
    
    # Convertir a lista de diccionarios
    datos = []
    for reg in registros:
        dato = {}
        for i, col in enumerate(tabla_config['columnas']):
            dato[col] = reg[i]
        datos.append(dato)
    
    cursor.close()
    conn.close()
    
    return render(request, 'turnos/administrar_tabla_detalle.html', {
        'tabla': tabla,
        'tabla_nombre': tabla_config['nombre'],
        'columnas': tabla_config['columnas'],
        'columnas_display': tabla_config['columnas_display'],
        'datos': datos,
        'readonly': tabla_config.get('readonly', False)
    })


@user_passes_test(lambda u: u.is_superuser)
def crear_registro(request, tabla):
    """Crear un nuevo registro en la tabla"""
    import psycopg2
    
    if request.method == 'POST':
        conn = psycopg2.connect(
            dbname='Laboratorio',
            user='postgres',
            password='estufa10',
            host='localhost',
            port='5432'
        )
        cursor = conn.cursor()
        
        try:
            if tabla == 'determinaciones':
                cursor.execute("""
                    INSERT INTO determinaciones (codigo, nombre, descripcion, usuario)
                    VALUES (%s, %s, %s, %s)
                """, (
                    request.POST.get('codigo'),
                    request.POST.get('nombre'),
                    request.POST.get('descripcion'),
                    request.user.username
                ))
            elif tabla == 'perfiles':
                cursor.execute("""
                    INSERT INTO perfiles (codigo, nombre, descripcion, usuario)
                    VALUES (%s, %s, %s, %s)
                """, (
                    request.POST.get('codigo'),
                    request.POST.get('nombre'),
                    request.POST.get('descripcion'),
                    request.user.username
                ))
            elif tabla == 'pacientes':
                cursor.execute("""
                    INSERT INTO pacientes (dni, apellido, nombre, fecha_nacimiento, sexo, telefono, email)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    request.POST.get('dni'),
                    request.POST.get('apellido'),
                    request.POST.get('nombre'),
                    request.POST.get('fecha_nacimiento') or None,
                    request.POST.get('sexo') or None,
                    request.POST.get('telefono') or None,
                    request.POST.get('email') or None
                ))
            elif tabla == 'medicos':
                cursor.execute("""
                    INSERT INTO medicos (matricula_provincial, nombre_apellido, usuario)
                    VALUES (%s, %s, %s)
                """, (
                    request.POST.get('matricula_provincial'),
                    request.POST.get('nombre_apellido'),
                    request.user.username
                ))
            elif tabla == 'feriados':
                cursor.execute("""
                    INSERT INTO feriados (fecha, descripcion, usuario)
                    VALUES (%s, %s, %s)
                """, (
                    request.POST.get('fecha'),
                    request.POST.get('descripcion'),
                    request.user.username
                ))
            
            conn.commit()
            messages.success(request, 'Registro creado exitosamente')
        except Exception as e:
            conn.rollback()
            messages.error(request, f'Error al crear registro: {str(e)}')
        finally:
            cursor.close()
            conn.close()
        
        return redirect('turnos:administrar_tabla_detalle', tabla=tabla)
    
    return render(request, 'turnos/crear_registro.html', {'tabla': tabla})


@user_passes_test(lambda u: u.is_superuser)
def editar_registro(request, tabla, id):
    """Editar un registro existente"""
    import psycopg2
    
    conn = psycopg2.connect(
        dbname='Laboratorio',
        user='postgres',
        password='estufa10',
        host='localhost',
        port='5432'
    )
    cursor = conn.cursor()
    
    if request.method == 'POST':
        try:
            if tabla == 'determinaciones':
                cursor.execute("""
                    UPDATE determinaciones 
                    SET codigo = %s, nombre = %s, descripcion = %s
                    WHERE id = %s
                """, (
                    request.POST.get('codigo'),
                    request.POST.get('nombre'),
                    request.POST.get('descripcion'),
                    id
                ))
            elif tabla == 'perfiles':
                cursor.execute("""
                    UPDATE perfiles 
                    SET codigo = %s, nombre = %s, descripcion = %s
                    WHERE id = %s
                """, (
                    request.POST.get('codigo'),
                    request.POST.get('nombre'),
                    request.POST.get('descripcion'),
                    id
                ))
            elif tabla == 'pacientes':
                cursor.execute("""
                    UPDATE pacientes 
                    SET dni = %s, apellido = %s, nombre = %s, fecha_nacimiento = %s, 
                        sexo = %s, telefono = %s, email = %s
                    WHERE id = %s
                """, (
                    request.POST.get('dni'),
                    request.POST.get('apellido'),
                    request.POST.get('nombre'),
                    request.POST.get('fecha_nacimiento') or None,
                    request.POST.get('sexo') or None,
                    request.POST.get('telefono') or None,
                    request.POST.get('email') or None,
                    id
                ))
            elif tabla == 'medicos':
                cursor.execute("""
                    UPDATE medicos 
                    SET matricula_provincial = %s, nombre_apellido = %s
                    WHERE id = %s
                """, (
                    request.POST.get('matricula_provincial'),
                    request.POST.get('nombre_apellido'),
                    id
                ))
            elif tabla == 'feriados':
                cursor.execute("""
                    UPDATE feriados 
                    SET fecha = %s, descripcion = %s
                    WHERE id = %s
                """, (
                    request.POST.get('fecha'),
                    request.POST.get('descripcion'),
                    id
                ))
            
            conn.commit()
            messages.success(request, 'Registro actualizado exitosamente')
        except Exception as e:
            conn.rollback()
            messages.error(request, f'Error al actualizar registro: {str(e)}')
        finally:
            cursor.close()
            conn.close()
        
        return redirect('turnos:administrar_tabla_detalle', tabla=tabla)
    
    # Obtener datos actuales
    if tabla == 'determinaciones':
        cursor.execute("SELECT id, codigo, nombre, descripcion FROM determinaciones WHERE id = %s", (id,))
    elif tabla == 'perfiles':
        cursor.execute("SELECT id, codigo, nombre, descripcion FROM perfiles WHERE id = %s", (id,))
    elif tabla == 'pacientes':
        cursor.execute("SELECT id, dni, apellido, nombre, fecha_nacimiento, sexo, telefono, email FROM pacientes WHERE id = %s", (id,))
    elif tabla == 'medicos':
        cursor.execute("SELECT id, matricula_provincial, nombre_apellido FROM medicos WHERE id = %s", (id,))
    elif tabla == 'feriados':
        cursor.execute("SELECT id, fecha, descripcion FROM feriados WHERE id = %s", (id,))
    
    registro = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if not registro:
        messages.error(request, 'Registro no encontrado')
        return redirect('turnos:administrar_tabla_detalle', tabla=tabla)
    
    return render(request, 'turnos/editar_registro.html', {
        'tabla': tabla,
        'registro': registro,
        'id': id
    })


@user_passes_test(lambda u: u.is_superuser)
def eliminar_registro(request, tabla, id):
    """Eliminar un registro"""
    import psycopg2
    
    if request.method == 'POST':
        conn = psycopg2.connect(
            dbname='Laboratorio',
            user='postgres',
            password='estufa10',
            host='localhost',
            port='5432'
        )
        cursor = conn.cursor()
        
        try:
            if tabla == 'determinaciones':
                cursor.execute("DELETE FROM determinaciones WHERE id = %s", (id,))
            elif tabla == 'perfiles':
                cursor.execute("DELETE FROM perfiles WHERE id = %s", (id,))
            elif tabla == 'pacientes':
                cursor.execute("DELETE FROM pacientes WHERE id = %s", (id,))
            
            conn.commit()
            messages.success(request, 'Registro eliminado exitosamente')
        except Exception as e:
            conn.rollback()
            messages.error(request, f'Error al eliminar registro: {str(e)}')
        finally:
            cursor.close()
            conn.close()
    
    return redirect('turnos:administrar_tabla_detalle', tabla=tabla)


@user_passes_test(lambda u: u.is_superuser)
def aplicar_feriados(request):
    """Anular cupos en fechas feriadas"""
    import psycopg2
    
    conn = psycopg2.connect(
        dbname='Laboratorio',
        user='postgres',
        password='estufa10',
        host='localhost',
        port='5432'
    )
    cursor = conn.cursor()
    
    try:
        # Obtener todas las fechas de feriados
        cursor.execute("SELECT fecha, descripcion FROM feriados ORDER BY fecha")
        feriados = cursor.fetchall()
        
        if not feriados:
            messages.warning(request, 'No hay feriados registrados')
            return redirect('turnos:administrar_tabla_detalle', tabla='feriados')
        
        cupos_anulados = 0
        fechas_procesadas = []
        
        # Anular cupos para cada fecha feriada
        for fecha, descripcion in feriados:
            cursor.execute("""
                UPDATE turnos_cupo 
                SET cantidad_total = 0 
                WHERE fecha = %s AND cantidad_total > 0
            """, (fecha,))
            
            if cursor.rowcount > 0:
                cupos_anulados += cursor.rowcount
                fechas_procesadas.append(f"{fecha.strftime('%d/%m/%Y')} ({descripcion})")
        
        conn.commit()
        
        if cupos_anulados > 0:
            fechas_str = ', '.join(fechas_procesadas)
            messages.success(request, f'Se anularon {cupos_anulados} cupos en {len(fechas_procesadas)} fechas: {fechas_str}')
        else:
            messages.info(request, 'No había cupos activos en las fechas feriadas')
            
    except Exception as e:
        conn.rollback()
        messages.error(request, f'Error al aplicar feriados: {str(e)}')
    finally:
        cursor.close()
        conn.close()
    
    return redirect('turnos:administrar_tabla_detalle', tabla='feriados')
