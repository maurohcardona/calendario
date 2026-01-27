import psycopg2
from django.conf import settings
from django.contrib.auth.decorators import login_required
from determinaciones.models import Determinacion, PerfilDeterminacion, DeterminacionCompleja
from medicos.models import Medico
from datetime import timedelta


def get_db_conn():
    return psycopg2.connect(
        dbname=settings.DATABASES['default']['NAME'],
        user=settings.DATABASES['default']['USER'],
        password=settings.DATABASES['default']['PASSWORD'],
        host=settings.DATABASES['default']['HOST'],
        port=settings.DATABASES['default']['PORT'],
    )


def calcular_max_tiempo(determinaciones_texto):
    """Devuelve el máximo tiempo (en días) entre todas las determinaciones, perfiles y determinaciones complejas."""
    if not determinaciones_texto:
        return 0

    codigos = [c.strip() for c in determinaciones_texto.split(',') if c.strip()]
    det_codes = [c for c in codigos if not c.startswith('/')]
    complejas_codes = [c for c in codigos if c.startswith('/')]

    tiempos = []
    if det_codes:
        tiempos.extend([d.tiempo for d in Determinacion.objects.filter(codigo__in=det_codes)])

    if complejas_codes:
        # Procesar determinaciones complejas (código incluye /)
        complejas = DeterminacionCompleja.objects.filter(codigo__in=complejas_codes)
        dets_complejas = []
        for compleja in complejas:
            dets_complejas.extend(compleja.determinaciones)
        if dets_complejas:
            tiempos.extend([d.tiempo for d in Determinacion.objects.filter(codigo__in=dets_complejas)])
        
        # Procesar perfiles (buscar sin /)
        perfil_codes = [c.lstrip('/') for c in complejas_codes]
        perfiles = PerfilDeterminacion.objects.filter(codigo__in=perfil_codes)
        dets_perfiles = []
        for perfil in perfiles:
            for det_code in perfil.determinaciones:
                # Si el código dentro del perfil es una determinación compleja
                if det_code.startswith('/'):
                    compleja_en_perfil = DeterminacionCompleja.objects.filter(codigo=det_code).first()
                    if compleja_en_perfil:
                        # Expandir la determinación compleja
                        dets_perfiles.extend(compleja_en_perfil.determinaciones)
                else:
                    # Es una determinación simple
                    dets_perfiles.append(det_code)
        if dets_perfiles:
            tiempos.extend([d.tiempo for d in Determinacion.objects.filter(codigo__in=dets_perfiles)])

    return max(tiempos) if tiempos else 0

@login_required
def precoordinacion_turno(request, turno_id):
    """Vista de pre-coordinación: permite editar datos personales y coordinar el turno."""
    import psycopg2
    from django.conf import settings
    from django.shortcuts import get_object_or_404, redirect, render
    from django.urls import reverse
    from .models import Turno, Agenda
    turno = get_object_or_404(Turno.objects.select_related('medico', 'dni', 'agenda'), id=turno_id)

    paciente_obj = turno.dni  # Ya es una FK
    paciente_data = None
    if paciente_obj:
        paciente_data = {
            'nombre': paciente_obj.nombre,
            'apellido': paciente_obj.apellido,
            'dni': paciente_obj.iden,
            'fecha_nacimiento': paciente_obj.fecha_nacimiento,
            'sexo': paciente_obj.sexo,
            'telefono': paciente_obj.telefono,
            'email': paciente_obj.email,
            'observaciones': paciente_obj.observaciones or ''
        }

    if request.method == 'POST':
        accion = request.POST.get('accion')
        if accion == 'eliminar':
            turno.delete()
            return redirect('turnos:buscar')

        # Actualizar datos personales
        dni_nuevo = request.POST.get('dni', '').strip()
        apellido_nuevo = request.POST.get('apellido', '').strip()
        nombre_nuevo = request.POST.get('nombre', '').strip()
        fecha_nac_nueva = request.POST.get('fecha_nacimiento', '')
        sexo_nuevo = request.POST.get('sexo', '')
        telefono = request.POST.get('telefono', '')
        email = request.POST.get('email', '')
        observaciones_paciente = request.POST.get('observaciones_paciente', '')

        # Mapear sexo a opciones del modelo Paciente
        sexo_map = {
            'Hombre': 'Masculino',
            'Mujer': 'Femenino',
            'Generico': 'Sin asignar',
            '': 'Sin asignar',
            None: 'Sin asignar'
        }
        sexo_model = sexo_map.get(sexo_nuevo, sexo_nuevo or 'Sin asignar')

        # Parsear fecha de nacimiento
        from datetime import datetime
        fecha_nac_parsed = None
        if fecha_nac_nueva:
            try:
                fecha_nac_parsed = datetime.strptime(fecha_nac_nueva, '%Y-%m-%d').date()
            except Exception:
                fecha_nac_parsed = paciente_obj.fecha_nacimiento if paciente_obj else None

        # Crear o actualizar Paciente
        paciente_obj, _ = Paciente.objects.update_or_create(
            iden=dni_nuevo,
            defaults={
                'nombre': nombre_nuevo,
                'apellido': apellido_nuevo,
                'fecha_nacimiento': fecha_nac_parsed or date.today(),
                'sexo': sexo_model,
                'telefono': telefono or None,
                'email': email or None,
                'observaciones': observaciones_paciente or ''
            }
        )
        
        # Asignar paciente al turno
        turno.dni = paciente_obj

        # Actualizar datos del turno (agenda, fecha, determinaciones, medico y nota_interna)
        turno.agenda_id = request.POST.get('agenda')
        turno.fecha = request.POST.get('fecha')
        turno.determinaciones = request.POST.get('determinaciones', '')
        
        # Manejar el médico correctamente
        medico_nombre = request.POST.get('medico', '')
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
        
        turno.nota_interna = request.POST.get('nota_interna', '')
        turno.save()

        # Si se presionó coordinar, redirigir a la acción de coordinación
        if accion == 'coordinar':
            # Redirigir por GET, nunca hacer POST directo
            return redirect(reverse('turnos:coordinar_turno', args=[turno.id]))

        return redirect('turnos:buscar')

    agendas = Agenda.objects.all()
    context = {
        'turno': turno,
        'paciente': paciente_data,
        'agendas': agendas,
        'es_precoordinacion': True,
    }
    return render(request, 'turnos/precoordinacion_turno.html', context)
