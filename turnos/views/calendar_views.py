"""
Vistas relacionadas con el calendario y gestión de cupos.

Este módulo contiene las vistas para visualizar y gestionar el calendario de turnos,
incluyendo cupos, feriados y disponibilidad de agendas.
"""

from datetime import date, timedelta, datetime
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import redirect, render
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.urls import reverse
from django.contrib import messages
from django.db import transaction
from turnos.models import Cupo, Turno, Agenda, Feriados
from turnos.forms import CupoForm


def lighten_color(color_hex: str, factor: float = 0.6) -> str:
    """
    Aclara un color hexadecimal.

    Args:
        color_hex: Color en formato hexadecimal (#RRGGBB)
        factor: Factor de aclarado (0.0 = original, 1.0 = blanco)

    Returns:
        Color aclarado en formato hexadecimal
    """
    if not color_hex or not color_hex.startswith("#"):
        return color_hex

    color_hex = color_hex.lstrip("#")
    try:
        r = int(color_hex[0:2], 16)
        g = int(color_hex[2:4], 16)
        b = int(color_hex[4:6], 16)

        r = int(r + (255 - r) * factor)
        g = int(g + (255 - g) * factor)
        b = int(b + (255 - b) * factor)

        return f"#{r:02x}{g:02x}{b:02x}"
    except:
        return color_hex


@login_required
def calendario(request: HttpRequest) -> HttpResponse:
    """
    Vista principal del calendario de turnos y cupos.

    Genera y muestra el calendario completo con:
    - Feriados (marcados con 🚫)
    - Cupos explícitos creados manualmente
    - Cupos calculados automáticamente según disponibilidad de agendas
    - Indicadores de disponibilidad (libres/total)
    - Colores según estado (completo, disponible, pasado)

    Proyecta 60 días hacia el futuro mostrando disponibilidad calculada
    para agendas que no tienen cupos explícitos.

    Args:
        request: Objeto HttpRequest (requiere autenticación).

    Returns:
        HttpResponse: Render de calendario.html con eventos y agendas.

    Example:
        GET /calendario/
        Muestra el calendario interactivo con todos los cupos y feriados
    """
    eventos = []
    hoy = date.today()

    # Obtener feriados
    feriados_dict = {}
    try:
        for feriado in Feriados.objects.all():
            feriados_dict[feriado.fecha] = feriado.descripcion
    except Exception as e:
        print(f"Error al cargar feriados: {e}")

    # Agregar eventos de feriados al calendario
    for fecha_fer, descripcion in feriados_dict.items():
        eventos.append(
            {
                "title": f"🚫 {descripcion}",
                "start": fecha_fer.isoformat(),
                "allDay": True,
                "color": "#9e9e9e",
                "textColor": "#ffffff",
                "extendedProps": {"es_feriado": True, "descripcion": descripcion},
            }
        )

    # Eventos por Cupo explícito
    cupos = Cupo.objects.select_related("agenda").all().order_by("fecha")
    for cupo in cupos:
        if cupo.fecha in feriados_dict:
            continue

        libres = cupo.disponibles()
        usados = Turno.objects.filter(fecha=cupo.fecha, agenda=cupo.agenda).count()
        es_pasado = cupo.fecha < hoy

        # Determinar color y título según disponibilidad
        if libres == 0:
            color_claro = "#ff4444"
            titulo = f"{cupo.agenda.name}: Completo"
            texto_tachado = True
        else:
            color_original = cupo.agenda.color if cupo.agenda.color else "#4caf50"
            color_claro = lighten_color(color_original)
            titulo = f"{cupo.agenda.name}: {libres}/{cupo.cantidad_total}"
            texto_tachado = False

        eventos.append(
            {
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
                    "texto_tachado": texto_tachado,
                },
            }
        )

    # Generar eventos calculados para los próximos días según WeeklyAvailability
    horizon_days = 60
    today = date.today()
    agendas = Agenda.objects.all()

    for delta in range(horizon_days):
        d = today + timedelta(days=delta)

        if d in feriados_dict:
            continue

        for ag in agendas:
            # Saltar si ya existe un Cupo explícito
            if Cupo.objects.filter(agenda=ag, fecha=d).exists():
                continue

            capacidad = ag.get_capacity_for_date(d)
            if capacidad <= 0:
                continue

            usados = Turno.objects.filter(fecha=d, agenda=ag).count()
            libres = max(capacidad - usados, 0)
            es_pasado = d < hoy

            # Determinar color y título
            if libres == 0:
                color_claro = "#ff4444"
                titulo = f"{ag.name}: Completo"
                texto_tachado = True
            else:
                color_original = ag.color if ag.color else "#4caf50"
                color_claro = lighten_color(color_original)
                titulo = f"{ag.name}: {libres}/{capacidad}"
                texto_tachado = False

            eventos.append(
                {
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
                        "texto_tachado": texto_tachado,
                    },
                }
            )

    agendas = Agenda.objects.all()
    return render(
        request, "turnos/calendario.html", {"eventos": eventos, "agendas": agendas}
    )


