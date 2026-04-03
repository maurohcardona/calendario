"""
Views para la gestión de informes médicos.

Este módulo contiene las vistas para listar, visualizar y enviar informes
médicos en formato PDF a los pacientes por email.
"""

from pathlib import Path
from typing import List
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Informes
from .services import InformesService


def _obtener_pdfs(carpeta: Path) -> List[str]:
    """
    Obtiene lista de archivos PDF en una carpeta ordenados por fecha.

    Args:
            carpeta: Ruta del directorio a explorar.

    Returns:
            Lista de nombres de archivos PDF ordenados de más reciente a más antiguo.
            Retorna lista vacía si la carpeta no existe o no es un directorio.

    Example:
            >>> pdfs = _obtener_pdfs(Path("/informes/enviados"))
            >>> # ['informe_20230315.pdf', 'informe_20230314.pdf', ...]
    """
    if not carpeta.exists() or not carpeta.is_dir():
        return []

    return sorted(
        [
            archivo.name
            for archivo in carpeta.iterdir()
            if archivo.is_file() and archivo.suffix.lower() == ".pdf"
        ],
        reverse=True,
    )


def _obtener_pdf_por_estado(estado: str, nombre_archivo: str) -> Path:
    """
    Obtiene y valida la ruta de un archivo PDF según su estado.

    Args:
            estado: Estado del informe ('enviados', 'pendientes', 'sin_email', 'otros_origenes').
            nombre_archivo: Nombre del archivo PDF a buscar.

    Returns:
            Ruta absoluta al archivo PDF validado.

    Raises:
            Http404: Si el estado es inválido, el archivo no existe, no es PDF,
                    o se intenta acceder fuera del directorio permitido (path traversal).

    Security:
            Protege contra ataques de path traversal validando que el archivo
            resuelto esté dentro del directorio permitido.

    Example:
            >>> archivo = _obtener_pdf_por_estado("enviados", "informe_123.pdf")
            >>> # Path("/base/informes/enviados/informe_123.pdf")
    """
    if estado not in {"enviados", "pendientes", "sin_email", "otros_origenes"}:
        raise Http404("Estado inválido")

    base_informes = Path(settings.BASE_DIR) / "informes"
    carpeta = (base_informes / estado).resolve()
    archivo = (carpeta / nombre_archivo).resolve()

    try:
        archivo.relative_to(carpeta)
    except ValueError as exc:
        raise Http404("Archivo inválido") from exc

    if (
        not archivo.exists()
        or not archivo.is_file()
        or archivo.suffix.lower() != ".pdf"
    ):
        raise Http404("Archivo no encontrado")

    return archivo


def _query_desde_request(request: HttpRequest) -> str:
    """
    Construye query string para preservar estado de paginación y búsqueda.

    Args:
            request: Objeto HttpRequest con datos POST.

    Returns:
            Query string completo con '?' inicial (ej: "?q=texto&page=2").

    Example:
            >>> query = _query_desde_request(request)
            >>> # "?q=12345678&page=1"
    """
    q = request.POST.get("q", "").strip()
    page = request.POST.get("page", "1")

    params = {}
    if q:
        params["q"] = q
    if page and page != "1":
        params["page"] = page

    if params:
        return f"?{urlencode(params)}"
    return ""


def _redirect_listado(request: HttpRequest) -> HttpResponse:
    """
    Redirige al listado de informes preservando el estado actual.

    Args:
            request: Objeto HttpRequest con datos de paginación/búsqueda.

    Returns:
            HttpResponse de redirección con query string preservado.

    Example:
            >>> return _redirect_listado(request)
            >>> # Redirige a: /informes/listado/?q=texto&page_enviados=2&...
    """
    return redirect(f"{reverse('informes:listado')}{_query_desde_request(request)}")


