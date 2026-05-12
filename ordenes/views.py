import json

from django.contrib import messages
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView as DjangoLoginView
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from pacientes.models import Paciente

from .forms import CancelarOrdenForm, IngresarOrdenForm, OrdenForm, OrdenProgramadaForm, PacienteInlineForm, VincularTurnoForm
from .mixins import medico_requerido, operador_lab_requerido
from .models import OrdenLaboratorio, Servicio

NOMBRES_GUARDIA_ORDENADOS = [
    "hemograma completo",
    "glucemia",
    "urea",
    "creatinina serica",
    "ionograma serico",
    "hepatograma",
    "coagulograma",
    "sedimento urinario",
    "estado acido base",
    "estado acido base venoso",
    "calcemia",
    "fosfatemia",
    "magnesemia",
    "acido urico serico",
    "ck - creatinkinaza total serica",
    "troponina i de alta sensibilidad",
    "ck-mb - creatinkinaza mb",
    "ldh - lactato deshidrogenasa",
    "procalcitonina",
    "nt probnp",
    "proteina c reactiva",
    "dimero d",
    "acidos biliares",
    "lipasa serica",
    "test de embarazo",
    "test de embarazo en orina",
    "vancomicina",
    "hiv - anticuerpos",
    "hiv - test rapido",
    "bilirrubinemia",
]


def obtener_servicios(request):
    """Vista AJAX que retorna servicios filtrados por origen."""
    origen = request.GET.get("origen", "")
    servicios = Servicio.objects.filter(activo=True)
    if origen:
        servicios = servicios.filter(origen=origen)
    data = [{"id": s.pk, "nombre": s.nombre} for s in servicios]
    return JsonResponse(data, safe=False)


@medico_requerido
def buscar_paciente(request):
    """Vista AJAX que busca un paciente por número de identificación (cross-tipo).

    Busca el número ingresado en todos los tipos de identificación (DNI, NEO, NN, etc.)
    para facilitar la búsqueda sin que el operador deba conocer el tipo previamente.
    """
    iden = request.GET.get("iden", "").strip()
    paciente = Paciente.objects.filter(iden=iden).first()
    if paciente:
        data = {
            "encontrado": True,
            "paciente": {
                "id": paciente.pk,
                "tipo_iden": paciente.tipo_iden,
                "nombre_completo": paciente.nombre_completo,
                "apellido": paciente.apellido,
                "nombre": paciente.nombre,
                "iden": paciente.iden,
                "fecha_nacimiento": str(paciente.fecha_nacimiento) if paciente.fecha_nacimiento else "",
                "sexo": paciente.sexo,
            },
        }
    else:
        data = {"encontrado": False}
    return JsonResponse(data)


