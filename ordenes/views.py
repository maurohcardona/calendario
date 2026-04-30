import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from pacientes.models import Paciente

from .forms import CancelarOrdenForm, IngresarOrdenForm, OrdenForm, PacienteInlineForm, VincularTurnoForm
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
    """Vista AJAX que busca un paciente por DNI."""
    dni = request.GET.get("iden", "").strip()
    try:
        paciente = Paciente.objects.get(iden=dni)
        data = {
            "encontrado": True,
            "paciente": {
                "id": paciente.pk,
                "nombre_completo": paciente.nombre_completo,
                "apellido": paciente.apellido,
                "nombre": paciente.nombre,
                "iden": paciente.iden,
                "fecha_nacimiento": str(paciente.fecha_nacimiento) if paciente.fecha_nacimiento else "",
                "sexo": paciente.sexo,
            },
        }
    except Paciente.DoesNotExist:
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
                iden = paciente_form.cleaned_data.get("iden")
                if iden:
                    paciente, _ = Paciente.objects.get_or_create(
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
def mis_ordenes(request):
    """Vista que muestra todas las órdenes de laboratorio."""
    ordenes = OrdenLaboratorio.objects.select_related("paciente", "medico").order_by("-fecha_creacion")
    return render(request, "ordenes/mis_ordenes.html", {"ordenes": ordenes})


@login_required
def detalle_orden(request, pk):
    """Vista que muestra el detalle de una orden de laboratorio."""
    orden = get_object_or_404(OrdenLaboratorio, pk=pk)
    es_operador_lab = request.user.is_superuser or request.user.groups.filter(name="laboratorio").exists()
    return render(
        request,
        "ordenes/detalle_orden.html",
        {"orden": orden, "es_operador_lab": es_operador_lab},
    )


@operador_lab_requerido
def cola_laboratorio(request):
    """Vista que muestra la cola de órdenes pendientes del día."""
    hoy = timezone.localtime(timezone.now()).date()
    ordenes = OrdenLaboratorio.objects.filter(
        estado="PENDIENTE",
        fecha_creacion__date=hoy,
    ).select_related("paciente", "medico", "servicio").order_by("fecha_creacion")

    # Agrupar por tipo_origen
    grupos = {}
    for orden in ordenes:
        tipo = orden.get_tipo_origen_display()
        if tipo not in grupos:
            grupos[tipo] = []
        grupos[tipo].append(orden)

    # Servicios con órdenes hoy para el filtro
    servicios = (
        Servicio.objects.filter(ordenlaboratorio__estado="PENDIENTE", ordenlaboratorio__fecha_creacion__date=hoy)
        .distinct()
        .order_by("nombre")
    )

    return render(request, "ordenes/cola_laboratorio.html", {
        "grupos": grupos,
        "hoy": hoy,
        "servicios": servicios,
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


@login_required
def todas_ordenes(request):
    """Vista con filtros avanzados para buscar todas las órdenes."""
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

    return render(request, "ordenes/todas_ordenes.html", {
        "ordenes": qs[:200],
        "servicios": servicios,
        "filtros": {
            "dni": dni,
            "servicio": servicio_id,
            "fecha_desde": fecha_desde,
            "fecha_hasta": fecha_hasta,
        },
    })
