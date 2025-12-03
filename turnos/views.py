from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponseBadRequest
from django.contrib.auth.decorators import login_required, user_passes_test
from django.urls import reverse
from .models import Cupo, Turno, CapacidadDia
from .forms import TurnoForm, CupoForm
from django.db import IntegrityError, transaction
from django.core.exceptions import ValidationError
import json
from django.contrib import messages
from django.contrib.auth import logout
from django.conf import settings


@login_required
def calendario(request):
    # Mostrar todos los Cupos y también permitir agendar en fechas sin cupo
    cupos = Cupo.objects.all().order_by('fecha')
    
    eventos = []
    for cupo in cupos:
        libres = cupo.disponibles()
        usados = Turno.objects.filter(fecha=cupo.fecha).count()
        
        # Color: verde si hay lugar, rojo si está lleno
        color = "green" if libres > 0 else "red"
        
        eventos.append({
            "title": f"{libres}/{cupo.cantidad_total} libres",
            "start": cupo.fecha.isoformat(),
            "allDay": True,
            "color": color,
            "extendedProps": {
                "fecha": cupo.fecha.isoformat(),
                "disponibles": libres,
                "total": cupo.cantidad_total,
                "usados": usados,
                "has_cupo": True
            }
        })
    
    return render(request, "turnos/calendario.html", {"eventos": eventos})



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
    cupos = Cupo.objects.all()
    for c in cupos:
        libres = c.disponibles()
        eventos.append({
            "title": f"{libres} libres" if libres > 0 else "Completo",
            "start": c.fecha.isoformat(),
            "allDay": True,
            "color": "green" if libres > 0 else "red",
        })
    return JsonResponse(eventos, safe=False)


@login_required
def dia(request, fecha):
    turnos = Turno.objects.filter(fecha=fecha)
    try:
        cupo = Cupo.objects.get(fecha=fecha)
        disponibles = cupo.disponibles()
    except Cupo.DoesNotExist:
        cupo = None
        disponibles = 0

    if request.method == 'POST':
        form = TurnoForm(request.POST)
        if form.is_valid():
            try:
                # Usar transacción y bloqueo del cupo para evitar sobre-reservas concurrentes
                with transaction.atomic():
                    try:
                        cupo_lock = Cupo.objects.select_for_update().get(fecha=fecha)
                    except Cupo.DoesNotExist:
                        form.add_error(None, ValidationError("No hay cupo configurado para esa fecha."))
                        cupo_lock = None

                    if cupo_lock:
                        usados_qs = Turno.objects.filter(fecha=fecha)
                        if usados_qs.count() >= cupo_lock.cantidad_total:
                            form.add_error(None, ValidationError("La fecha está completa."))
                        else:
                            nuevo = form.save(commit=False)
                            nuevo.full_clean()
                            nuevo.save()
                            return redirect(reverse('turnos:dia', args=[fecha]))
            except ValidationError as e:
                form.add_error(None, e)
    else:
        form = TurnoForm(initial={'fecha': fecha})

    context = {
        'fecha': fecha,
        'turnos': turnos,
        'form': form,
        'cupo': cupo,
        'disponibles': disponibles,
        # Mostrar formulario solo si hay cupo y quedan disponibilidades
        'show_form': True if (cupo and disponibles > 0) else False
    }
    return render(request, 'turnos/dia.html', context)


@login_required
def buscar(request):
    q = request.GET.get('q', '').strip()
    resultados = []
    if q:
        resultados = Turno.objects.filter(dni__icontains=q).order_by('-fecha')
    return render(request, 'turnos/buscar.html', {'resultados': resultados, 'q': q})


def logout_view(request):
    """Accept GET and POST. POST logs out the user. GET redirects to login."""
    if request.method == 'POST':
        # No mostrar ningún mensaje al hacer logout (quitar notificación de 'Has cerrado sesión')
        logout(request)
        return redirect(settings.LOGOUT_REDIRECT_URL or '/accounts/login/')
    # For GET requests, just redirect to the login page (avoid 405)
    return redirect(settings.LOGOUT_REDIRECT_URL or '/accounts/login/')

