"""
Vistas relacionadas con coordinación de turnos y generación de tickets.
"""
import json
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.http import JsonResponse, HttpResponse
from django.urls import reverse
from turnos.models import Turno, Coordinados
from turnos.services import ASTMService, PDFService, DeterminacionService
from datetime import date


@login_required
def precoordinacion_turno(request, turno_id):
    """Vista de pre-coordinación: permite editar datos personales y coordinar el turno."""
    from turnos.models import Agenda
    from pacientes.models import Paciente
    from medicos.models import Medico
    from datetime import datetime
    
    turno = get_object_or_404(Turno.objects.select_related('medico', 'dni', 'agenda'), id=turno_id)

    paciente_obj = turno.dni
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

        # Actualizar datos del turno
        turno.agenda_id = request.POST.get('agenda')
        turno.fecha = request.POST.get('fecha')
        turno.determinaciones = request.POST.get('determinaciones', '')
        
        # Manejar el médico
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
def ver_coordinacion(request, turno_id):
    """Ver detalles completos de un turno coordinado (solo lectura)."""
    turno = get_object_or_404(Turno.objects.select_related('dni', 'medico', 'agenda'), id=turno_id)
    
    # Verificar que el turno esté coordinado
    coordinacion = Coordinados.objects.filter(id_turno=turno_id).first()
    
    # Obtener datos del paciente
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
    
    # Obtener datos del médico
    medico_data = None
    if turno.medico:
        medico_data = {
            'matricula': turno.medico.matricula,
            'nombre': turno.medico.nombre
        }
    
    # Obtener nombres de determinaciones
    determinaciones_nombres = []
    if turno.determinaciones:
        codigos = [c.strip() for c in turno.determinaciones.split(',') if c.strip()]
        
        from determinaciones.models import Determinacion, PerfilDeterminacion, DeterminacionCompleja
        
        for codigo in codigos:
            if codigo.startswith('/'):
                # Es un perfil o determinación compleja
                compleja = DeterminacionCompleja.objects.filter(codigo=codigo).first()
                if compleja:
                    determinaciones_nombres.append(f"{codigo} - {compleja.nombre}")
                    continue
                
                codigo_sin_slash = codigo.lstrip('/')
                perfil = PerfilDeterminacion.objects.filter(codigo=codigo_sin_slash).first()
                if perfil:
                    determinaciones_nombres.append(f"{codigo} - {perfil.nombre}")
            else:
                # Es una determinación simple
                det = Determinacion.objects.filter(codigo=codigo).first()
                if det:
                    determinaciones_nombres.append(f"{codigo} - {det.nombre}")
                else:
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
def coordinar_turno(request, turno_id):
    """Genera archivo ASTM para coordinar turno y registra en Coordinados"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'})
    
    try:
        turno = get_object_or_404(Turno.objects.select_related('dni'), id=turno_id)
        
        # Obtener nombre de impresora
        if request.content_type == 'application/json':
            try:
                data = json.loads(request.body)
                nombre_impresora = data.get('impresora', '')
            except:
                nombre_impresora = request.POST.get('impresora', '')
        else:
            nombre_impresora = request.POST.get('impresora', '')
        
        if not nombre_impresora:
            return JsonResponse({'success': False, 'error': 'Debe seleccionar una impresora'})
        
        nombre_impresora = nombre_impresora.strip()
        usuario = request.user.username if request.user.is_authenticated else ''
        
        # Generar archivo ASTM usando el servicio
        exito, ruta_archivo, mensaje_error = ASTMService.generar_archivo_astm(
            turno, nombre_impresora, usuario
        )
        
        if exito:
            return JsonResponse({
                'success': True,
                'message': f'Turno coordinado exitosamente. Archivo: {ruta_archivo}'
            })
        else:
            return JsonResponse({'success': False, 'error': mensaje_error})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Error inesperado: {str(e)}'})


@login_required
def generar_ticket_turno(request, turno_id):
    """Genera un ticket PDF de turno para impresora térmica."""
    turno = get_object_or_404(Turno.objects.select_related('agenda', 'dni', 'medico'), id=turno_id)
    
    # Obtener apellido y nombre del usuario
    if turno.usuario:
        usuario_asignador = f"{turno.usuario.last_name}, {turno.usuario.first_name}" if turno.usuario.last_name and turno.usuario.first_name else turno.usuario.username
    else:
        usuario_asignador = f"{request.user.last_name}, {request.user.first_name}" if request.user.last_name and request.user.first_name else request.user.username
    
    return PDFService.generar_ticket_turno(turno, usuario_asignador)


@login_required
def generar_ticket_retiro(request, turno_id):
    """Genera un ticket PDF de retiro para impresora térmica."""
    turno = get_object_or_404(Turno.objects.select_related('agenda', 'dni'), id=turno_id)
    
    # Obtener el usuario que coordinó el turno desde Coordinados
    coordinacion = Coordinados.objects.filter(id_turno=turno_id).first()
    
    if coordinacion and coordinacion.usuario:
        # Usar el usuario que coordinó
        usuario_asignador = f"{coordinacion.usuario.last_name}, {coordinacion.usuario.first_name}" if coordinacion.usuario.last_name and coordinacion.usuario.first_name else coordinacion.usuario.username
    else:
        # Fallback: usar el usuario actual
        usuario_asignador = f"{request.user.last_name}, {request.user.first_name}" if request.user.last_name and request.user.first_name else request.user.username
    
    return PDFService.generar_ticket_retiro(turno, usuario_asignador)


@login_required
def control_ordenes(request):
    """Vista de control de órdenes coordinadas del día actual o fecha seleccionada"""
    from datetime import datetime
    
    # Obtener fecha del parámetro GET o usar hoy por defecto
    fecha_str = request.GET.get('fecha')
    if fecha_str:
        try:
            fecha_control = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        except ValueError:
            fecha_control = date.today()
    else:
        fecha_control = date.today()
    
    # Obtener IDs de turnos coordinados
    turnos_coordinados_ids = Coordinados.objects.values_list('id_turno', flat=True)
    
    # Filtrar turnos de la fecha seleccionada que estén coordinados
    turnos = Turno.objects.filter(
        id__in=turnos_coordinados_ids,
        fecha=fecha_control
    ).select_related('dni', 'agenda', 'medico').order_by('agenda__name', 'creado')
    
    # Preparar datos de turnos con determinaciones expandidas
    ordenes = []
    for turno in turnos:
        determinaciones_detalle = DeterminacionService.obtener_determinaciones_detalladas(
            turno.determinaciones
        )
        
        ordenes.append({
            'turno': turno,
            'determinaciones': determinaciones_detalle
        })
    
    context = {
        'fecha': fecha_control,
        'ordenes': ordenes,
        'total_ordenes': len(ordenes)
    }
    
    return render(request, 'turnos/control.html', context)
