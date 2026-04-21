"""Vistas de la app instituciones."""

from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import render

from instituciones.models import Institucion
from turnos.models import Turno


@login_required
def estadisticas_instituciones(request):
    """Vista de estadísticas de órdenes por institución en un rango de fechas."""
    hoy = date.today()
    fecha_desde_default = hoy.replace(day=1)  # primer día del mes actual

    fecha_desde_str = request.GET.get("fecha_desde", "")
    fecha_hasta_str = request.GET.get("fecha_hasta", "")
    institucion_id = request.GET.get("institucion", "")

    try:
        fecha_desde = (
            date.fromisoformat(fecha_desde_str)
            if fecha_desde_str
            else fecha_desde_default
        )
    except ValueError:
        fecha_desde = fecha_desde_default

    try:
        fecha_hasta = date.fromisoformat(fecha_hasta_str) if fecha_hasta_str else hoy
    except ValueError:
        fecha_hasta = hoy

    # Queryset base filtrado por rango de fechas
    qs = Turno.objects.filter(fecha__gte=fecha_desde, fecha__lte=fecha_hasta)

    # Filtro opcional por institución específica
    institucion_seleccionada = None
    if institucion_id:
        try:
            institucion_seleccionada = Institucion.objects.get(pk=institucion_id)
            qs = qs.filter(institucion=institucion_seleccionada)
        except Institucion.DoesNotExist:
            pass

    # Totales agrupados por institución
    resultados = (
        qs.values("institucion__id", "institucion__nombre")
        .annotate(total=Count("id"))
        .order_by("-total")
    )

    # Separar turnos sin institución asignada
    sin_institucion = qs.filter(institucion__isnull=True).count()
    total_general = qs.count()

    instituciones = Institucion.objects.filter(activa=True).order_by("nombre")

    context = {
        "resultados": resultados,
        "sin_institucion": sin_institucion,
        "total_general": total_general,
        "fecha_desde": fecha_desde,
        "fecha_hasta": fecha_hasta,
        "instituciones": instituciones,
        "institucion_seleccionada": institucion_seleccionada,
        "institucion_id": institucion_id,
    }
    return render(request, "instituciones/estadisticas.html", context)