@medico_requerido
def crear_orden(request):
    """Vista para crear una nueva orden de laboratorio."""
    paciente = None
    paciente_id = request.POST.get("paciente_id") or request.GET.get("paciente_id")

    if paciente_id:
        paciente = get_object_or_404(Paciente, pk=paciente_id)

    if request.method == "POST":
        orden_form = OrdenForm(request.POST)
        paciente_form = PacienteInlineForm(request.POST)

        if not paciente:
            # Intentar crear el paciente
            if paciente_form.is_valid():
                tipo_iden = paciente_form.cleaned_data.get("tipo_iden") or "DNI"
                iden = paciente_form.cleaned_data.get("iden")

                if tipo_iden == "NEO":
                    # Para NEO el número se genera automáticamente server-side
                    from turnos.services.turno_service import generar_numero_neo_unico
                    iden = generar_numero_neo_unico(
                        nombre=paciente_form.cleaned_data.get("nombre", ""),
                        apellido=paciente_form.cleaned_data.get("apellido", ""),
                        fecha_nacimiento=paciente_form.cleaned_data.get("fecha_nacimiento"),
                    )

                if iden:
                    paciente, _ = Paciente.objects.get_or_create(
                        tipo_iden=tipo_iden,
                        iden=iden,
                        defaults={
                            "apellido": paciente_form.cleaned_data.get("apellido", ""),
                            "nombre": paciente_form.cleaned_data.get("nombre", ""),
                            "fecha_nacimiento": paciente_form.cleaned_data.get("fecha_nacimiento"),
                            "sexo": paciente_form.cleaned_data.get("sexo", ""),
                        },
                    )

        if paciente and orden_form.is_valid():
            orden = orden_form.save(commit=False)
            orden.paciente = paciente
            orden.medico = request.user.medico
            orden.creado_por = request.user
            orden.save()
            orden_form.save_m2m()
            messages.success(request, f"Orden #{orden.pk} creada exitosamente.")
            return redirect("ordenes:detalle_orden", pk=orden.pk)
        elif not paciente:
            messages.error(request, "Debés seleccionar o ingresar un paciente.")
    else:
        orden_form = OrdenForm()
        paciente_form = PacienteInlineForm()

    from determinaciones.models import Determinacion, DeterminacionCompleja, Sector
    guardia_pks_simples = set(
        str(pk) for pk in Determinacion.objects.filter(guardia=True).values_list("pk", flat=True)
    )
    guardia_pks_complejas = set(
        str(pk) for pk in DeterminacionCompleja.objects.filter(guardia=True).values_list("pk", flat=True)
    )

    # Sectores con sus PKs para agrupar en el template
    ORDEN_SECTORES = [
        "hematologia",
        "hemostasia",
        "quimica",
        "enzimas cardiacas",
        "serologia",
        "endocrinologia",
    ]

    sectores_raw = []
    for sector in Sector.objects.all():
        pks_simples = set(
            str(pk) for pk in Determinacion.objects.filter(sector=sector, activa=True, visible=True)
            .values_list("pk", flat=True)
        )
        pks_complejas = set(
            str(pk) for pk in DeterminacionCompleja.objects.filter(sector=sector, activa=True, visible=True)
            .values_list("pk", flat=True)
        )
        sectores_raw.append({
            "nombre": sector.nombre,
            "pks_simples": pks_simples,
            "pks_complejas": pks_complejas,
        })

    def sector_sort_key(s):
        nombre = s["nombre"].lower()
        try:
            return ORDEN_SECTORES.index(nombre)
        except ValueError:
            return len(ORDEN_SECTORES)  # los que no están en la lista van al final

    sectores = sorted(sectores_raw, key=sector_sort_key)
    # Determinaciones sin sector
    pks_sin_sector_simples = set(
        str(pk) for pk in Determinacion.objects.filter(sector__isnull=True, activa=True, visible=True)
        .values_list("pk", flat=True)
    )
    if pks_sin_sector_simples:
        sectores.append({
            "nombre": "Otros",
            "pks_simples": pks_sin_sector_simples,
            "pks_complejas": set(),
        })

    guardia_orden = json.dumps(NOMBRES_GUARDIA_ORDENADOS)

    return render(
        request,
        "ordenes/crear_orden.html",
        {
            "orden_form": orden_form,
            "paciente_form": paciente_form,
            "paciente": paciente,
            "guardia_orden": guardia_orden,
            "guardia_pks_simples": guardia_pks_simples,
            "guardia_pks_complejas": guardia_pks_complejas,
            "sectores": sectores,
        },
    )