@login_required
def generar_ticket_retiro(request, turno_id):
    """Genera un ticket PDF de retiro para impresora térmica de 8cm de ancho"""
    from datetime import date, datetime
    from io import BytesIO
    from reportlab.lib.units import cm
    from reportlab.pdfgen import canvas
    from django.shortcuts import get_object_or_404
    from pacientes.models import Paciente

    turno = get_object_or_404(Turno.objects.select_related('agenda', 'dni'), id=turno_id)
    paciente_obj = turno.dni  # Ya es FK

    edad = None
    if paciente_obj and paciente_obj.fecha_nacimiento:
        fecha_nac = paciente_obj.fecha_nacimiento
        fecha_turno = turno.fecha
        edad = fecha_turno.year - fecha_nac.year
        if (fecha_turno.month, fecha_turno.day) < (fecha_nac.month, fecha_nac.day):
            edad -= 1

    max_tiempo = calcular_max_tiempo(turno.determinaciones or '')
    fecha_retiro = date.today() + timedelta(days=max_tiempo)

    agenda_nombre = turno.agenda.name if turno.agenda else ""
    apellido = turno.apellido or ""
    nombre = turno.nombre or ""
    dni = turno.paciente_dni or ""
    telefono = paciente_obj.telefono if paciente_obj else ""
    email = paciente_obj.email if paciente_obj else ""
    # Obtener apellido y nombre del usuario
    if turno.usuario:
        usuario_asignador = f"{turno.usuario.last_name}, {turno.usuario.first_name}" if turno.usuario.last_name and turno.usuario.first_name else turno.usuario.username
    else:
        usuario_asignador = f"{request.user.last_name}, {request.user.first_name}" if request.user.last_name and request.user.first_name else request.user.username
    medico_nombre = turno.medico.nombre if turno.medico else ""
    determinaciones_texto = turno.determinaciones or ""

    # Crear PDF para impresora térmica (8cm = 226.77 puntos)
    buffer = BytesIO()
    ancho_papel = 8 * cm  # 8 cm
    alto_papel = 18 * cm  # Altura suficiente para los datos
    p = canvas.Canvas(buffer, pagesize=(ancho_papel, alto_papel))

    margen = 0.3 * cm
    ancho_util = ancho_papel - (2 * margen)
    y = alto_papel - margen

    # ====== ENCABEZADO ======
    p.setFont("Helvetica-Bold", 11)
    p.drawCentredString(ancho_papel / 2, y, "Hospital Balestrini")
    y -= 0.5 * cm
    p.setFont("Helvetica", 9)
    p.drawCentredString(ancho_papel / 2, y, agenda_nombre)
    y -= 0.6 * cm
    p.line(margen, y, ancho_papel - margen, y)
    y -= 0.5 * cm

    # ====== DATOS DEL PACIENTE ======
    p.setFont("Helvetica-Bold", 9)
    p.drawString(margen, y, "Paciente:")
    p.setFont("Helvetica", 9)
    apellido_formateado = apellido.strip().capitalize() if apellido else ""
    nombre_formateado = nombre.strip().capitalize() if nombre else ""
    nombre_completo = f"{apellido_formateado}, {nombre_formateado}"
    p.drawString(margen + 2*cm, y, nombre_completo)
    y -= 0.45 * cm
    p.setFont("Helvetica-Bold", 9)
    p.drawString(margen, y, "DNI:")
    p.setFont("Helvetica", 9)
    p.drawString(margen + 2*cm, y, str(dni))
    y -= 0.45 * cm
    if telefono:
        p.setFont("Helvetica-Bold", 9)
        p.drawString(margen, y, "Teléfono:")
        p.setFont("Helvetica", 9)
        p.drawString(margen + 2*cm, y, str(telefono))
        y -= 0.45 * cm
    if email:
        p.setFont("Helvetica-Bold", 9)
        p.drawString(margen, y, "Email:")
        p.setFont("Helvetica", 7)
        email_str = str(email)
        if len(email_str) > 30:
            p.drawString(margen + 2*cm, y, email_str[:30])
            y -= 0.35 * cm
            p.drawString(margen + 2*cm, y, email_str[30:])
            y -= 0.45 * cm
        else:
            p.setFont("Helvetica", 9)
            p.drawString(margen + 2*cm, y, email_str)
            y -= 0.45 * cm
    if edad is not None:
        p.setFont("Helvetica-Bold", 9)
        p.drawString(margen, y, "Edad:")
        p.setFont("Helvetica", 9)
        p.drawString(margen + 2*cm, y, f"{edad} años")
        y -= 0.45 * cm
    if medico_nombre:
        p.setFont("Helvetica-Bold", 9)
        p.drawString(margen, y, "Médico:")
        p.setFont("Helvetica", 9)
        medico_str = str(medico_nombre).strip().capitalize()
        if len(medico_str) > 30:
            p.drawString(margen + 2*cm, y, medico_str[:30])
            y -= 0.35 * cm
            p.drawString(margen + 2*cm, y, medico_str[30:])
            y -= 0.45 * cm
        else:
            p.drawString(margen + 2*cm, y, medico_str)
            y -= 0.45 * cm

    # ====== FECHA DE RETIRO ======
    p.setFont("Helvetica-Bold", 10)
    fecha_retiro_str = fecha_retiro.strftime('%d/%m/%Y')
    p.drawString(margen, y, f"Fecha de retiro: a partir de {fecha_retiro_str}")
    y -= 0.45 * cm
    # Aumentar tamaño de las indicaciones
    p.setFont("Helvetica", 11)
    p.drawString(margen, y, "De lunes a viernes de 10 a 17 hs")
    y -= 0.5 * cm

    
    p.line(margen, y, ancho_papel - margen, y)
    y -= 0.5 * cm

    # ====== PIE DE PÁGINA ======
    p.setFont("Helvetica", 10)
    p.drawCentredString(ancho_papel / 2, y, f"Ticket asignado por: {usuario_asignador}")
    y -= 0.5 * cm
    p.drawCentredString(ancho_papel / 2, y, "admlabobalestrini@gmail.com")
    y -= 0.5 * cm
    p.setFont("Helvetica-Bold", 11)
    p.drawCentredString(ancho_papel / 2, y, f"Ticket N° {turno_id}")
    y -= 0.35 * cm
    p.setFont("Helvetica", 6)
    from datetime import datetime
    p.drawCentredString(ancho_papel / 2, y, datetime.now().strftime('%d/%m/%Y %H:%M'))
    p.showPage()
    p.save()

    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="ticket_retiro_{turno_id}.pdf"'
    return response
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.urls import reverse
from .models import Cupo, Turno, Agenda, Coordinados, Feriados
from pacientes.models import Paciente
from determinaciones.models import Determinacion, PerfilDeterminacion
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
from django.views.decorators.csrf import csrf_exempt


