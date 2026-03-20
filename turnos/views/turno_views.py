"""
Vistas relacionadas con gestión de turnos (CRUD y búsqueda).

Este módulo contiene las vistas principales para el manejo de turnos:
- Vista del día con listado y creación de turnos
- Búsqueda de turnos por múltiples criterios
- Edición de turnos existentes
- Eliminación de turnos
"""

from datetime import date, datetime
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpRequest, HttpResponse
from django.urls import reverse
from django.db import transaction
from django.core.exceptions import ValidationError
from django.contrib import messages
from turnos.models import Turno, Cupo, Agenda, Coordinados, Feriados
from pacientes.models import Paciente
from medicos.models import Medico
from determinaciones.models import (
    Determinacion,
    PerfilDeterminacion,
    DeterminacionCompleja,
)
from turnos.forms import TurnoForm
from turnos.services import DeterminacionService, TurnoService


@login_required
def dia(request: HttpRequest, fecha: str | date) -> HttpResponse:
    """
    Vista principal del día para visualizar y crear turnos en una fecha específica.

    Esta es la vista central del sistema de gestión de turnos. Permite:
    - Ver todos los turnos agrupados por agenda (modo "todas_agendas")
    - Ver turnos de una agenda específica con formulario de creación (modo "agenda_seleccionada")
    - Crear nuevos turnos con validaciones automáticas
    - Verificar disponibilidad y cupos
    - Detectar feriados y bloquear creación de turnos

    Funcionalidades principales:
    1. **Modo Vista Dual:**
       - Sin parámetro 'agenda': muestra todas las agendas con turnos agrupados
       - Con parámetro 'agenda': filtra una agenda específica y muestra formulario

    2. **Cálculo de Disponibilidad:**
       - Calcula capacidad, turnos usados y disponibles usando TurnoService
       - Muestra cupos explícitos si existen en la fecha

    3. **Verificación de Feriados:**
       - Detecta automáticamente si la fecha es feriado
       - Bloquea creación de turnos en feriados
       - Muestra descripción del feriado

    4. **Creación de Turnos (POST):**
       - Valida disponibilidad antes de crear
       - Valida que no sea feriado
       - Crea/actualiza paciente automáticamente
       - Procesa determinaciones (simples, perfiles, complejas)
       - Usa transacciones atómicas para integridad
       - Redirige con parámetro para abrir PDF automáticamente

    5. **Agrupación Inteligente:**
       - En modo "todas_agendas": agrupa turnos coordinados vs no coordinados
       - Incluye agendas con capacidad aunque no tengan turnos
       - Muestra disponibilidad por agenda

    Args:
        request: Objeto HttpRequest con:
            - GET['agenda']: (opcional) ID de agenda para filtrar
            - POST: datos del formulario TurnoForm para crear turno
            - user: usuario autenticado (requerido)
        fecha: Fecha del día a mostrar. Acepta:
            - str en formato 'YYYY-MM-DD' (se convierte a date)
            - date object directamente

    Returns:
        HttpResponse: Render de 'turnos/dia.html' con contexto:
        {
            'fecha': date object de la fecha visualizada,
            'turnos': QuerySet de turnos (todos o filtrados por agenda),
            'turnos_por_agenda': dict (solo en modo todas_agendas) {
                agenda_id: {
                    'agenda': objeto Agenda,
                    'coordinados': lista de turnos coordinados,
                    'no_coordinados': lista de turnos sin coordinar,
                    'capacidad': int total de cupos,
                    'usados': int turnos ocupados,
                    'disponibles': int cupos libres
                }
            },
            'modo_vista': str ('todas_agendas' o 'agenda_seleccionada'),
            'form': instancia de TurnoForm (inicializada o con errores),
            'cupo': objeto Cupo si existe explícito para la agenda,
            'disponibles': int cupos disponibles (solo en modo agenda),
            'agenda_name': str nombre de la agenda seleccionada,
            'show_form': bool si debe mostrar formulario de creación,
            'es_feriado': bool si la fecha es feriado,
            'descripcion_feriado': str descripción del feriado (si aplica)
        }

        En caso de creación exitosa (POST):
        - Redirige a la misma vista con parámetros:
          ?agenda={agenda_id}&turno_creado={turno_id}

    Raises:
        Agenda.DoesNotExist: Capturada internamente, se ignora agenda inválida
        Feriados.DoesNotExist: Capturada internamente, indica que no es feriado
        Cupo.DoesNotExist: Capturada internamente, indica que no hay cupo explícito
        ValidationError: Agregado al formulario y mostrado al usuario en caso de:
            - Intentar crear turno en feriado
            - No hay disponibilidad en la agenda
            - Datos inválidos del paciente
            - Error en procesamiento de determinaciones

    Note:
        - La función maneja dos flujos completamente distintos según el modo de vista
        - En modo "todas_agendas" calcula disponibilidad para TODAS las agendas activas
        - En modo "agenda_seleccionada" solo calcula para la agenda filtrada
        - Los turnos se precargan con select_related('agenda') para optimizar queries
        - La creación de turnos usa transaction.atomic() para garantizar consistencia
        - Si la creación falla, el formulario mantiene los datos ingresados
        - El servicio TurnoService.crear_turno() maneja toda la lógica de negocio:
          * Validación de disponibilidad
          * Creación/actualización de paciente
          * Procesamiento de determinaciones
          * Registro de auditoría
        - Los turnos coordinados se identifican consultando la tabla Coordinados
        - El formulario se pre-inicializa con la agenda del cupo o la agenda seleccionada

    Example:
        # Ver todos los turnos del día 2026-03-20:
        GET /turnos/dia/2026-03-20/

        # Ver turnos de agenda específica (ID 5):
        GET /turnos/dia/2026-03-20/?agenda=5

        # Crear turno (POST):
        POST /turnos/dia/2026-03-20/?agenda=5
        {
            'agenda': 5,
            'dni': '12345678',
            'nombre': 'Juan',
            'apellido': 'Pérez',
            'fecha_nacimiento': '1980-05-15',
            'sexo': 'M',
            'telefono': '1234567890',
            'medico': 'Dr. García',
            'determinaciones': 'HEMOGRAMA, GLUCEMIA'
        }

        # Respuesta exitosa redirige a:
        /turnos/dia/2026-03-20/?agenda=5&turno_creado=123

        # Si es feriado, muestra alerta y bloquea formulario:
        GET /turnos/dia/2026-05-01/  # 1 de Mayo
        → context['es_feriado'] = True
        → context['show_form'] = False
        → context['descripcion_feriado'] = 'Día del Trabajador'
    """
    # Convertir fecha a objeto date si viene como string
    if isinstance(fecha, str):
        fecha = datetime.strptime(fecha, "%Y-%m-%d").date()

    # Verificar si es feriado
    es_feriado = False
    descripcion_feriado = None
    try:
        feriado_obj = Feriados.objects.get(fecha=fecha)
        es_feriado = True
        descripcion_feriado = feriado_obj.descripcion
    except Feriados.DoesNotExist:
        es_feriado = False

    # Obtener turnos y cupos
    turnos_all = Turno.objects.filter(fecha=fecha).select_related("agenda")
    cupos_qs = Cupo.objects.select_related("agenda").filter(fecha=fecha)

    # Determinar modo de vista y agenda seleccionada
    agenda_id = request.GET.get("agenda")
    cupo = None
    disponibles = 0
    agenda_obj = None
    turnos = turnos_all
    modo_vista = "todas_agendas"

    if agenda_id:
        try:
            agenda_obj = Agenda.objects.get(id=agenda_id)
            turnos = turnos_all.filter(agenda__id=agenda_id)
            modo_vista = "agenda_seleccionada"
        except Agenda.DoesNotExist:
            agenda_obj = None

        if agenda_obj:
            # Calcular disponibilidad
            disponibilidad = TurnoService.calcular_disponibilidad_fecha(
                fecha, agenda_obj
            )
            disponibles = disponibilidad["disponibles"]

            # Intentar obtener cupo explícito
            try:
                cupo = cupos_qs.get(agenda=agenda_obj)
            except Cupo.DoesNotExist:
                pass

    # Procesar formulario POST
    if request.method == "POST":
        form = TurnoForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Validar que la fecha no sea feriado
                    if Feriados.objects.filter(fecha=fecha).exists():
                        feriado = Feriados.objects.get(fecha=fecha)
                        form.add_error(
                            None,
                            ValidationError(
                                f"No se pueden asignar turnos en feriados: {feriado.descripcion}"
                            ),
                        )
                    else:
                        # Extraer datos del formulario
                        agenda_form = form.cleaned_data.get("agenda")
                        dni = form.cleaned_data.get("dni")
                        nombre = form.cleaned_data.get("nombre")
                        apellido = form.cleaned_data.get("apellido")
                        fecha_nacimiento = form.cleaned_data.get("fecha_nacimiento")
                        sexo = form.cleaned_data.get("sexo")
                        telefono = form.cleaned_data.get("telefono", "")
                        email = form.cleaned_data.get("email", "")
                        observaciones_paciente = form.cleaned_data.get(
                            "observaciones_paciente", ""
                        )
                        medico_nombre = form.cleaned_data.get("medico", "")
                        nota_interna = form.cleaned_data.get("nota_interna", "")
                        determinaciones = form.cleaned_data.get("determinaciones", "")

                        # Usar el servicio para crear el turno
                        exito, turno_nuevo, mensaje_error = TurnoService.crear_turno(
                            fecha=fecha,
                            agenda=agenda_form,
                            dni=dni,
                            nombre=nombre,
                            apellido=apellido,
                            fecha_nacimiento=fecha_nacimiento,
                            sexo=sexo,
                            telefono=telefono,
                            email=email,
                            observaciones_paciente=observaciones_paciente,
                            medico_nombre=medico_nombre,
                            nota_interna=nota_interna,
                            determinaciones=determinaciones,
                            usuario=request.user,
                        )

                        if exito:
                            # Redirigir con parámetro para abrir PDF
                            return redirect(
                                f"{reverse('turnos:dia', args=[fecha])}?agenda={agenda_form.id}&turno_creado={turno_nuevo.id}"
                            )
                        else:
                            form.add_error(None, ValidationError(mensaje_error))

            except ValidationError as e:
                form.add_error(None, e)
    else:
        initial = {"fecha": fecha}
        if cupo:
            initial["agenda"] = cupo.agenda
        elif agenda_obj:
            initial["agenda"] = agenda_obj
        form = TurnoForm(initial=initial)

    # Agrupar turnos por agenda si estamos viendo todas las agendas
    if modo_vista == "todas_agendas":
        turnos_por_agenda = {}
        agendas_disponibilidad = {}

        # Obtener todas las agendas que tienen capacidad o turnos para esta fecha
        all_agendas = Agenda.objects.all()
        for ag in all_agendas:
            disponibilidad_ag = TurnoService.calcular_disponibilidad_fecha(fecha, ag)

            # Incluir agenda si tiene capacidad O si tiene turnos (para fechas pasadas)
            if disponibilidad_ag["capacidad"] > 0 or disponibilidad_ag["usados"] > 0:
                agendas_disponibilidad[ag.id] = {"agenda": ag, **disponibilidad_ag}

        # Obtener IDs de turnos coordinados para la fecha
        turnos_coordinados_ids = set(
            Coordinados.objects.filter(
                id_turno__in=turnos_all.values_list("id", flat=True)
            ).values_list("id_turno", flat=True)
        )

        # Agrupar turnos por agenda y por coordinación
        for turno in turnos_all:
            if turno.agenda.id not in turnos_por_agenda:
                turnos_por_agenda[turno.agenda.id] = {
                    "agenda": turno.agenda,
                    "coordinados": [],
                    "no_coordinados": [],
                    **agendas_disponibilidad.get(
                        turno.agenda.id, {"capacidad": 0, "usados": 0, "disponibles": 0}
                    ),
                }
            if turno.id in turnos_coordinados_ids:
                turnos_por_agenda[turno.agenda.id]["coordinados"].append(turno)
            else:
                turnos_por_agenda[turno.agenda.id]["no_coordinados"].append(turno)

        # Agregar agendas con disponibilidad pero sin turnos
        for agenda_id, info in agendas_disponibilidad.items():
            if agenda_id not in turnos_por_agenda and info["capacidad"] > 0:
                turnos_por_agenda[agenda_id] = {
                    "agenda": info["agenda"],
                    "coordinados": [],
                    "no_coordinados": [],
                    "capacidad": info["capacidad"],
                    "usados": info["usados"],
                    "disponibles": info["disponibles"],
                }
    else:
        turnos_por_agenda = None

    context = {
        "fecha": fecha,
        "turnos": turnos,
        "turnos_por_agenda": turnos_por_agenda,
        "modo_vista": modo_vista,
        "form": form,
        "cupo": cupo,
        "disponibles": disponibles,
        "agenda_name": agenda_obj.name
        if agenda_obj
        else (cupo.agenda.name if cupo else ""),
        "show_form": (
            disponibles > 0
            and agenda_obj
            and modo_vista == "agenda_seleccionada"
            and not es_feriado
        ),
        "es_feriado": es_feriado,
        "descripcion_feriado": descripcion_feriado,
        "agendas": Agenda.objects.all(),
        "agenda_obj": agenda_obj,
    }
    return render(request, "turnos/dia.html", context)