@medico_requerido
def crear_orden_programada(request):
    """Vista para crear una nueva orden programada (pacientes internados, fecha futura).

    Tras crear exitosamente una orden, redirige al mismo formulario manteniendo
    servicio y fecha para facilitar la carga de múltiples órdenes consecutivas.
    """
    import datetime

    # Leer parámetros GET para pre-rellenar servicio y fecha en recarga
    servicio_id_get = request.GET.get("servicio_id")
    fecha_get = request.GET.get("fecha_programada")
    es_recarga = bool(servicio_id_get or fecha_get)

    if request.method == "POST":
        orden_form = OrdenProgramadaForm(request.POST)
        paciente_form = PacienteInlineForm(request.POST)

        paciente = None
        paciente_id = request.POST.get("paciente_id")
        if paciente_id:
            from django.shortcuts import get_object_or_404
            paciente = get_object_or_404(Paciente, pk=paciente_id)

        if not paciente:
            if paciente_form.is_valid():
                tipo_iden = paciente_form.cleaned_data.get("tipo_iden") or "DNI"
                iden = paciente_form.cleaned_data.get("iden")

                if tipo_iden == "NEO":
                    # Para NEO el número se genera automáticamente server-side
                    from turnos.services.turno_service import generar_numero_neo_unico
                    iden = generar_numero_neo_unico(
                        nombre=paciente_form.cleaned_data.get("nombre", ""),
                        apellido=paciente_form.cleaned_data.get("apellido", ""),
                        fecha_nacimiento=paciente_form.cleaned_data.get("fecha_nacimiento"),
                    )

                if iden:
                    paciente, _ = Paciente.objects.get_or_create(
                        tipo_iden=tipo_iden,
                        iden=iden,
                        defaults={
                            "apellido": paciente_form.cleaned_data.get("apellido", ""),
                            "nombre": paciente_form.cleaned_data.get("nombre", ""),
                            "fecha_nacimiento": paciente_form.cleaned_data.get("fecha_nacimiento"),
                            "sexo": paciente_form.cleaned_data.get("sexo", ""),
                        },
                    )

        if paciente and orden_form.is_valid():
            orden = orden_form.save(commit=False)
            orden.paciente = paciente
            orden.medico = request.user.medico
            orden.creado_por = request.user
            orden.tipo_origen = "ORDENES_PROGRAMADAS"
            orden.estado = "PENDIENTE"
            orden.save()
            orden_form.save_m2m()
            messages.success(
                request,
                f"✓ Orden {orden.numero_orden_lab} creada correctamente. "
                f"Podés crear otra para el mismo servicio y fecha.",
            )
            # Redirigir manteniendo servicio y fecha para la siguiente orden
            redirect_url = (
                reverse("ordenes:crear_orden_programada")
                + f"?servicio_id={orden.servicio_id}&fecha_programada={orden.fecha_programada}"
            )
            return redirect(redirect_url)
        elif not paciente:
            messages.error(request, "Debés seleccionar o ingresar un paciente.")

    else:
        # GET: inicializar formulario con valores pre-rellenados si corresponde
        initial = {}
        if servicio_id_get:
            initial["servicio"] = servicio_id_get
        if fecha_get:
            initial["fecha_programada"] = fecha_get
        else:
            # Por defecto: mañana
            initial["fecha_programada"] = datetime.date.today() + datetime.timedelta(days=1)

        orden_form = OrdenProgramadaForm(initial=initial)
        paciente_form = PacienteInlineForm()

    # Preparar sectores y determinaciones (igual que crear_orden)
    from determinaciones.models import Determinacion, DeterminacionCompleja, Sector

    guardia_pks_simples = set(
        str(pk) for pk in Determinacion.objects.filter(guardia=True).values_list("pk", flat=True)
    )
    guardia_pks_complejas = set(
        str(pk) for pk in DeterminacionCompleja.objects.filter(guardia=True).values_list("pk", flat=True)
    )

    ORDEN_SECTORES = [
        "hematologia",
        "hemostasia",
        "quimica",
        "enzimas cardiacas",
        "serologia",
        "endocrinologia",
    ]

    sectores_raw = []
    for sector in Sector.objects.all():
        pks_simples = set(
            str(pk) for pk in Determinacion.objects.filter(sector=sector, activa=True, visible=True)
            .values_list("pk", flat=True)
        )
        pks_complejas = set(
            str(pk) for pk in DeterminacionCompleja.objects.filter(sector=sector, activa=True, visible=True)
            .values_list("pk", flat=True)
        )
        sectores_raw.append({
            "nombre": sector.nombre,
            "pks_simples": pks_simples,
            "pks_complejas": pks_complejas,
        })

    def sector_sort_key(s):
        nombre = s["nombre"].lower()
        try:
            return ORDEN_SECTORES.index(nombre)
        except ValueError:
            return len(ORDEN_SECTORES)

    sectores = sorted(sectores_raw, key=sector_sort_key)
    pks_sin_sector_simples = set(
        str(pk) for pk in Determinacion.objects.filter(sector__isnull=True, activa=True, visible=True)
        .values_list("pk", flat=True)
    )
    if pks_sin_sector_simples:
        sectores.append({
            "nombre": "Otros",
            "pks_simples": pks_sin_sector_simples,
            "pks_complejas": set(),
        })

    return render(
        request,
        "ordenes/crear_orden_programada.html",
        {
            "orden_form": orden_form,
            "paciente_form": paciente_form,
            "es_recarga": es_recarga,
            "servicio_id_preseleccionado": servicio_id_get,
            "fecha_preseleccionada": fecha_get,
            "guardia_pks_simples": guardia_pks_simples,
            "guardia_pks_complejas": guardia_pks_complejas,
            "sectores": sectores,
        },
    )


@medico_requerido
@medico_requerido
def mis_ordenes(request):
    """Vista que muestra las órdenes del médico autenticado con paginación de 10 por página."""
    medico = request.user.medico
    ordenes_qs = OrdenLaboratorio.objects.filter(
        medico=medico
    ).select_related("paciente", "medico").order_by("-fecha_creacion")
    paginator = Paginator(ordenes_qs, 10)
    ordenes = paginator.get_page(request.GET.get("page", 1))
    return render(request, "ordenes/mis_ordenes.html", {"ordenes": ordenes})