def _parsear_nombre_pdf(nombre_archivo: str) -> dict | None:
    """
    Parsea el nombre de un archivo PDF para extraer sus componentes.

    Formato esperado: [Origen]_[DNI]_[NumeroOrden]_[NumeroProtocolo].pdf
    El campo NumeroProtocolo (turno) es opcional.

    Args:
        nombre_archivo: Nombre del archivo PDF.

    Returns:
        Dict con keys: origen, dni, numero_orden, numero_protocolo.
        None si el formato es inválido.

    Mapeo con modelo Informes:
        - numero_orden (archivo) → numero_orden (BD) = N° de Petición
        - numero_protocolo (archivo) → numero_protocolo (BD) = Turno
    """
    try:
        nombre_sin_ext = Path(nombre_archivo).stem
        partes = [p.strip() for p in nombre_sin_ext.split("_") if p.strip()]

        if len(partes) < 3:
            return None

        return {
            "origen": partes[0],
            "dni": partes[1],
            "numero_orden": partes[2],
            "numero_protocolo": partes[3] if len(partes) > 3 else "",
        }
    except (ValueError, IndexError):
        return None


def _buscar_pdfs_por_criterio(termino: str) -> List[dict]:
    """
    Busca PDFs por DNI, número de orden o número de protocolo en todas las carpetas.
    La búsqueda es EXACTA (coincidencia completa).

    Args:
        termino: DNI, número de orden o número de protocolo a buscar (búsqueda exacta).

    Returns:
        Lista de dicts con información de cada PDF encontrado:
        - dni: Número de documento
        - numero_orden: Número de orden/petición
        - numero_protocolo: Número de protocolo/turno
        - estado: 'enviados', 'pendientes', 'sin_email'
        - carpeta: Nombre de la carpeta donde está el archivo
        - archivo: Nombre del archivo PDF
        - paciente: Objeto Paciente si existe, None si no
    """
    from pacientes.models import Paciente

    base_informes = Path(settings.BASE_DIR) / "informes"
    carpetas = {
        "pendientes": Path(settings.INFORMES_PENDIENTES_DIR),
        "enviados": base_informes / "enviados",
        "sin_email": base_informes / "sin_email",
    }

    # Prioridad de estados: pendientes primero, luego sin_email, luego enviados
    prioridad_estado = {"pendientes": 0, "sin_email": 1, "enviados": 2}

    resultados = []
    termino_normalizado = termino.strip()

    for carpeta_nombre, carpeta_path in carpetas.items():
        if not carpeta_path.exists() or not carpeta_path.is_dir():
            continue

        for archivo in carpeta_path.iterdir():
            if not archivo.is_file() or archivo.suffix.lower() != ".pdf":
                continue

            datos = _parsear_nombre_pdf(archivo.name)
            if not datos:
                continue

            # Búsqueda EXACTA por DNI, número de orden o número de protocolo
            dni_match = termino_normalizado == datos["dni"]
            numero_orden_match = termino_normalizado == str(datos["numero_orden"])
            numero_protocolo_match = termino_normalizado == datos["numero_protocolo"]

            if dni_match or numero_orden_match or numero_protocolo_match:
                # Buscar paciente por DNI
                paciente = None
                try:
                    paciente = Paciente.objects.get(iden=datos["dni"])
                except Paciente.DoesNotExist:
                    pass

                resultados.append(
                    {
                        "dni": datos["dni"],
                        "numero_orden": datos["numero_orden"],
                        "numero_protocolo": datos["numero_protocolo"],
                        "origen": datos["origen"],
                        "estado": carpeta_nombre,
                        "carpeta": carpeta_nombre,
                        "archivo": archivo.name,
                        "paciente": paciente,
                        "prioridad": prioridad_estado.get(carpeta_nombre, 99),
                    }
                )

    # Ordenar por prioridad (pendientes > sin_email > enviados) y luego por número de orden
    resultados.sort(key=lambda x: (x["prioridad"], x["numero_orden"]))

    return resultados


