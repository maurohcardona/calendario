"""
Servicio de monitoreo de archivos PDF generados por Navify.

Usa watchdog para escuchar eventos del filesystem en tiempo real
sobre la carpeta INFORMES_PENDIENTES_DIR.

Formato de nombre de archivo esperado:
    [Origen]_[DNI]_[NPeticion]_[NumeroProtocolo].pdf
    Ejemplo: Ambulatorio_12345678_98765_T001.pdf

Flujo de estados:
    on_created  → estado_informe = 'PENDIENTE'      (Navify creó el PDF)
    on_modified → estado_informe = 'CON_RESULTADOS' (Navify agregó resultados)
    on_moved    → estado_informe = 'FINALIZADO'     (Navify renombró/movió el PDF)

Estrategia de búsqueda:
    El campo NumeroProtocolo del nombre de archivo (partes[3]) se corresponde
    con el campo numero_protocolo_lis en los modelos Coordinados y CoordinadosOrden.
    Si partes[3] no existe, se intenta con partes[2] (NPeticion).
    Se busca primero en Coordinados (turnos), luego en CoordinadosOrden (órdenes).
"""

import logging
from pathlib import Path

from watchdog.events import FileSystemEventHandler

logger = logging.getLogger("informes.pdf_monitor")


def _parsear_nombre_archivo(nombre_archivo: str) -> dict | None:
    """
    Parsea el nombre del archivo PDF según el formato de Navify.

    Args:
        nombre_archivo: Nombre del archivo (sin ruta), ej: Ambulatorio_12345678_98765_T001.pdf

    Returns:
        Dict con claves origen, iden, orden, protocolo — o None si el formato es inválido.
    """
    try:
        nombre_sin_ext = Path(nombre_archivo).stem
        partes = [p.strip() for p in nombre_sin_ext.split("_") if p.strip()]
        origenes_validos = ("Internacion", "Internación", "Guardia", "Ambulatorio")

        if len(partes) < 3:
            return None

        origen = partes[0]
        if origen not in origenes_validos:
            return None

        return {
            "origen": origen,
            "iden": partes[1],
            "orden": partes[2],
            "protocolo": partes[3] if len(partes) > 3 else "",
        }
    except (ValueError, IndexError):
        return None


def _buscar_coordinacion(numero_protocolo: str) -> tuple | None:
    """
    Busca el registro de coordinación por numero_protocolo_lis.

    Busca primero en Coordinados (turnos), luego en CoordinadosOrden (órdenes).

    Args:
        numero_protocolo: Valor de NumeroProtocolo del nombre del archivo.

    Returns:
        Tupla (instancia, tipo) donde tipo es 'turno' u 'orden', o None si no se encuentra.
    """
    # Importación diferida para evitar problemas de inicialización de Django
    from turnos.models import Coordinados
    from ordenes.models import CoordinadosOrden

    if not numero_protocolo:
        return None

    coord = Coordinados.objects.filter(numero_protocolo_lis=numero_protocolo).first()
    if coord:
        return (coord, "turno")

    coord_orden = CoordinadosOrden.objects.filter(numero_protocolo_lis=numero_protocolo).first()
    if coord_orden:
        return (coord_orden, "orden")

    return None


def _buscar_por_nombre_archivo(nombre_archivo: str) -> tuple | None:
    """
    Busca el registro de coordinación por nombre_archivo_pdf.

    Usado para eventos on_modified y on_moved, donde ya se guardó el nombre
    del archivo en el registro al momento de on_created.

    Args:
        nombre_archivo: Nombre del archivo PDF (sin ruta).

    Returns:
        Tupla (instancia, tipo) o None.
    """
    from turnos.models import Coordinados
    from ordenes.models import CoordinadosOrden

    coord = Coordinados.objects.filter(nombre_archivo_pdf=nombre_archivo).first()
    if coord:
        return (coord, "turno")

    coord_orden = CoordinadosOrden.objects.filter(nombre_archivo_pdf=nombre_archivo).first()
    if coord_orden:
        return (coord_orden, "orden")

    return None