@medico_requerido
def filtrar_mis_ordenes_ajax(request):
    """Endpoint AJAX: filtra las órdenes del médico autenticado según parámetros GET."""
    medico = request.user.medico
    qs = OrdenLaboratorio.objects.filter(medico=medico).select_related("paciente", "servicio")

    paciente_busqueda = request.GET.get("paciente", "").strip()
    origen = request.GET.get("origen", "").strip()
    estado = request.GET.get("estado", "").strip()
    fecha_desde = request.GET.get("fecha_desde", "").strip()
    fecha_hasta = request.GET.get("fecha_hasta", "").strip()
    tipo_fecha = request.GET.get("tipo_fecha", "creacion")

    if paciente_busqueda:
        qs = qs.filter(
            Q(paciente__iden__icontains=paciente_busqueda)
            | Q(paciente__nombre__icontains=paciente_busqueda)
            | Q(paciente__apellido__icontains=paciente_busqueda)
        )
    if origen:
        qs = qs.filter(tipo_origen=origen)
    if estado:
        qs = qs.filter(estado=estado)

    if tipo_fecha == "programada":
        if fecha_desde:
            qs = qs.filter(fecha_programada__gte=fecha_desde)
        if fecha_hasta:
            qs = qs.filter(fecha_programada__lte=fecha_hasta)
    else:
        if fecha_desde:
            qs = qs.filter(fecha_creacion__date__gte=fecha_desde)
        if fecha_hasta:
            qs = qs.filter(fecha_creacion__date__lte=fecha_hasta)

    qs = qs.order_by("-fecha_creacion")[:100]

    ordenes_data = []
    for orden in qs:
        ordenes_data.append({
            "pk": orden.pk,
            "numero_orden_lab": orden.numero_orden_lab,
            "paciente_nombre": orden.paciente.nombre_completo,
            "paciente_dni": orden.paciente.iden,
            "origen": orden.get_tipo_origen_display(),
            "tipo_origen": orden.tipo_origen,
            "servicio_nombre": orden.servicio.nombre if orden.servicio else None,
            "sala": orden.sala or "",
            "tiene_observaciones": bool(orden.observaciones),
            "observaciones": orden.observaciones,
            "estado": orden.estado,
            "estado_display": orden.get_estado_display(),
            "fecha_creacion": orden.fecha_creacion.strftime("%d/%m/%Y %H:%M"),
            "fecha_programada": orden.fecha_programada.strftime("%d/%m/%Y") if orden.fecha_programada else None,
            "url": reverse("ordenes:detalle_orden", args=[orden.pk]),
        })

    return JsonResponse({"ordenes": ordenes_data, "total": len(ordenes_data)})


@login_required
def detalle_orden(request, pk):
    """Vista que muestra el detalle de una orden de laboratorio."""
    orden = get_object_or_404(
        OrdenLaboratorio.objects.select_related("paciente", "medico", "servicio", "turno"),
        pk=pk,
    )
    es_operador_lab = request.user.is_superuser or request.user.groups.filter(name="laboratorio").exists()
    tiene_medico = hasattr(request.user, "medico") and request.user.medico is not None
    base_template = "base_medico.html" if tiene_medico else "base.html"
    return render(
        request,
        "ordenes/detalle_orden.html",
        {
            "orden": orden,
            "es_operador_lab": es_operador_lab,
            "tiene_medico": tiene_medico,
            "base_template": base_template,
        },
    )