@login_required
def calendario(request):
    import psycopg2
    # Mostrar todos los Cupos de todas las agendas en el mismo calendario
    # Usar Cupo explícitos + disponibilidad semanal para construir eventos
    from datetime import date, timedelta
    eventos = []
    hoy = date.today()

    # 0) Obtener feriados usando el modelo ORM
    feriados_dict = {}
    try:
        for feriado in Feriados.objects.all():
            feriados_dict[feriado.fecha] = feriado.descripcion
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
    
    # 1. Obtener feriados usando el modelo ORM
    feriados_dict = {}
    try:
        for feriado in Feriados.objects.all():
            feriados_dict[feriado.fecha] = feriado.descripcion
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
    
    turnos = Turno.objects.filter(fecha=fecha_obj).select_related('agenda').order_by('agenda__name', 'apellido', 'nombre')
    
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
def dia(request, fecha):
    # Convertir fecha a objeto date si viene como string
    from datetime import datetime
    if isinstance(fecha, str):
        fecha = datetime.strptime(fecha, '%Y-%m-%d').date()
    
    # Verificar si es feriado usando el modelo ORM
    es_feriado = False
    descripcion_feriado = None
    try:
        feriado_obj = Feriados.objects.get(fecha=fecha)
        es_feriado = True
        descripcion_feriado = feriado_obj.descripcion
    except Feriados.DoesNotExist:
        es_feriado = False
    
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
                    from django.conf import settings
                    
                    # Validar que la fecha no sea feriado
                    if Feriados.objects.filter(fecha=fecha).exists():
                        feriado = Feriados.objects.get(fecha=fecha)
                        form.add_error(None, ValidationError(f"No se pueden asignar turnos en feriados: {feriado.descripcion}"))
                    else:
                        agenda_form = form.cleaned_data.get('agenda')
                        dni = form.cleaned_data.get('dni')
                        nombre = form.cleaned_data.get('nombre')
                        apellido = form.cleaned_data.get('apellido')
                        fecha_nacimiento = form.cleaned_data.get('fecha_nacimiento')
                        sexo = form.cleaned_data.get('sexo')
                        telefono = form.cleaned_data.get('telefono', '')
                        email = form.cleaned_data.get('email', '')
                        observaciones_paciente = form.cleaned_data.get('observaciones_paciente', '')
                        medico_nombre = form.cleaned_data.get('medico', '')  # Este va al turno, no al paciente
                        nota_interna = form.cleaned_data.get('nota_interna', '')  # Este va al turno
                        
                        # Obtener la instancia de Médico por nombre
                        medico_obj = None
                        if medico_nombre:
                            try:
                                medico_obj = Medico.objects.get(nombre=medico_nombre)
                            except Medico.DoesNotExist:
                                # Si no existe, intenta por coincidencia parcial (para nombres guardados como texto)
                                medicos = Medico.objects.filter(nombre__icontains=medico_nombre)
                                if medicos.exists():
                                    medico_obj = medicos.first()
                        
                        # Guardar o actualizar paciente usando ORM (tabla pacientes_paciente)
                        paciente_obj, created = Paciente.objects.update_or_create(
                            iden=dni,
                            defaults={
                                'nombre': nombre,
                                'apellido': apellido,
                                'fecha_nacimiento': fecha_nacimiento,
                                'sexo': sexo,
                                'telefono': telefono,
                                'email': email,
                                'observaciones': observaciones_paciente,
                            }
                        )
                        
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
                            nuevo.dni = paciente_obj  # Asignar la instancia de Paciente
                            nuevo.medico = medico_obj  # Asignar la instancia de Médico (puede ser None)
                            nuevo.nota_interna = nota_interna
                            nuevo.usuario = request.user  # Asignar la instancia de User, no el username
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
        
        # Obtener IDs de turnos coordinados para la fecha
        turnos_coordinados_ids = set(Coordinados.objects.filter(id_turno__in=turnos_all.values_list('id', flat=True)).values_list('id_turno', flat=True))

        # Agrupar turnos por agenda y por coordinación
        for turno in turnos_all:
            if turno.agenda.id not in turnos_por_agenda:
                turnos_por_agenda[turno.agenda.id] = {
                    'agenda': turno.agenda,
                    'coordinados': [],
                    'no_coordinados': [],
                    'capacidad': agendas_disponibilidad.get(turno.agenda.id, {}).get('capacidad', 0),
                    'usados': agendas_disponibilidad.get(turno.agenda.id, {}).get('usados', 0),
                    'disponibles': agendas_disponibilidad.get(turno.agenda.id, {}).get('disponibles', 0)
                }
            if turno.id in turnos_coordinados_ids:
                turnos_por_agenda[turno.agenda.id]['coordinados'].append(turno)
            else:
                turnos_por_agenda[turno.agenda.id]['no_coordinados'].append(turno)

        # Agregar agendas con disponibilidad pero sin turnos (solo para fechas futuras con capacidad)
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
        # Mostrar formulario solo si hay disponibles Y una agenda específica seleccionada Y NO es feriado
        'show_form': True if (disponibles > 0 and agenda_obj and modo_vista == 'agenda_seleccionada' and not es_feriado) else False,
        'es_feriado': es_feriado,
        'descripcion_feriado': descripcion_feriado
    }
    return render(request, 'turnos/dia.html', context)