class PDFInformeEventHandler(FileSystemEventHandler):
    """
    Manejador de eventos watchdog para archivos PDF de informes de Navify.

    Solo procesa archivos .pdf. Ignora directorios y otros tipos de archivo.
    """

    def on_created(self, event):
        """
        Navify creó un nuevo PDF en la carpeta monitoreada.

        Parsea el nombre del archivo para extraer el numero_protocolo,
        busca el registro de coordinación correspondiente y lo actualiza
        con el nombre del archivo y estado PENDIENTE.
        """
        if event.is_directory or not event.src_path.endswith(".pdf"):
            return

        ruta = Path(event.src_path)
        nombre = ruta.name

        logger.info("PDF creado: %s", nombre)

        datos = _parsear_nombre_archivo(nombre)
        if not datos:
            logger.warning("Nombre de archivo con formato inválido, ignorado: %s", nombre)
            return

        # Buscar por protocolo (partes[3]), con fallback a orden (partes[2])
        resultado = _buscar_coordinacion(datos["protocolo"]) or _buscar_coordinacion(datos["orden"])

        if not resultado:
            logger.warning(
                "No se encontró coordinación para protocolo='%s' / orden='%s' — archivo: %s",
                datos["protocolo"],
                datos["orden"],
                nombre,
            )
            return

        instancia, tipo = resultado
        instancia.nombre_archivo_pdf = nombre
        instancia.estado_informe = "PENDIENTE"
        instancia.ruta_archivo_pdf = str(ruta)
        instancia.save(update_fields=["nombre_archivo_pdf", "estado_informe", "ruta_archivo_pdf"])

        logger.info(
            "Coordinación actualizada a PENDIENTE — tipo=%s id=%d archivo=%s",
            tipo,
            instancia.pk,
            nombre,
        )

    def on_modified(self, event):
        """
        Navify modificó un PDF existente (agregó resultados al archivo).

        Busca el registro por nombre_archivo_pdf y actualiza el estado a CON_RESULTADOS.
        """
        if event.is_directory or not event.src_path.endswith(".pdf"):
            return

        nombre = Path(event.src_path).name

        logger.info("PDF modificado: %s", nombre)

        resultado = _buscar_por_nombre_archivo(nombre)
        if not resultado:
            logger.debug("No hay coordinación registrada para: %s (puede ser on_created previo)", nombre)
            return

        instancia, tipo = resultado

        # Solo avanzar si no está ya en un estado superior
        if instancia.estado_informe == "FINALIZADO":
            return

        instancia.estado_informe = "CON_RESULTADOS"
        instancia.save(update_fields=["estado_informe"])

        logger.info(
            "Coordinación actualizada a CON_RESULTADOS — tipo=%s id=%d archivo=%s",
            tipo,
            instancia.pk,
            nombre,
        )

    def on_moved(self, event):
        """
        Navify renombró o movió un PDF (señal de finalización).

        Busca el registro por el nombre original, actualiza el nombre y
        la ruta con los nuevos valores, y cambia el estado a FINALIZADO.
        """
        if event.is_directory or not event.dest_path.endswith(".pdf"):
            return

        nombre_origen = Path(event.src_path).name
        nombre_destino = Path(event.dest_path).name
        ruta_destino = Path(event.dest_path)

        logger.info("PDF movido/renombrado: %s → %s", nombre_origen, nombre_destino)

        resultado = _buscar_por_nombre_archivo(nombre_origen)
        if not resultado:
            logger.warning(
                "No se encontró coordinación para el archivo origen: %s", nombre_origen
            )
            return

        instancia, tipo = resultado
        instancia.nombre_archivo_pdf = nombre_destino
        instancia.estado_informe = "FINALIZADO"
        instancia.ruta_archivo_pdf = str(ruta_destino)
        instancia.save(update_fields=["nombre_archivo_pdf", "estado_informe", "ruta_archivo_pdf"])

        logger.info(
            "Coordinación actualizada a FINALIZADO — tipo=%s id=%d archivo=%s",
            tipo,
            instancia.pk,
            nombre_destino,
        )