@operador_lab_requerido
def cola_laboratorio(request):
    """Vista que muestra la cola de órdenes pendientes con filtros por origen y fecha programada."""
    hoy = timezone.localtime(timezone.now()).date()

    origen_filtro = request.GET.get("origen", "").strip()
    fecha_programada_filtro = request.GET.get("fecha_programada", "").strip()

    hace_24hs = timezone.now() - timezone.timedelta(hours=24)
    hay_filtros = bool(origen_filtro or fecha_programada_filtro)

    # Sin filtros: solo últimas 24 hs. Con filtros: toda la base.
    qs = OrdenLaboratorio.objects.filter(estado="PENDIENTE")
    if not hay_filtros:
        qs = qs.filter(fecha_creacion__gte=hace_24hs)

    if origen_filtro:
        qs = qs.filter(tipo_origen=origen_filtro)
    if fecha_programada_filtro:
        qs = qs.filter(fecha_programada=fecha_programada_filtro)

    ordenes = qs.select_related("paciente", "medico", "servicio").order_by("fecha_creacion")

    # Agrupar por tipo_origen para la tabla
    grupos = {}
    for orden in ordenes:
        tipo = orden.get_tipo_origen_display()
        if tipo not in grupos:
            grupos[tipo] = []
        grupos[tipo].append(orden)

    # Contar por origen para los badges (misma restricción de 24hs si no hay filtros)
    base_qs = OrdenLaboratorio.objects.filter(estado="PENDIENTE")
    if not hay_filtros:
        base_qs = base_qs.filter(fecha_creacion__gte=hace_24hs)
    if fecha_programada_filtro:
        base_qs = base_qs.filter(fecha_programada=fecha_programada_filtro)

    contadores = {
        "AMBULATORIO": base_qs.filter(tipo_origen="AMBULATORIO").count(),
        "GUARDIA": base_qs.filter(tipo_origen="GUARDIA").count(),
        "INTERNACION": base_qs.filter(tipo_origen="INTERNACION").count(),
        "ORDENES_PROGRAMADAS": base_qs.filter(tipo_origen="ORDENES_PROGRAMADAS").count(),
        "TODOS": base_qs.count(),
    }

    # Servicios para filtro de servicio (solo los que tienen órdenes pendientes)
    servicios = (
        Servicio.objects.filter(ordenlaboratorio__estado="PENDIENTE")
        .distinct()
        .order_by("nombre")
    )

    # Próximos 7 días para el select de fecha programada
    import datetime as dt
    proximos_dias = [hoy + dt.timedelta(days=i) for i in range(8)]

    return render(request, "ordenes/cola_laboratorio.html", {
        "grupos": grupos,
        "hoy": hoy,
        "servicios": servicios,
        "origen_filtro": origen_filtro,
        "fecha_programada_filtro": fecha_programada_filtro,
        "contadores": contadores,
        "total_ordenes": ordenes.count(),
        "proximos_dias": proximos_dias,
        "hay_filtros": hay_filtros,
    })


@operador_lab_requerido
def ingresar_orden(request, pk):
    """Vista para ingresar una orden (cambiar estado a INGRESADA)."""
    orden = get_object_or_404(OrdenLaboratorio, pk=pk)
    if request.method == "POST":
        form = IngresarOrdenForm(request.POST, instance=orden)
        if form.is_valid():
            orden.ingresar(
                observaciones_lab=form.cleaned_data.get("observaciones_lab", ""),
            )
            messages.success(request, f"Orden #{orden.pk} ingresada al laboratorio.")
            return redirect("ordenes:cola_laboratorio")
    else:
        form = IngresarOrdenForm(instance=orden)
    return render(request, "ordenes/ingresar_orden.html", {"orden": orden, "form": form})


@operador_lab_requerido
def vincular_turno(request, pk):
    """Vista para vincular un turno a la orden."""
    orden = get_object_or_404(OrdenLaboratorio, pk=pk)
    if request.method == "POST":
        form = VincularTurnoForm(request.POST, instance=orden)
        if form.is_valid():
            form.save()
            messages.success(request, "Turno vinculado correctamente.")
            return redirect("ordenes:detalle_orden", pk=orden.pk)
    else:
        form = VincularTurnoForm(instance=orden)
    return render(request, "ordenes/vincular_turno.html", {"orden": orden, "form": form})


@operador_lab_requerido
def completar_orden(request, pk):
    """Vista para completar una orden (solo POST)."""
    if request.method == "POST":
        orden = get_object_or_404(OrdenLaboratorio, pk=pk)
        orden.completar()
        messages.success(request, f"Orden #{orden.pk} marcada como completada.")
    return redirect("ordenes:cola_laboratorio")


@operador_lab_requerido
def cancelar_orden(request, pk):
    """Vista para cancelar una orden."""
    orden = get_object_or_404(OrdenLaboratorio, pk=pk)
    if request.method == "POST":
        form = CancelarOrdenForm(request.POST)
        if form.is_valid():
            orden.cancelar(motivo=form.cleaned_data.get("motivo", ""))
            messages.success(request, f"Orden #{orden.pk} cancelada.")
            return redirect("ordenes:cola_laboratorio")
    else:
        form = CancelarOrdenForm()
    return render(request, "ordenes/cancelar_orden.html", {"orden": orden, "form": form})


