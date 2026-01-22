from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from determinaciones.models import Determinacion, PerfilDeterminacion


@login_required
def buscar_determinacion_api(request):
    """API para buscar determinación por código en PostgreSQL"""
    codigo = request.GET.get('codigo', '').strip()
    if not codigo:
        return JsonResponse({'found': False})
    
    try:
        determinacion = Determinacion.objects.filter(codigo=codigo).first()
        if determinacion:
            return JsonResponse({
                'found': True,
                'codigo': determinacion.codigo,
                'nombre': determinacion.nombre
            })
        return JsonResponse({'found': False})
    except Exception as e:
        return JsonResponse({'found': False, 'error': str(e)})


@login_required
def listar_determinaciones_api(request):
    """API para listar todas las determinaciones y perfiles"""
    try:
        items = []
        for det in Determinacion.objects.filter(activa=True).order_by('nombre'):
            items.append({'codigo': det.codigo, 'nombre': det.nombre, 'tipo': 'determinacion'})
        for perf in PerfilDeterminacion.objects.order_by('codigo'):
            items.append({'codigo': perf.codigo, 'nombre': perf.codigo, 'tipo': 'perfil', 'determinaciones': perf.determinaciones})
        return JsonResponse(items, safe=False)
    except Exception:
        return JsonResponse([], safe=False)


@login_required
def buscar_codigo_api(request):
    """API para buscar por código (determinación o perfil)"""
    codigo = request.GET.get('codigo', '').strip()
    if not codigo:
        return JsonResponse({'found': False})
    
    try:
        codigo_sin_prefijo = codigo.lstrip('/')

        perfil = PerfilDeterminacion.objects.filter(codigo=codigo_sin_prefijo).first()
        if perfil:
            return JsonResponse({
                'found': True,
                'tipo': 'perfil',
                'codigo': perfil.codigo,
                'nombre': perfil.codigo,
                'determinaciones': perfil.determinaciones
            })

        determinacion = Determinacion.objects.filter(codigo=codigo_sin_prefijo).first()
        if determinacion:
            return JsonResponse({
                'found': True,
                'tipo': 'determinacion',
                'codigo': determinacion.codigo,
                'nombre': determinacion.nombre
            })

        return JsonResponse({'found': False})
    except Exception as e:
        return JsonResponse({'found': False, 'error': str(e)})


@login_required
def buscar_perfil_api(request):
    """API para obtener detalles de un perfil"""
    codigo = request.GET.get('codigo', '').strip()
    if not codigo:
        return JsonResponse({'found': False})
    
    try:
        perfil = PerfilDeterminacion.objects.filter(codigo=codigo).first()
        if perfil:
            return JsonResponse({
                'found': True,
                'codigo': perfil.codigo,
                'nombre': perfil.codigo,
                'determinaciones': perfil.determinaciones
            })
        return JsonResponse({'found': False})
    except Exception as e:
        return JsonResponse({'found': False, 'error': str(e)})