@login_required
def listado_informes(request: HttpRequest) -> HttpResponse:
    """
    Vista principal para buscar informes PDF por DNI o número de protocolo.

    Permite buscar PDFs en las carpetas pendientes, enviados y sin_email.
    Muestra los resultados como cards con información del informe.

    Args:
        request: Objeto HttpRequest con parámetros GET:
            - q: Término de búsqueda (DNI o número de protocolo)
            - page: Número de página para resultados

    Returns:
        HttpResponse con template renderizado mostrando resultados de búsqueda.

    Template:
        informes/listado_pdfs.html

    Context:
        - resultados (Page): Página actual de resultados de búsqueda
        - total_resultados (int): Total de PDFs encontrados
        - termino_busqueda (str): Término de búsqueda aplicado
        - tiene_busqueda (bool): Indica si hay un término de búsqueda activo

    Example:
        GET /informes/listado/?q=12345678
        Busca PDFs con DNI o protocolo que contenga "12345678"
    """
    termino_busqueda = request.GET.get("q", "").strip()
    page = request.GET.get("page", "1")
    pdfs_por_pagina = 15

    resultados = []
    total_resultados = 0

    if termino_busqueda:
        resultados = _buscar_pdfs_por_criterio(termino_busqueda)
        total_resultados = len(resultados)

    resultados_page = Paginator(resultados, pdfs_por_pagina).get_page(page)

    context = {
        "resultados": resultados_page,
        "total_resultados": total_resultados,
        "termino_busqueda": termino_busqueda,
        "tiene_busqueda": bool(termino_busqueda),
    }
    return render(request, "informes/listado_pdfs.html", context)


@login_required
def ver_pdf(request: HttpRequest, estado: str, nombre_archivo: str) -> FileResponse:
    """
    Muestra un archivo PDF en el navegador.

    Args:
            request: Objeto HttpRequest (requerido para @login_required).
            estado: Estado del informe ('enviados', 'pendientes', 'sin_email', 'otros_origenes').
            nombre_archivo: Nombre del archivo PDF a visualizar.

    Returns:
            FileResponse con el contenido del PDF para visualizar en navegador.

    Raises:
            Http404: Si el estado es inválido o el archivo no existe.

    Security:
            Requiere autenticación (@login_required).
            Valida que el archivo esté en el directorio permitido.

    Example:
            GET /informes/ver/enviados/informe_123.pdf
            Muestra el PDF en el navegador
    """
    archivo = _obtener_pdf_por_estado(estado, nombre_archivo)

    return FileResponse(open(archivo, "rb"), content_type="application/pdf")