@login_required
def buscar(request):
    from datetime import date
    from .models import Coordinados
    from determinaciones.models import DeterminacionCompleja
    
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
            resultados = Turno.objects.filter(dni__apellido__icontains=apellido).select_related('dni', 'agenda').order_by('-fecha')
        else:
            resultados = Turno.objects.filter(dni__iden__icontains=q).select_related('dni', 'agenda').order_by('-fecha')
            
        hoy = date.today()
        
        # Obtener IDs de turnos coordinados
        turnos_coordinados_ids = set(Coordinados.objects.values_list('id_turno', flat=True))
        
        # Separar turnos en previos y pendientes y agregar nombres de determinaciones usando ORM
        for turno in resultados:
            turno.esta_coordinado = turno.id in turnos_coordinados_ids

            if turno.determinaciones:
                codigos = [c.strip() for c in turno.determinaciones.split(',') if c.strip()]
                det_codes = [c for c in codigos if not c.startswith('/')]
                codigos_con_slash = [c for c in codigos if c.startswith('/')]

                # Determinaciones simples
                det_map = {d.codigo: d.nombre for d in Determinacion.objects.filter(codigo__in=det_codes)}
                nombres = []

                # determinaciones individuales
                for code in det_codes:
                    nombres.append(det_map.get(code, code))

                # Procesar códigos con / (pueden ser complejas o perfiles)
                for code in codigos_con_slash:
                    code_sin_slash = code.lstrip('/')
                    
                    # Primero intentar como determinación compleja (con /)
                    compleja = DeterminacionCompleja.objects.filter(codigo=code).first()
                    if compleja:
                        nombres.append(compleja.nombre)
                        continue
                    
                    # Si no es compleja, buscar como perfil (sin /)
                    perfil = PerfilDeterminacion.objects.filter(codigo=code_sin_slash).first()
                    if perfil:
                        cant = len(perfil.determinaciones or [])
                        nombres.append(f"Perfil {perfil.codigo} ({cant} dets)")

                turno.determinaciones_nombres = ', '.join(nombres) if nombres else turno.determinaciones
            else:
                turno.determinaciones_nombres = ''

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
def ver_coordinacion(request, turno_id):
    """Ver detalles completos de un turno coordinado (solo lectura)."""
    from datetime import date
    from .models import Coordinados
    
    turno = get_object_or_404(Turno.objects.select_related('dni', 'medico', 'agenda'), id=turno_id)
    
    # Verificar que el turno esté coordinado
    coordinacion = Coordinados.objects.filter(id_turno=turno_id).first()
    
    # Obtener datos del paciente desde la FK
    paciente_data = None
    if turno.dni:
        paciente_data = {
            'nombre': turno.dni.nombre,
            'apellido': turno.dni.apellido,
            'dni': turno.dni.iden,
            'fecha_nacimiento': turno.dni.fecha_nacimiento,
            'sexo': turno.dni.sexo,
            'telefono': turno.dni.telefono or '',
            'email': turno.dni.email or ''
        }
    
    # Obtener datos del médico desde la FK
    medico_data = None
    if turno.medico:
        medico_data = {
            'matricula': turno.medico.matricula,
            'nombre': turno.medico.nombre
        }
    
    # Obtener nombres de determinaciones y perfiles
    from determinaciones.models import Determinacion, PerfilDeterminacion, DeterminacionCompleja
    
    determinaciones_nombres = []
    if turno.determinaciones:
        codigos = [c.strip() for c in turno.determinaciones.split(',') if c.strip()]
        
        for codigo in codigos:
            if codigo.startswith('/'):
                # Es un perfil o determinación compleja
                # Intentar buscar como determinación compleja primero
                compleja = DeterminacionCompleja.objects.filter(codigo=codigo).first()
                if compleja:
                    determinaciones_nombres.append(f"{codigo} - {compleja.nombre}")
                    continue
                
                # Si no, buscar como perfil (sin el /)
                codigo_sin_slash = codigo.lstrip('/')
                perfil = PerfilDeterminacion.objects.filter(codigo=codigo_sin_slash).first()
                if perfil:
                    determinaciones_nombres.append(f"{codigo} - {perfil.nombre}")
            else:
                # Es una determinación simple
                try:
                    det = Determinacion.objects.filter(codigo=codigo).first()
                    if det:
                        determinaciones_nombres.append(f"{codigo} - {det.nombre}")
                    else:
                        determinaciones_nombres.append(codigo)
                except Exception:
                    determinaciones_nombres.append(codigo)
    
    context = {
        'turno': turno,
        'coordinacion': coordinacion,
        'paciente': paciente_data,
        'medico': medico_data,
        'determinaciones_nombres': determinaciones_nombres,
        'hoy': date.today()
    }
    
    return render(request, 'turnos/ver_coordinacion.html', context)