@login_required
def buscar(request: HttpRequest) -> HttpResponse:
    """
    Búsqueda de turnos por múltiples criterios.

    Permite buscar turnos utilizando diferentes filtros:
    - DNI del paciente (búsqueda parcial)
    - Apellido del paciente (búsqueda parcial case-insensitive)
    - ID de turno (búsqueda exacta)

    Los resultados se separan automáticamente en:
    - Turnos previos (fecha < hoy)
    - Turnos pendientes (fecha >= hoy)

    Además expande las determinaciones mostrando nombres completos
    e indica visualmente si el turno está coordinado.

    Args:
        request: Objeto HttpRequest (requiere autenticación) con parámetros GET:
            - q: DNI del paciente (parcial)
            - turno_id: ID exacto del turno
            - apellido: Apellido del paciente (parcial)

    Returns:
        HttpResponse: Render de buscar.html con contexto:
        {
            "turnos_previos": lista de turnos pasados,
            "turnos_pendientes": lista de turnos futuros/hoy,
            "q": string de búsqueda DNI,
            "turno_id": string de búsqueda ID,
            "apellido": string de búsqueda apellido,
            "hoy": date.today()
        }

    Note:
        Cada turno en los resultados tiene atributos adicionales:
        - esta_coordinado: bool
        - determinaciones_nombres: str con nombres expandidos

    Example:
        GET /buscar/?apellido=García
        Busca todos los turnos de pacientes con apellido García
    """
    q = request.GET.get("q", "").strip()
    turno_id = request.GET.get("turno_id", "").strip()
    apellido = request.GET.get("apellido", "").strip()
    resultados = []
    turnos_previos = []
    turnos_pendientes = []

    if q or turno_id or apellido:
        # Buscar por DNI, apellido o por ID de turno
        if turno_id:
            try:
                turno_id_int = int(turno_id.rstrip(".").strip())
                resultados = Turno.objects.filter(id=turno_id_int).select_related(
                    "dni", "agenda"
                )
            except ValueError:
                resultados = []
        elif apellido:
            resultados = (
                Turno.objects.filter(dni__apellido__icontains=apellido)
                .select_related("dni", "agenda")
                .order_by("-fecha")
            )
        else:
            resultados = (
                Turno.objects.filter(dni__iden__icontains=q)
                .select_related("dni", "agenda")
                .order_by("-fecha")
            )

        hoy = date.today()

        # Obtener IDs de turnos coordinados
        turnos_coordinados_ids = set(
            Coordinados.objects.values_list("id_turno", flat=True)
        )

        # Procesar cada turno
        for turno in resultados:
            turno.esta_coordinado = turno.id in turnos_coordinados_ids

            # Obtener nombres de determinaciones
            if turno.determinaciones:
                nombres = DeterminacionService.obtener_nombres_determinaciones(
                    turno.determinaciones
                )
                turno.determinaciones_nombres = (
                    ", ".join(nombres) if nombres else turno.determinaciones
                )
            else:
                turno.determinaciones_nombres = ""

            # Separar en previos y pendientes
            if turno.fecha < hoy:
                turnos_previos.append(turno)
            else:
                turnos_pendientes.append(turno)

    return render(
        request,
        "turnos/buscar.html",
        {
            "turnos_previos": turnos_previos,
            "turnos_pendientes": turnos_pendientes,
            "q": q,
            "turno_id": turno_id,
            "apellido": apellido,
            "hoy": date.today(),
        },
    )


