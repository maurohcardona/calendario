from datetime import date, datetime
from typing import List, Dict, Any

from django.http import JsonResponse, HttpRequest, HttpResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.db.models import Count, Q
from django.views.decorators.http import require_http_methods

from determinaciones.models import (
    Determinacion,
    PerfilDeterminacion,
    DeterminacionCompleja,
)
from turnos.models import Turno


@login_required
@require_http_methods(["GET"])
def buscar_determinacion_api(request: HttpRequest) -> JsonResponse:
    """API para buscar determinación por código.

    Args:
        request: HttpRequest con el parámetro 'codigo' en GET

    Returns:
        JsonResponse con los datos de la determinación si se encuentra.
    """
    codigo = request.GET.get("codigo", "").strip().upper()

    if not codigo:
        return JsonResponse({"found": False, "error": "Código no proporcionado"})

    try:
        determinacion = Determinacion.objects.filter(codigo=codigo).first()

        if determinacion:
            return JsonResponse(
                {
                    "found": True,
                    "codigo": determinacion.codigo,
                    "nombre": determinacion.nombre,
                    "tiempo": determinacion.tiempo,
                    "stock": determinacion.stock,
                    "activa": determinacion.activa,
                }
            )

        return JsonResponse({"found": False})

    except Exception as e:
        return JsonResponse(
            {"found": False, "error": f"Error al buscar determinación: {str(e)}"},
            status=500,
        )


@login_required
@require_http_methods(["GET"])
def listar_determinaciones_api(request: HttpRequest) -> JsonResponse:
    """API para listar todas las determinaciones, perfiles y determinaciones complejas.

    Filtra solo las determinaciones activas y visibles para el autocompletado.

    Returns:
        JsonResponse con lista de items disponibles.
    """
    try:
        items: List[Dict[str, Any]] = []

        # Determinaciones simples (solo activas y visibles)
        determinaciones = Determinacion.objects.filter(
            activa=True, visible=True
        ).order_by("nombre")

        for det in determinaciones:
            items.append(
                {
                    "codigo": det.codigo,
                    "nombre": det.nombre,
                    "tipo": "determinacion",
                    "stock": det.stock,
                    "tiempo": det.tiempo,
                }
            )

        # Perfiles de determinación
        perfiles = PerfilDeterminacion.objects.all().order_by("codigo")

        for perf in perfiles:
            items.append(
                {
                    "codigo": perf.codigo,
                    "nombre": perf.nombre,
                    "tipo": "perfil",
                    "determinaciones": perf.determinaciones,
                    "stock": True,  # Los perfiles siempre se consideran disponibles
                }
            )

        # Determinaciones complejas (solo visibles)
        complejas = DeterminacionCompleja.objects.filter(
            visible=True, activa=True
        ).order_by("codigo")

        for compleja in complejas:
            items.append(
                {
                    "codigo": compleja.codigo,
                    "nombre": compleja.nombre,
                    "tipo": "compleja",
                    "determinaciones": compleja.determinaciones,
                    "stock": compleja.stock,
                    "tiempo": compleja.tiempo,
                }
            )

        return JsonResponse(items, safe=False)

    except Exception as e:
        return JsonResponse(
            {"error": f"Error al listar determinaciones: {str(e)}"},
            status=500,
            safe=False,
        )


@login_required
@require_http_methods(["GET"])
def buscar_codigo_api(request: HttpRequest) -> JsonResponse:
    """API para buscar por código en determinaciones, perfiles o complejas.

    Prioridad de búsqueda:
    1. Determinaciones complejas (pueden tener / en el código)
    2. Perfiles de determinación
    3. Determinaciones simples

    Args:
        request: HttpRequest con el parámetro 'codigo' en GET

    Returns:
        JsonResponse con los datos del elemento encontrado.
    """
    codigo = request.GET.get("codigo", "").strip()

    if not codigo:
        return JsonResponse({"found": False, "error": "Código no proporcionado"})

    try:
        # 1. Buscar en determinaciones complejas
        compleja = DeterminacionCompleja.objects.filter(codigo=codigo).first()
        if compleja:
            return JsonResponse(
                {
                    "found": True,
                    "tipo": "compleja",
                    "codigo": compleja.codigo,
                    "nombre": compleja.nombre,
                    "determinaciones": compleja.determinaciones,
                    "stock": compleja.stock,
                    "tiempo": compleja.tiempo,
                }
            )

        # 2. Buscar en perfiles
        perfil = PerfilDeterminacion.objects.filter(codigo=codigo).first()
        if perfil:
            return JsonResponse(
                {
                    "found": True,
                    "tipo": "perfil",
                    "codigo": perfil.codigo,
                    "nombre": perfil.nombre,
                    "determinaciones": perfil.determinaciones,
                }
            )

        # 3. Buscar en determinaciones simples
        determinacion = Determinacion.objects.filter(codigo=codigo).first()
        if determinacion:
            return JsonResponse(
                {
                    "found": True,
                    "tipo": "determinacion",
                    "codigo": determinacion.codigo,
                    "nombre": determinacion.nombre,
                    "stock": determinacion.stock,
                    "tiempo": determinacion.tiempo,
                }
            )

        return JsonResponse({"found": False})

    except Exception as e:
        return JsonResponse(
            {"found": False, "error": f"Error al buscar código: {str(e)}"}, status=500
        )