@login_required
@require_POST
def enviar_informe(
    request: HttpRequest, estado: str, nombre_archivo: str
) -> HttpResponse:
    """
    Envía o reenvía un informe por email al paciente.

    Comportamiento según el estado:
    - 'pendientes': Procesa y envía el informe por primera vez usando InformesService
    - Otros estados: Busca al paciente y reenvía el informe

    Args:
            request: Objeto HttpRequest con método POST.
            estado: Estado del informe ('enviados', 'pendientes', 'sin_email', 'otros_origenes').
            nombre_archivo: Nombre del archivo PDF a enviar.

    Returns:
            HttpResponse con redirección al listado preservando el estado de paginación.
            Muestra mensaje de éxito o error mediante Django messages framework.

    Raises:
            Http404: Si el estado es inválido o el archivo no existe.

    Side Effects:
            - Crea o actualiza registro en modelo Informes
            - Incrementa contador de intentos_envio
            - Envía email al paciente
            - Mueve archivo a carpeta "enviados" si el envío es exitoso

    Security:
            Requiere autenticación y método POST.

    Example:
            POST /informes/enviar/pendientes/informe_123.pdf
            Procesa y envía el informe por primera vez

            POST /informes/enviar/sin_email/informe_456.pdf
            Reenvía un informe previamente clasificado sin email
    """
    archivo = _obtener_pdf_por_estado(estado, nombre_archivo)
    service = InformesService()

    if estado == "pendientes":
        resultado = service.procesar_archivo(archivo)
        if resultado.get("exito"):
            messages.success(request, f"Informe enviado: {nombre_archivo}")
        else:
            messages.error(
                request,
                f"No se pudo enviar {nombre_archivo}: {resultado.get('error', 'Error desconocido')}",
            )
        return _redirect_listado(request)

    datos = service.parsear_nombre_archivo(nombre_archivo)
    if not datos:
        messages.error(request, f"Formato inválido para reenviar: {nombre_archivo}")
        return _redirect_listado(request)

    paciente = service.buscar_paciente(datos["iden"])
    if not paciente:
        messages.error(
            request,
            f"No se encontró el paciente {datos['iden']} para reenviar {nombre_archivo}",
        )
        return _redirect_listado(request)

    if not paciente.email:
        messages.error(
            request,
            f"El paciente {datos['iden']} no tiene email para reenviar {nombre_archivo}",
        )
        return _redirect_listado(request)

    informe, _ = Informes.objects.get_or_create(
        paciente=paciente,
        numero_orden=datos["orden"],
        numero_protocolo=datos["protocolo"],
        defaults={
            "nombre_archivo": nombre_archivo,
            "email_destino": paciente.email,
            "estado": "PENDIENTE",
        },
    )

    informe.nombre_archivo = nombre_archivo
    informe.email_destino = paciente.email
    informe.intentos_envio += 1

    if service.enviar_email(informe, archivo):
        informe.estado = "ENVIADO"
        informe.fecha_envio = timezone.now()
        informe.mensaje_error = ""
        informe.save()
        if estado != "enviados":
            service.mover_archivo_enviado(archivo)
        messages.success(request, f"Informe reenviado: {nombre_archivo}")
    else:
        informe.estado = "ERROR"
        informe.save()
        messages.error(
            request,
            f"No se pudo reenviar {nombre_archivo}: {informe.mensaje_error or 'Error desconocido'}",
        )

    return _redirect_listado(request)


@require_POST
@login_required
def actualizar_email_paciente(request: HttpRequest, dni: str) -> HttpResponse:
    """
    Actualiza el email de un paciente y mueve sus PDFs de sin_email a pendientes.

    Args:
        request: Objeto HttpRequest con POST data:
            - email: Nuevo email del paciente
            - q: Término de búsqueda para preservar
            - page: Página actual
        dni: DNI del paciente a actualizar.

    Returns:
        HttpResponse redirigiendo al listado con mensaje de éxito o error.
    """
    import logging
    from pacientes.models import Paciente
    from django.core.validators import validate_email
    from django.core.exceptions import ValidationError

    logger = logging.getLogger(__name__)
    nuevo_email = request.POST.get("email", "").strip()

    if not nuevo_email:
        messages.error(request, "Debe ingresar un email válido.")
        return _redirect_listado(request)

    # Validar formato de email
    try:
        validate_email(nuevo_email)
    except ValidationError:
        messages.error(request, f"El email '{nuevo_email}' no tiene un formato válido.")
        return _redirect_listado(request)

    # Buscar paciente
    try:
        paciente = Paciente.objects.get(iden=dni)
    except Paciente.DoesNotExist:
        messages.error(request, f"No se encontró el paciente con DNI {dni}.")
        return _redirect_listado(request)

    # Actualizar email
    paciente.email = nuevo_email
    paciente.save(update_fields=["email"])

    # Mover archivos de sin_email a pendientes
    service = InformesService()
    archivos_movidos, errores = service.mover_pdfs_sin_email_a_pendientes(dni)

    # Logging
    usuario = request.user.username if request.user.is_authenticated else "anónimo"
    logger.info(
        f"Usuario '{usuario}' actualizó email del DNI {dni} a '{nuevo_email}'. "
        f"Archivos movidos a pendientes: {archivos_movidos}"
    )

    # Mensaje de éxito
    if archivos_movidos > 0:
        messages.success(
            request,
            f"Email guardado. {archivos_movidos} PDF(s) movido(s) a pendientes.",
        )
    else:
        messages.success(request, f"Email guardado: {nuevo_email}")

    # Mostrar warnings si hubo errores en algunos archivos
    for error in errores:
        messages.warning(request, error)

    return _redirect_listado(request)