@login_required
def editar_turno(request: HttpRequest, turno_id: int) -> HttpResponse:
    """
    Edita un turno existente modificando sus datos.

    Permite actualizar todos los campos del turno incluyendo:
    - Agenda y fecha
    - Determinaciones solicitadas
    - Médico solicitante
    - Nota interna
    - Datos de contacto del paciente (teléfono, email, observaciones)

    Utiliza TurnoService para procesar las actualizaciones con validaciones.

    Args:
        request: Objeto HttpRequest (requiere autenticación).
            - GET: Muestra formulario de edición con datos actuales
            - POST: Procesa cambios y actualiza el turno
        turno_id: ID del turno a editar.

    Returns:
        HttpResponse:
            - GET: Render de editar_turno.html con formulario
            - POST exitoso: Redirect a vista del día con filtro de agenda
            - POST con errores: Render con mensaje de error

    Raises:
        Http404: Si el turno_id no existe.

    Note:
        Los cambios se validan a través de TurnoService.actualizar_turno()
        que verifica disponibilidad de cupos y validez de datos.

    Example:
        GET /turnos/123/editar/
        POST /turnos/123/editar/
        → Actualiza turno y redirige a /turnos/dia/2024-03-15/?agenda=1
    """
    turno = get_object_or_404(Turno, id=turno_id)

    # Obtener datos del paciente
    paciente_data = TurnoService.obtener_datos_paciente(turno)

    if request.method == "POST":
        # Usar el servicio para actualizar
        exito, mensaje = TurnoService.actualizar_turno(
            turno=turno,
            agenda_id=request.POST.get("agenda"),
            fecha=request.POST.get("fecha"),
            determinaciones=request.POST.get("determinaciones", ""),
            medico_nombre=request.POST.get("medico", ""),
            nota_interna=request.POST.get("nota_interna", ""),
            telefono=request.POST.get("telefono", ""),
            email=request.POST.get("email", ""),
            observaciones_paciente=request.POST.get("observaciones_paciente", ""),
        )

        if exito:
            return redirect(
                reverse("turnos:dia", args=[turno.fecha]) + f"?agenda={turno.agenda.id}"
            )
        else:
            messages.error(request, mensaje)

    # Obtener todas las agendas
    agendas = Agenda.objects.all()

    context = {
        "turno": turno,
        "paciente": paciente_data,
        "agendas": agendas,
        "es_edicion": True,
    }
    return render(request, "turnos/editar_turno.html", context)


