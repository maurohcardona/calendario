from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponseBadRequest
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from .models import Cupo, Turno, CapacidadDia
from .forms import TurnoForm
from django.db import IntegrityError
from django.core.exceptions import ValidationError
import json


@login_required
def calendario(request):
    capacidades = CapacidadDia.objects.all()

    eventos = []
    for c in capacidades:
        eventos.append({
            "title": f"{c.capacidad} turnos",
            "start": str(c.fecha),
            "allDay": True
        })

    return render(request, "calendario.html", {"eventos": eventos})



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
        'disponibles': disponibles
    }
    return render(request, 'turnos/dia.html', context)


@login_required
def buscar(request):
    q = request.GET.get('q', '').strip()
    resultados = []
    if q:
        resultados = Turno.objects.filter(dni__icontains=q).order_by('-fecha')
    return render(request, 'turnos/buscar.html', {'resultados': resultados, 'q': q})