@login_required
def editar_turno(request, turno_id):
    """Editar un turno existente."""
    turno = get_object_or_404(Turno, id=turno_id)
    
    # Obtener datos del paciente desde la FK
    paciente_data = None
    if turno.dni:
        paciente_data = {
            'nombre': turno.dni.nombre,
            'apellido': turno.dni.apellido,
            'dni': turno.dni.iden,
            'fecha_nacimiento': turno.dni.fecha_nacimiento,
            'sexo': turno.dni.sexo,
            'telefono': turno.dni.telefono,
            'email': turno.dni.email,
            'observaciones': turno.dni.observaciones or ''
        }
    
    if request.method == 'POST':
        # Actualizar turno (agenda, fecha, determinaciones, medico y nota_interna)
        turno.agenda_id = request.POST.get('agenda')
        turno.fecha = request.POST.get('fecha')
        turno.determinaciones = request.POST.get('determinaciones', '')
        
        # Manejar el médico correctamente
        medico_nombre = request.POST.get('medico', '')
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
        
        turno.nota_interna = request.POST.get('nota_interna', '')
        turno.save()

        # Actualizar datos del paciente si se enviaron (telefono, email, observaciones)
        telefono = request.POST.get('telefono', '')
        email = request.POST.get('email', '')
        observaciones_paciente = request.POST.get('observaciones_paciente', '')

        if turno.dni and (telefono or email or observaciones_paciente):
            turno.dni.telefono = telefono or turno.dni.telefono
            turno.dni.email = email or turno.dni.email
            turno.dni.observaciones = observaciones_paciente or turno.dni.observaciones
            turno.dni.save()

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
def listar_medicos_api(request):
    """API para listar todos los médicos"""
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



