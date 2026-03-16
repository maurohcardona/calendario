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
            Query string completo con '?' inicial (ej: "?q=texto&page_enviados=2").

    Example:
            >>> query = _query_desde_request(request)
            >>> # "?q=paciente&page_enviados=1&page_pendientes=1&..."
    """
    q = request.POST.get("q", "").strip()
    page_enviados = request.POST.get("page_enviados", "1")
    page_pendientes = request.POST.get("page_pendientes", "1")
    page_sin_email = request.POST.get("page_sin_email", "1")
    page_otros = request.POST.get("page_otros", "1")

    query = urlencode(
        {
            "q": q,
            "page_enviados": page_enviados,
            "page_pendientes": page_pendientes,
            "page_sin_email": page_sin_email,
            "page_otros": page_otros,
        }
    )
    return f"?{query}"


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


@login_required
def listado_informes(request: HttpRequest) -> HttpResponse:
    """
    Vista principal para listar informes PDF organizados por estado.

    Muestra informes divididos en 4 categorías con paginación independiente:
    - Enviados: Informes enviados exitosamente por email
    - Pendientes: Informes listos para procesar y enviar
    - Sin email: Informes de pacientes sin dirección de email
    - Otros orígenes: Informes de otros sistemas o fuentes

    Args:
            request: Objeto HttpRequest con parámetros GET:
                    - q: Término de búsqueda para filtrar por nombre de archivo
                    - page_enviados: Número de página para enviados
                    - page_pendientes: Número de página para pendientes
                    - page_sin_email: Número de página para sin email
                    - page_otros: Número de página para otros orígenes

    Returns:
            HttpResponse con template renderizado que muestra los 4 listados paginados.

    Template:
            informes/listado_pdfs.html

    Context:
            - pdfs_enviados (Page): Página actual de PDFs enviados
            - pdfs_pendientes (Page): Página actual de PDFs pendientes
            - pdfs_sin_email (Page): Página actual de PDFs sin email
            - pdfs_otros (Page): Página actual de PDFs de otros orígenes
            - total_enviados (int): Total de PDFs enviados
            - total_pendientes (int): Total de PDFs pendientes
            - total_sin_email (int): Total de PDFs sin email
            - total_otros (int): Total de PDFs de otros orígenes
            - termino_busqueda (str): Término de búsqueda aplicado
            - page_*_actual (int): Número de página actual para cada categoría

    Example:
            GET /informes/listado/?q=paciente&page_enviados=2
            Muestra página 2 de enviados filtrando por "paciente"
    """
    base_informes = Path(settings.BASE_DIR) / "informes"
    carpeta_enviados = base_informes / "enviados"
    carpeta_pendientes = Path(settings.INFORMES_PENDIENTES_DIR)
    carpeta_sin_email = base_informes / "sin_email"
    carpeta_otros = base_informes / "otros_origenes"
    termino_busqueda = request.GET.get("q", "").strip()
    page_enviados = request.GET.get("page_enviados", "1")
    page_pendientes = request.GET.get("page_pendientes", "1")
    page_sin_email = request.GET.get("page_sin_email", "1")
    page_otros = request.GET.get("page_otros", "1")
    pdfs_por_pagina = 20

    pdfs_enviados = _obtener_pdfs(carpeta_enviados)
    pdfs_pendientes = _obtener_pdfs(carpeta_pendientes)
    pdfs_sin_email = _obtener_pdfs(carpeta_sin_email)
    pdfs_otros = _obtener_pdfs(carpeta_otros)

    if termino_busqueda:
        termino_normalizado = termino_busqueda.lower()
        pdfs_enviados = [
            archivo
            for archivo in pdfs_enviados
            if termino_normalizado in archivo.lower()
        ]
        pdfs_pendientes = [
            archivo
            for archivo in pdfs_pendientes
            if termino_normalizado in archivo.lower()
        ]
        pdfs_sin_email = [
            archivo
            for archivo in pdfs_sin_email
            if termino_normalizado in archivo.lower()
        ]
        pdfs_otros = [
            archivo for archivo in pdfs_otros if termino_normalizado in archivo.lower()
        ]

    total_enviados = len(pdfs_enviados)
    total_pendientes = len(pdfs_pendientes)
    total_sin_email = len(pdfs_sin_email)
    total_otros = len(pdfs_otros)

    pdfs_enviados_page = Paginator(pdfs_enviados, pdfs_por_pagina).get_page(
        page_enviados
    )
    pdfs_pendientes_page = Paginator(pdfs_pendientes, pdfs_por_pagina).get_page(
        page_pendientes
    )
    pdfs_sin_email_page = Paginator(pdfs_sin_email, pdfs_por_pagina).get_page(
        page_sin_email
    )
    pdfs_otros_page = Paginator(pdfs_otros, pdfs_por_pagina).get_page(page_otros)

    context = {
        "pdfs_enviados": pdfs_enviados_page,
        "pdfs_pendientes": pdfs_pendientes_page,
        "pdfs_sin_email": pdfs_sin_email_page,
        "pdfs_otros": pdfs_otros_page,
        "total_enviados": total_enviados,
        "total_pendientes": total_pendientes,
        "total_sin_email": total_sin_email,
        "total_otros": total_otros,
        "termino_busqueda": termino_busqueda,
        "page_enviados_actual": pdfs_enviados_page.number,
        "page_pendientes_actual": pdfs_pendientes_page.number,
        "page_sin_email_actual": pdfs_sin_email_page.number,
        "page_otros_actual": pdfs_otros_page.number,
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
        if estado in ("sin_email", "otros_origenes"):
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