@login_required
def buscar_orden_pendiente(request):
    """AJAX: busca órdenes PENDIENTES de un paciente por DNI."""
    dni = request.GET.get("dni", "").strip()
    if not dni:
        return JsonResponse({"tiene_orden_pendiente": False, "ordenes": []})

    ordenes = (
        OrdenLaboratorio.objects.filter(paciente__iden=dni, estado="PENDIENTE")
        .select_related("medico", "servicio", "paciente")
        .prefetch_related("determinaciones", "determinaciones_complejas")
        .order_by("-fecha_creacion")
    )

    if not ordenes.exists():
        return JsonResponse({"tiene_orden_pendiente": False, "ordenes": []})

    data = []
    for o in ordenes:
        data.append({
            "pk": o.pk,
            "numero_orden_lab": o.numero_orden_lab,
            "tipo_origen": o.get_tipo_origen_display(),
            "servicio": str(o.servicio) if o.servicio else None,
            "observaciones": o.observaciones,
            "medico": o.medico.nombre if o.medico else "",
            "fecha_creacion": o.fecha_creacion.strftime("%d/%m/%Y %H:%M"),
            "fecha_creacion_raw": o.fecha_creacion.isoformat(),
            "estado": o.estado,
            "determinaciones": [
                {"pk": d.pk, "codigo": d.codigo, "nombre": d.nombre}
                for d in o.determinaciones.all()
            ],
            "determinaciones_complejas": [
                {"pk": d.pk, "codigo": d.codigo, "nombre": d.nombre}
                for d in o.determinaciones_complejas.all()
            ],
        })

    return JsonResponse({"tiene_orden_pendiente": True, "ordenes": data})


@login_required
def buscar_ordenes_global(request):
    """AJAX: busca órdenes por DNI o número de orden en toda la base de datos."""
    q = request.GET.get("q", "").strip()
    if not q:
        return JsonResponse({"ordenes": []})

    ordenes = OrdenLaboratorio.objects.select_related(
        "paciente", "medico", "servicio"
    ).filter(
        Q(paciente__iden__icontains=q) | Q(numero_orden_lab__icontains=q)
    ).order_by("-fecha_creacion")[:20]

    data = []
    for o in ordenes:
        data.append({
            "pk": o.pk,
            "numero_orden_lab": o.numero_orden_lab,
            "paciente": o.paciente.nombre_completo,
            "dni": o.paciente.iden,
            "origen": o.get_tipo_origen_display(),
            "estado": o.estado,
            "estado_display": o.get_estado_display(),
            "fecha": o.fecha_creacion.strftime("%d/%m/%Y %H:%M"),
            "url": f"/ordenes/{o.pk}/",
        })
    return JsonResponse({"ordenes": data})


@medico_requerido
def todas_ordenes(request):
    """Vista con filtros avanzados para buscar todas las órdenes con paginación de 10 por página."""
    qs = OrdenLaboratorio.objects.select_related("paciente", "medico", "servicio").order_by("-fecha_creacion")

    dni = request.GET.get("dni", "").strip()
    servicio_id = request.GET.get("servicio", "").strip()
    fecha_desde = request.GET.get("fecha_desde", "").strip()
    fecha_hasta = request.GET.get("fecha_hasta", "").strip()

    if dni:
        qs = qs.filter(paciente__iden__icontains=dni)
    if servicio_id:
        qs = qs.filter(servicio_id=servicio_id)
    if fecha_desde:
        qs = qs.filter(fecha_creacion__date__gte=fecha_desde)
    if fecha_hasta:
        qs = qs.filter(fecha_creacion__date__lte=fecha_hasta)

    servicios = Servicio.objects.filter(activo=True).order_by("nombre")

    paginator = Paginator(qs, 10)
    ordenes = paginator.get_page(request.GET.get("page", 1))

    return render(request, "ordenes/todas_ordenes.html", {
        "ordenes": ordenes,
        "servicios": servicios,
        "filtros": {
            "dni": dni,
            "servicio": servicio_id,
            "fecha_desde": fecha_desde,
            "fecha_hasta": fecha_hasta,
        },
    })


class MedicoAwareLoginView(DjangoLoginView):
    """
    LoginView que redirige médicos a su interfaz específica post-login.

    - Usuarios con médico asociado → ordenes:mis_ordenes
    - Resto de usuarios → comportamiento default de Django (LOGIN_REDIRECT_URL)
    """

    def get_success_url(self):
        try:
            _ = self.request.user.medico  # Dispara DoesNotExist si no tiene
            return reverse("ordenes:mis_ordenes")
        except Exception:
            return super().get_success_url()