@login_required
def coordinar_turno(request, turno_id):
    """Genera archivo ASTM para coordinar turno y registra en Coordinados"""
    from datetime import datetime
    import os
    from .models import Coordinados
    from pacientes.models import Paciente
    from determinaciones.models import Determinacion, PerfilDeterminacion
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'})
    
    try:
        # Verificar si el turno ya fue coordinado
        if Coordinados.objects.filter(id_turno=turno_id).exists():
            return JsonResponse({'success': False, 'error': 'Este turno ya fue coordinado anteriormente'})
        
        # Obtener el turno con FK
        turno = get_object_or_404(Turno.objects.select_related('dni'), id=turno_id)
        
        paciente_obj = turno.dni
        if not paciente_obj:
            return JsonResponse({'success': False, 'error': 'Paciente no encontrado'})

        nombre = paciente_obj.nombre
        apellido = paciente_obj.apellido
        dni = paciente_obj.iden
        fecha_nacimiento = paciente_obj.fecha_nacimiento
        sexo = paciente_obj.sexo
        telefono = paciente_obj.telefono
        email = paciente_obj.email
        
        # Convertir sexo al formato ASTM (M/F/U)
        sexo_astm = 'M' if sexo == 'Masculino' else ('F' if sexo == 'Femenino' else 'U')
        
        # Preparar telefono y email (sin comillas)
        telefono_astm = telefono if telefono else ''
        email_astm = email if email else ''
        
        # Formatear fechas
        ahora = datetime.now()
        timestamp = ahora.strftime('%Y%m%d%H%M%S')  # AAAAMMDDHHMMSS
        fecha_nac = fecha_nacimiento.strftime('%Y%m%d')  # AAAAMMDD
        
        # Procesar determinaciones/perfiles/complejas
        determinaciones_str = turno.determinaciones if turno.determinaciones else ''
        codigos = [c.strip() for c in determinaciones_str.split(',') if c.strip()]
        det_codes = [c for c in codigos if not c.startswith('/')]
        complejas_codes = [c for c in codigos if c.startswith('/')]

        determinaciones_astm = []
        if det_codes:
            determinaciones_astm.extend([f'^^^{c}\\' for c in det_codes])

        if complejas_codes:
            # Procesar determinaciones complejas (código incluye /)
            complejas = DeterminacionCompleja.objects.filter(codigo__in=complejas_codes)
            for compleja in complejas:
                for det_code in compleja.determinaciones:
                    determinaciones_astm.append(f'^^^{det_code}\\')
            
            # Procesar perfiles (buscar sin /)
            perfil_codes = [c.lstrip('/') for c in complejas_codes]
            perfiles = PerfilDeterminacion.objects.filter(codigo__in=perfil_codes)
            for perfil in perfiles:
                for det_code in perfil.determinaciones:
                    # Si el código dentro del perfil es una determinación compleja
                    if det_code.startswith('/'):
                        compleja_en_perfil = DeterminacionCompleja.objects.filter(codigo=det_code).first()
                        if compleja_en_perfil:
                            # Expandir la determinación compleja
                            for sub_det_code in compleja_en_perfil.determinaciones:
                                determinaciones_astm.append(f'^^^{sub_det_code}\\')
                    else:
                        # Es una determinación simple
                        determinaciones_astm.append(f'^^^{det_code}\\')
        
        # Preparar nota_interna (sin comillas)
        nota_interna_astm = turno.nota_interna if turno.nota_interna else ''
        # Observaciones de paciente (sin comillas)
        # Buscar en la tabla pacientes
        observaciones_paciente = paciente_obj.observaciones or ''
        # Nombre y matrícula del médico (sin comillas)
        nombre_medico = turno.medico.nombre if turno.medico else ''
        matricula_medico = turno.medico.matricula if turno.medico else ''
        # Impresora desde JSON (body) o POST clásico
        if request.content_type == 'application/json':
            try:
                data = json.loads(request.body.decode('utf-8'))
                nombre_impresora = data.get('nombre_impresora', '')
            except Exception:
                nombre_impresora = ''
        else:
            nombre_impresora = request.POST.get('nombre_impresora', '')
        if not nombre_impresora:
            nombre_impresora = ''
        nombre_impresora = nombre_impresora.strip()
        # Construir el contenido del archivo ASTM
        lineas = []
        lineas.append(f'H|\\^&|||Balestrini|||||||P||{timestamp}')
        lineas.append(f'P|1||{dni}||{apellido}^{nombre}^||{fecha_nac}|{sexo_astm}|{email_astm}|{telefono_astm}|{nota_interna_astm}|{observaciones_paciente}|||||| |||||{timestamp}||||||||||')
        # Construir línea O con todas las determinaciones/perfiles
        determinaciones_concatenadas = ''.join(determinaciones_astm)
        # Insertar el nombre de usuario en el campo correspondiente (sin comillas)
        usuario = request.user.username if request.user.is_authenticated else ''
        # El campo de usuario va en la posición donde en el ejemplo aparece "nombre_usuario"
        # O|1|46||^^^1000...|nombre_usuario|ADM2|MALVIDO  JOSE MARIA|332706||A||||||||||||||O
        # Usamos el mismo orden de campos:
        # O|1|<id>|...|<usuario>|<nombre_impresora>|<nombre_medico>|<matricula_medico>|...resto
        lineas.append(f'O|1|{turno_id}||{determinaciones_concatenadas}|||{nombre_impresora}|{nombre_medico}|{matricula_medico}|{usuario}|A||||||||||||||O')
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
            dni=paciente_obj,  # Usar la instancia de Paciente, no el string del DNI
            determinaciones=turno.determinaciones,
            usuario=request.user if request.user.is_authenticated else None
        )
        
        # Construir URL del ticket de retiro
        from django.urls import reverse
        ticket_retiro_url = reverse('turnos:generar_ticket_retiro', args=[turno_id])
        return JsonResponse({
            'success': True,
            'mensaje': f'Turno coordinado exitosamente. Mensaje generado: {nombre_archivo}',
            'ticket_retiro_url': ticket_retiro_url
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def generar_ticket_turno(request, turno_id):
    """Genera un ticket PDF para impresora térmica de 8cm de ancho"""
    from datetime import date, datetime
    from io import BytesIO
    from reportlab.lib.units import cm
    from reportlab.pdfgen import canvas
    from django.shortcuts import get_object_or_404
    from pacientes.models import Paciente
    from determinaciones.models import Determinacion, PerfilDeterminacion, DeterminacionCompleja

    turno = get_object_or_404(Turno.objects.select_related('agenda', 'dni', 'medico'), id=turno_id)

    # Paciente desde FK
    paciente_obj = turno.dni

    edad = None
    if paciente_obj and paciente_obj.fecha_nacimiento:
        fecha_nac = paciente_obj.fecha_nacimiento
        fecha_turno = turno.fecha
        edad = fecha_turno.year - fecha_nac.year
        if (fecha_turno.month, fecha_turno.day) < (fecha_nac.month, fecha_nac.day):
            edad -= 1

    # Determinaciones, perfiles y complejas
    determinaciones_texto = turno.determinaciones or ""
    codigos = [c.strip() for c in determinaciones_texto.split(',') if c.strip()]
    codigos_con_slash = [c for c in codigos if c.startswith('/')]
    det_codigos = [c for c in codigos if not c.startswith('/')]

    # Determinaciones simples
    det_objs = Determinacion.objects.filter(codigo__in=det_codigos)
    det_map = {d.codigo: d.nombre for d in det_objs}
    determinaciones_list = [(code, det_map.get(code, code)) for code in det_codigos]

    # Procesar códigos con / (pueden ser perfiles o complejas)
    perfiles_list = []
    complejas_list = []
    
    for code in codigos_con_slash:
        code_sin_slash = code.lstrip('/')
        
        # Intentar primero como determinación compleja (con /)
        compleja_obj = DeterminacionCompleja.objects.filter(codigo=code).first()
        if compleja_obj:
            complejas_list.append((code, compleja_obj.nombre))
            continue
        
        # Si no es compleja, buscar como perfil (sin /)
        perfil_obj = PerfilDeterminacion.objects.filter(codigo=code_sin_slash).first()
        if perfil_obj:
            dets_codes = perfil_obj.determinaciones
            # Expandir subdeterminaciones del perfil
            sub_dets = []
            for sub_code in dets_codes:
                if sub_code.startswith('/'):
                    # Es una compleja dentro del perfil
                    sub_compleja = DeterminacionCompleja.objects.filter(codigo=sub_code).first()
                    if sub_compleja:
                        sub_dets.append(sub_compleja.nombre)
                else:
                    # Es una determinación simple
                    det_obj = Determinacion.objects.filter(codigo=sub_code).first()
                    if det_obj:
                        sub_dets.append(det_obj.nombre)
            
            display = f"{code_sin_slash}: " + ', '.join(sub_dets) if sub_dets else code_sin_slash
            perfiles_list.append((code_sin_slash, display))

    agenda_nombre = turno.agenda.name if turno.agenda else ""
    apellido = turno.apellido or ""
    nombre = turno.nombre or ""
    dni = turno.paciente_dni or ""
    telefono = paciente_obj.telefono if paciente_obj else ""
    email = paciente_obj.email if paciente_obj else ""
    # Obtener apellido y nombre del usuario
    if turno.usuario:
        usuario_asignador = f"{turno.usuario.last_name}, {turno.usuario.first_name}" if turno.usuario.last_name and turno.usuario.first_name else turno.usuario.username
    else:
        usuario_asignador = f"{request.user.last_name}, {request.user.first_name}" if request.user.last_name and request.user.first_name else request.user.username
    medico_nombre = turno.medico.nombre if turno.medico else ""
    fecha_turno = turno.fecha
    
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
    p.drawCentredString(ancho_papel / 2, y, agenda_nombre)
    y -= 0.6 * cm
    
    # Línea separadora
    p.line(margen, y, ancho_papel - margen, y)
    y -= 0.5 * cm
    
    # ====== DATOS DEL PACIENTE ======
    p.setFont("Helvetica-Bold", 9)
    p.drawString(margen, y, "Paciente:")
    p.setFont("Helvetica", 9)
    # Formatear: Apellido, Nombre (primera letra mayúscula, resto minúscula)
    apellido_formateado = apellido.strip().capitalize() if apellido else ""
    nombre_formateado = nombre.strip().capitalize() if nombre else ""
    nombre_completo = f"{apellido_formateado}, {nombre_formateado}"
    p.drawString(margen + 2*cm, y, nombre_completo)
    y -= 0.45 * cm
    
    # DNI
    p.setFont("Helvetica-Bold", 9)
    p.drawString(margen, y, "DNI:")
    p.setFont("Helvetica", 9)
    p.drawString(margen + 2*cm, y, str(dni))
    y -= 0.45 * cm
    
    # Teléfono (si existe)
    if telefono:
        p.setFont("Helvetica-Bold", 9)
        p.drawString(margen, y, "Teléfono:")
        p.setFont("Helvetica", 9)
        p.drawString(margen + 2*cm, y, str(telefono))
        y -= 0.45 * cm
    
    # Email (si existe)
    if email:
        p.setFont("Helvetica-Bold", 9)
        p.drawString(margen, y, "Email:")
        p.setFont("Helvetica", 7)
        # Dividir email si es muy largo
        email_str = str(email)
        if len(email_str) > 30:
            p.drawString(margen + 2*cm, y, email_str[:30])
            y -= 0.35 * cm
            p.drawString(margen + 2*cm, y, email_str[30:])
            y -= 0.45 * cm
        else:
            p.setFont("Helvetica", 9)
            p.drawString(margen + 2*cm, y, email_str)
            y -= 0.45 * cm
    
    if edad is not None:
        p.setFont("Helvetica-Bold", 9)
        p.drawString(margen, y, "Edad:")
        p.setFont("Helvetica", 9)
        p.drawString(margen + 2*cm, y, f"{edad} años")
        y -= 0.45 * cm
    
    # Médico solicitante (si existe)
    if medico_nombre:
        p.setFont("Helvetica-Bold", 9)
        p.drawString(margen, y, "Médico:")
        p.setFont("Helvetica", 9)
        # Formatear: Primera letra mayúscula, resto minúscula
        medico_str = str(medico_nombre).strip().capitalize()
        # Dividir si el nombre es muy largo
        if len(medico_str) > 30:
            p.drawString(margen + 2*cm, y, medico_str[:30])
            y -= 0.35 * cm
            p.drawString(margen + 2*cm, y, medico_str[30:])
            y -= 0.45 * cm
        else:
            p.drawString(margen + 2*cm, y, medico_str)
            y -= 0.45 * cm
    
    # ====== FECHA DEL TURNO (EN NEGRITA) ======
    p.setFont("Helvetica-Bold", 10)
    fecha_str = fecha_turno.strftime('%d/%m/%Y')
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
    
    # Mostrar determinaciones complejas
    if complejas_list:
        p.setFont("Helvetica", 8)
        for compleja in complejas_list:
            texto_compleja = f"• {compleja[1].upper()}"
            # Dividir si es muy largo
            if len(texto_compleja) > 40:
                p.drawString(margen + 0.2*cm, y, texto_compleja[:40])
                y -= 0.35 * cm
                p.drawString(margen + 0.4*cm, y, texto_compleja[40:])
                y -= 0.4 * cm
            else:
                p.drawString(margen + 0.2*cm, y, texto_compleja)
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
    
    # Si no hay ni perfiles ni determinaciones ni complejas
    if not perfiles_list and not determinaciones_list and not complejas_list:
        p.setFont("Helvetica", 8)
        p.drawString(margen + 0.2*cm, y, "(Sin estudios especificados)")
        y -= 0.4 * cm
    
    y -= 0.3 * cm
    
    # Línea separadora
    p.line(margen, y, ancho_papel - margen, y)
    y -= 0.5 * cm
    
    # ====== INDICACIONES FIJAS ======
    p.setFont("Helvetica-Bold", 9)
    p.drawCentredString(ancho_papel / 2, y, "INDICACIONES")
    y -= 0.45 * cm
    
    p.setFont("Helvetica", 10)
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
    p.setFont("Helvetica", 10)
    p.drawCentredString(ancho_papel / 2, y, f"Ticket asignado por: {usuario_asignador}")
    y -= 0.5 * cm
    # Agregar el email debajo del nombre de usuario
    p.drawCentredString(ancho_papel / 2, y, "admlabobalestrini@gmail.com")
    y -= 0.5 * cm
    p.setFont("Helvetica-Bold", 11)
    p.drawCentredString(ancho_papel / 2, y, f"Ticket N° {turno_id}")
    y -= 0.35 * cm
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
    # Vista legacy basada en tablas antiguas; redirigimos al admin de Django que refleja los modelos actuales
    from django.urls import reverse
    return redirect(reverse('admin:index'))


@user_passes_test(lambda u: u.is_superuser)
def administrar_tabla_detalle(request, tabla):
    from django.urls import reverse
    return redirect(reverse('admin:index'))


@user_passes_test(lambda u: u.is_superuser)
def crear_registro(request, tabla):
    from django.urls import reverse
    return redirect(reverse('admin:index'))


@user_passes_test(lambda u: u.is_superuser)
def editar_registro(request, tabla, id):
    from django.urls import reverse
    return redirect(reverse('admin:index'))


@user_passes_test(lambda u: u.is_superuser)
def eliminar_registro(request, tabla, id):
    from django.urls import reverse
    return redirect(reverse('admin:index'))


@user_passes_test(lambda u: u.is_superuser)
def aplicar_feriados(request):
    from django.urls import reverse
    return redirect(reverse('admin:index'))


@login_required
@user_passes_test(lambda u: u.is_superuser)
def audit_log(request):
    """Vista para mostrar el registro de auditoría (solo superusuarios)"""
    from auditlog.models import LogEntry
    from django.core.paginator import Paginator
    from django.contrib.contenttypes.models import ContentType
    
    # Obtener todos los logs
    logs = LogEntry.objects.select_related('content_type', 'actor').all()
    
    # Filtros
    action = request.GET.get('action', '')
    model = request.GET.get('model', '')
    user = request.GET.get('user', '')
    
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
    
    # Ordenar por más reciente primero
    logs = logs.order_by('-timestamp')
    
    # Paginación
    paginator = Paginator(logs, 20)  # 20 registros por página
    page_number = request.GET.get('page', 1)
    logs_page = paginator.get_page(page_number)
    
    context = {
        'logs': logs_page,
        'action': action,
        'model': model,
        'user': user,
    }
    
    return render(request, 'turnos/audit_log.html', context)


@csrf_exempt
@login_required
def crear_medico_api(request):
    """API para crear un médico desde el modal (POST JSON)"""
    import psycopg2
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)
    try:
        data = json.loads(request.body)
        nombre_apellido = data.get('nombre_apellido', '').strip()
        matricula_provincial = data.get('matricula_provincial', '').strip()
        if not nombre_apellido or not matricula_provincial:
            return JsonResponse({'success': False, 'error': 'Faltan datos requeridos'}, status=400)
        conn = get_db_conn()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO medicos (matricula_provincial, nombre_apellido, usuario)
            VALUES (%s, %s, %s)
        """, (matricula_provincial, nombre_apellido, request.user.username))
        conn.commit()
        cursor.close()
        conn.close()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


def crear_medico_api(request):
    """API para crear un nuevo médico"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=400)
    
    try:
        import json
        data = json.loads(request.body)
        nombre = data.get('nombre_apellido', '').strip()
        matricula = data.get('matricula_provincial', '').strip()
        
        if not nombre or not matricula:
            return JsonResponse({'success': False, 'error': 'Nombre y matrícula son requeridos'})
        
        # Crear el médico
        medico, created = Medico.objects.get_or_create(
            matricula=matricula,
            defaults={'nombre': nombre}
        )
        
        if created:
            return JsonResponse({'success': True, 'message': 'Médico creado correctamente'})
        else:
            return JsonResponse({'success': False, 'error': 'La matrícula ya existe'})
    
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