@login_required
def buscador_determinaciones(request: HttpRequest) -> HttpResponse:
    """
    Vista principal del buscador de determinaciones con búsqueda por código.

    Renderiza una interfaz HTML para buscar información de determinaciones,
    perfiles y determinaciones complejas por código. La vista actúa como
    contenedor para la funcionalidad de búsqueda que se ejecuta mediante
    llamadas AJAX a las APIs del sistema.

    Args:
        request: Objeto HttpRequest (requiere autenticación)

    Returns:
        HttpResponse: Render de 'determinaciones/buscador.html' sin contexto adicional.
        El template contiene el formulario y lógica JavaScript para búsqueda interactiva.

    Note:
        La búsqueda real se realiza mediante AJAX a las APIs:
        - buscar_codigo_api: búsqueda por código específico
        - listar_determinaciones_api: listado completo con autocompletado
    """
    return render(request, "determinaciones/buscador.html")


@login_required
@require_http_methods(["GET"])
def estadisticas_determinacion_api(request: HttpRequest) -> JsonResponse:
    """API para obtener estadísticas de uso de una determinación.

    Calcula cuántas veces se solicitó una determinación en un rango de fechas.

    Args:
        request: HttpRequest con parámetros:
            - codigo: código de la determinación
            - fecha_desde: fecha inicial (opcional, por defecto hoy)
            - fecha_hasta: fecha final (opcional, por defecto fin de año)

    Returns:
        JsonResponse con estadísticas de la determinación.
    """
    codigo = request.GET.get("codigo", "").strip()

    if not codigo:
        return JsonResponse({"error": "Código no proporcionado"}, status=400)

    try:
        # Obtener fechas del rango (por defecto: hoy hasta último día del año)
        hoy = date.today()
        ultimo_dia_anio = date(hoy.year, 12, 31)

        fecha_desde_str = request.GET.get("fecha_desde")
        fecha_hasta_str = request.GET.get("fecha_hasta")

        # Parsear fecha_desde
        if fecha_desde_str:
            try:
                fecha_desde = datetime.strptime(fecha_desde_str, "%Y-%m-%d").date()
            except ValueError:
                fecha_desde = hoy
        else:
            fecha_desde = hoy

        # Parsear fecha_hasta
        if fecha_hasta_str:
            try:
                fecha_hasta = datetime.strptime(fecha_hasta_str, "%Y-%m-%d").date()
            except ValueError:
                fecha_hasta = ultimo_dia_anio
        else:
            fecha_hasta = ultimo_dia_anio

        # Buscar turnos que contengan este código en determinaciones
        turnos = (
            Turno.objects.filter(
                Q(determinaciones__icontains=codigo),
                Q(fecha__gte=fecha_desde),
                Q(fecha__lte=fecha_hasta),
            )
            .values("fecha")
            .annotate(cantidad=Count("id"))
            .order_by("fecha")
        )

        # Calcular totales
        total_turnos = sum(t["cantidad"] for t in turnos)

        # Preparar datos por día
        por_dia = [
            {"fecha": t["fecha"].strftime("%d-%m-%Y"), "cantidad": t["cantidad"]}
            for t in turnos
        ]

        return JsonResponse(
            {
                "success": True,
                "codigo": codigo,
                "total_turnos": total_turnos,
                "por_dia": por_dia,
                "fecha_desde": fecha_desde.strftime("%d-%m-%Y"),
                "fecha_hasta": fecha_hasta.strftime("%d-%m-%Y"),
            }
        )

    except Exception as e:
        return JsonResponse(
            {"error": f"Error al calcular estadísticas: {str(e)}"}, status=500
        )


@login_required
@require_http_methods(["GET"])
def buscar_perfil_api(request: HttpRequest) -> JsonResponse:
    """API para obtener detalles de un perfil de determinación.

    Args:
        request: HttpRequest con el parámetro 'codigo' en GET

    Returns:
        JsonResponse con los datos del perfil.
    """
    codigo = request.GET.get("codigo", "").strip()

    if not codigo:
        return JsonResponse({"found": False, "error": "Código no proporcionado"})

    try:
        perfil = PerfilDeterminacion.objects.filter(codigo=codigo).first()

        if perfil:
            return JsonResponse(
                {
                    "found": True,
                    "codigo": perfil.codigo,
                    "nombre": perfil.nombre,
                    "determinaciones": perfil.determinaciones,
                }
            )

        return JsonResponse({"found": False})

    except Exception as e:
        return JsonResponse(
            {"found": False, "error": f"Error al buscar perfil: {str(e)}"}, status=500
        )