@login_required
def eliminar_turno(request: HttpRequest, turno_id: int) -> HttpResponse:
    """
    Elimina un turno existente con confirmación previa.

    Muestra página de confirmación en GET y ejecuta la eliminación en POST.
    Después de eliminar redirige a la vista del día conservando el filtro
    por agenda.

    Args:
        request: Objeto HttpRequest (requiere autenticación).
            - GET: Muestra página de confirmación
            - POST: Ejecuta eliminación
        turno_id: ID del turno a eliminar.

    Returns:
        HttpResponse:
            - GET: Render de confirmar_eliminar.html
            - POST: Redirect a vista del día con filtro de agenda

    Raises:
        Http404: Si el turno_id no existe.

    Example:
        GET /turnos/123/eliminar/
        POST /turnos/123/eliminar/
        → Elimina turno y redirige a /turnos/dia/2024-03-15/?agenda=1
    """
    turno = get_object_or_404(Turno, id=turno_id)
    fecha = turno.fecha
    agenda_id = turno.agenda.id

    if request.method == "POST":
        turno.delete()
        return redirect(reverse("turnos:dia", args=[fecha]) + f"?agenda={agenda_id}")

    context = {
        "turno": turno,
    }
    return render(request, "turnos/confirmar_eliminar.html", context)