@user_passes_test(lambda u: u.is_superuser)
def nuevo_cupo(request: HttpRequest) -> HttpResponse:
    """
    Vista para crear un cupo manual en el calendario.

    Permite a superusuarios crear cupos específicos para fechas y agendas
    determinadas, sobrescribiendo la disponibilidad automática calculada.

    Args:
        request: Objeto HttpRequest (requiere superusuario).
            - GET: Muestra formulario vacío
            - POST: Procesa y guarda el nuevo cupo

    Returns:
        HttpResponse:
            - GET: Render de cupo_form.html con formulario
            - POST exitoso: Redirección al calendario
            - POST con errores: Render de cupo_form.html con errores

    Example:
        GET /cupos/nuevo/
        Muestra formulario para crear cupo manual
    """
    if request.method == "POST":
        form = CupoForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect(reverse("turnos:calendario"))
    else:
        form = CupoForm()
    return render(request, "turnos/cupo_form.html", {"form": form})


@user_passes_test(lambda u: u.is_superuser)
def generar_cupos_masivo(request: HttpRequest) -> HttpResponse:
    """
    Vista para crear cupos de forma masiva en un rango de fechas.

    Permite a superusuarios generar múltiples cupos automáticamente para una
    agenda específica en un rango de fechas. Soporta:
    - Creación masiva en rango de fechas (excluye fines de semana)
    - Filtro opcional por día de la semana
    - Actualización de cupos existentes
    - Validaciones de fechas y cantidades

    Args:
        request: Objeto HttpRequest (requiere superusuario).
            - GET: Muestra formulario de generación masiva
            - POST: Procesa y genera los cupos según parámetros:
                - agenda: ID de la agenda
                - desde_fecha: Fecha inicio (YYYY-MM-DD)
                - hasta_fecha: Fecha fin (YYYY-MM-DD)
                - cantidad: Cantidad de turnos por cupo
                - por_dia_semana: Boolean para filtrar por día
                - dia_semana: Día de la semana (0=lunes, ..., 6=domingo)

    Returns:
        HttpResponse:
            - Render de generar_cupos.html con formulario y mensajes
            - Redirección a sí mismo tras generar cupos exitosamente

    Example:
        POST /cupos/generar-masivo/
        Genera cupos del 1 al 31 de marzo para agenda específica
    """
    agendas = Agenda.objects.all()

    if request.method == "POST":
        try:
            agenda_id = request.POST.get("agenda")
            desde_fecha = request.POST.get("desde_fecha")
            hasta_fecha = request.POST.get("hasta_fecha")
            cantidad = request.POST.get("cantidad")
            por_dia_semana = request.POST.get("por_dia_semana") == "on"
            dia_semana = request.POST.get("dia_semana")

            # Validaciones
            if not all([agenda_id, desde_fecha, hasta_fecha, cantidad]):
                messages.error(
                    request, "Todos los campos obligatorios deben estar completos."
                )
                return render(
                    request, "turnos/generar_cupos.html", {"agendas": agendas}
                )

            agenda = Agenda.objects.get(id=agenda_id)
            desde = datetime.strptime(desde_fecha, "%Y-%m-%d").date()
            hasta = datetime.strptime(hasta_fecha, "%Y-%m-%d").date()
            cantidad_int = int(cantidad)

            if desde > hasta:
                messages.error(
                    request, "La fecha 'Desde' no puede ser posterior a 'Hasta'."
                )
                return render(
                    request, "turnos/generar_cupos.html", {"agendas": agendas}
                )

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
                    defaults={
                        "cantidad_total": cantidad_int,
                        "usuario": request.user.username,
                    },
                )

                if created:
                    cupos_creados += 1
                else:
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
                messages.warning(
                    request,
                    "No se generaron cupos. Verifica el rango de fechas y el día seleccionado.",
                )

            return redirect("turnos:generar_cupos_masivo")

        except Agenda.DoesNotExist:
            messages.error(request, "La agenda seleccionada no existe.")
        except ValueError as e:
            messages.error(request, f"Error en los datos ingresados: {str(e)}")
        except Exception as e:
            messages.error(request, f"Error inesperado: {str(e)}")

    return render(request, "turnos/generar_cupos.html", {"agendas": agendas})


