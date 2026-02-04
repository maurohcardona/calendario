"""
Vistas administrativas y de auditoría.
"""
import json
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import redirect, render
from django.http import JsonResponse
from django.urls import reverse
from django.core.paginator import Paginator
from django.contrib.contenttypes.models import ContentType
from django.views.decorators.csrf import csrf_exempt
from django.db import models
from medicos.models import Medico


@user_passes_test(lambda u: u.is_superuser)
def administrar_tablas(request):
    """Redirige al admin de Django."""
    return redirect(reverse('admin:index'))


@user_passes_test(lambda u: u.is_superuser)
def administrar_tabla_detalle(request, tabla):
    """Redirige al admin de Django."""
    return redirect(reverse('admin:index'))


@user_passes_test(lambda u: u.is_superuser)
def crear_registro(request, tabla):
    """Redirige al admin de Django."""
    return redirect(reverse('admin:index'))


@user_passes_test(lambda u: u.is_superuser)
def editar_registro(request, tabla, id):
    """Redirige al admin de Django."""
    return redirect(reverse('admin:index'))


@user_passes_test(lambda u: u.is_superuser)
def eliminar_registro(request, tabla, id):
    """Redirige al admin de Django."""
    return redirect(reverse('admin:index'))


@user_passes_test(lambda u: u.is_superuser)
def aplicar_feriados(request):
    """Redirige al admin de Django."""
    return redirect(reverse('admin:index'))


@login_required
@user_passes_test(lambda u: u.is_superuser)
def audit_log(request):
    """Vista para mostrar el registro de auditoría (solo superusuarios)."""
    from auditlog.models import LogEntry
    from pacientes.models import Paciente
    import json
    
    # Obtener todos los logs
    logs = LogEntry.objects.select_related('content_type', 'actor').all()
    
    # Filtros
    action = request.GET.get('action', '')
    model = request.GET.get('model', '')
    user = request.GET.get('user', '')
    dni = request.GET.get('dni', '')
    turno_id = request.GET.get('turno_id', '')
    
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
    
    # Filtro por número de turno
    if turno_id:
        try:
            # Buscar logs del turno mismo
            turno_ct = ContentType.objects.get(model='turno')
            turno_filters = models.Q(content_type=turno_ct, object_id=turno_id)
            
            # También buscar logs de coordinaciones de este turno
            try:
                coordinados_ct = ContentType.objects.get(model='coordinados')
                from turnos.models import Coordinados
                # Buscar todos los coordinados de este turno
                coordinados_ids = Coordinados.objects.filter(id_turno_id=turno_id).values_list('id', flat=True)
                if coordinados_ids:
                    turno_filters |= models.Q(content_type=coordinados_ct, object_id__in=coordinados_ids)
            except:
                pass
            
            logs = logs.filter(turno_filters)
        except:
            pass
    
    # Filtro por DNI del paciente
    if dni:
        # Buscar paciente por DNI
        pacientes = Paciente.objects.filter(iden__icontains=dni)
        if pacientes.exists():
            # Filtrar logs que contengan el DNI del paciente en los cambios
            # o que sean del modelo Turno y referencien al paciente
            dni_filters = models.Q()
            for paciente in pacientes:
                # Filtrar por object_id si es un Turno
                try:
                    turno_ct = ContentType.objects.get(model='turno')
                    # Buscar turnos de este paciente
                    from turnos.models import Turno
                    turnos_paciente = Turno.objects.filter(dni=paciente).values_list('id', flat=True)
                    dni_filters |= models.Q(content_type=turno_ct, object_id__in=turnos_paciente)
                except:
                    pass
                
                # También buscar en el campo changes que contenga el DNI
                dni_filters |= models.Q(changes__icontains=paciente.iden)
            
            logs = logs.filter(dni_filters)
    
    # Ordenar por más reciente primero
    logs = logs.order_by('-timestamp')
    
    # Paginación
    paginator = Paginator(logs, 20)
    page_number = request.GET.get('page', 1)
    logs_page = paginator.get_page(page_number)
    
    context = {
        'logs': logs_page,
        'action': action,
        'model': model,
        'user': user,
        'dni': dni,
        'turno_id': turno_id,
    }
    
    return render(request, 'turnos/audit_log.html', context)


@csrf_exempt
@login_required
def crear_medico_api(request):
    """API para crear un nuevo médico."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=400)
    
    try:
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