@user_passes_test(lambda u: u.is_superuser)
def borrar_cupos_masivo(request: HttpRequest) -> HttpResponse:
    """
    Vista para eliminar o reducir cupos de forma masiva.

    Permite a superusuarios eliminar o reducir la cantidad de cupos en un
    rango de fechas. IMPORTANTE: Los turnos ya agendados NO se eliminan.

    Soporta dos modos:
    - Eliminación total de cupos (sin cantidad_a_borrar)
    - Reducción parcial de cantidad (con cantidad_a_borrar)

    Args:
        request: Objeto HttpRequest (requiere superusuario).
            - POST: Procesa eliminación/reducción con parámetros:
                - agenda: ID de la agenda
                - desde_fecha: Fecha inicio (YYYY-MM-DD)
                - hasta_fecha: Fecha fin (YYYY-MM-DD)
                - por_dia_semana: Boolean para filtrar por día
                - dia_semana: Día de la semana (0-6)
                - cantidad_a_borrar: Cantidad a reducir (opcional)

    Returns:
        HttpResponse: Redirección a generar_cupos_masivo con mensajes
        de confirmación o error.

    Warning:
        Los cupos se eliminan pero los turnos agendados se mantienen intactos.
        Si un cupo tiene turnos, esos turnos permanecerán incluso sin cupo.

    Example:
        POST /cupos/borrar-masivo/
        Elimina cupos de marzo sin afectar turnos ya creados
    """
    if request.method == "POST":
        try:
            agenda_id = request.POST.get("agenda")
            desde_fecha = request.POST.get("desde_fecha")
            hasta_fecha = request.POST.get("hasta_fecha")
            por_dia_semana = request.POST.get("por_dia_semana") == "on"
            dia_semana = request.POST.get("dia_semana")
            cantidad_a_borrar = request.POST.get("cantidad_a_borrar")

            cantidad_a_borrar = int(cantidad_a_borrar) if cantidad_a_borrar else None

            # Validaciones
            if not all([agenda_id, desde_fecha, hasta_fecha]):
                messages.error(
                    request, "Todos los campos obligatorios deben estar completos."
                )
                return redirect("turnos:generar_cupos_masivo")

            agenda = Agenda.objects.get(id=agenda_id)
            desde = datetime.strptime(desde_fecha, "%Y-%m-%d").date()
            hasta = datetime.strptime(hasta_fecha, "%Y-%m-%d").date()

            if desde > hasta:
                messages.error(
                    request, "La fecha 'Desde' no puede ser posterior a 'Hasta'."
                )
                return redirect("turnos:generar_cupos_masivo")

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
                            agenda=agenda, fecha=fecha_actual
                        )

                        if cantidad_a_borrar:
                            # Reducir cantidad
                            nueva_cantidad = max(
                                cupo.cantidad_total - cantidad_a_borrar, 0
                            )
                            if nueva_cantidad == 0:
                                cupo.delete()
                                cupos_eliminados += 1
                            else:
                                cupo.cantidad_total = nueva_cantidad
                                cupo.save()
                                cupos_reducidos += 1
                        else:
                            # Eliminar completamente
                            cupo.delete()
                            cupos_eliminados += 1

                except Cupo.DoesNotExist:
                    pass

                fecha_actual += timedelta(days=1)

            if cupos_eliminados > 0 or cupos_reducidos > 0:
                mensaje = []
                if cupos_eliminados > 0:
                    mensaje.append(f"{cupos_eliminados} cupos eliminados")
                if cupos_reducidos > 0:
                    mensaje.append(f"{cupos_reducidos} cupos reducidos")
                messages.success(
                    request,
                    f"✅ {' y '.join(mensaje)} para {agenda.name}. Los turnos agendados se mantienen.",
                )
            else:
                messages.warning(
                    request,
                    "No se encontraron cupos para modificar en el rango especificado.",
                )

            return redirect("turnos:generar_cupos_masivo")

        except Agenda.DoesNotExist:
            messages.error(request, "La agenda seleccionada no existe.")
        except ValueError as e:
            messages.error(request, f"Error en los datos ingresados: {str(e)}")
        except Exception as e:
            messages.error(request, f"Error inesperado: {str(e)}")

    return redirect("turnos:generar_cupos_masivo")
