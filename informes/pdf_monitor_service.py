"""
Servicio de monitoreo de archivos PDF generados por Navify.

Usa watchdog para escuchar eventos del filesystem en tiempo real
sobre la carpeta INFORMES_PENDIENTES_DIR.

Formato de nombre de archivo esperado:
    [Origen]_[DNI]_[NPeticion]_[NumeroProtocolo].pdf
    Ejemplo: Ambulatorio_12345678_98765_T3894.pdf

Flujo de estados:
    on_created  → estado_informe = 'PENDIENTE'      (Navify creó el PDF)
    on_modified → estado_informe = 'CON_RESULTADOS' (Navify agregó resultados)
    on_moved    → estado_informe = 'FINALIZADO'     (Navify renombró/movió el PDF)

Estrategia de búsqueda:
    El campo NumeroProtocolo del nombre de archivo (partes[3]) es el identificador
    que nuestro sistema envió a Navify en el ORC-2 del mensaje HL7 OML^O21:
        T{turno_id}   → Coordinados (turno ambulatorio)
        OR{orden_pk}  → CoordinadosOrden (orden directa: guardia, internación, programada)

    Se resuelve directamente el ID sin depender del campo numero_protocolo_lis,
    que se poblaba únicamente al recibir el ORU^R01. El valor de partes[3]
    se guarda en numero_protocolo_lis al procesar el PDF.
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


def _buscar_coordinacion(protocolo: str) -> tuple | None:
    """
    Resuelve el protocolo del nombre de archivo al registro de coordinación.

    El protocolo (partes[3]) es el identificador generado por nuestro sistema
    y enviado al LIS en el ORC-2 del OML^O21:
        T{turno_id}  → busca en Coordinados por id_turno
        OR{orden_pk} → busca en CoordinadosOrden por orden_id (más reciente)

    No depende del campo numero_protocolo_lis (que requería recibir el ORU).

    Args:
        protocolo: Valor de partes[3] del nombre del archivo, e.g. 'T3894' o 'OR4'.

    Returns:
        Tupla (instancia, tipo) donde tipo es 'turno' u 'orden', o None si no se encuentra.
    """
    from turnos.models import Coordinados
    from ordenes.models import CoordinadosOrden

    if not protocolo:
        return None

    # Turno ambulatorio: T{turno_id}
    if protocolo.startswith("T"):
        try:
            turno_id = int(protocolo[1:])
        except ValueError:
            logger.warning("Protocolo con formato inesperado (esperado T<int>): %s", protocolo)
            return None
        coord = Coordinados.objects.filter(id_turno=turno_id).first()
        return (coord, "turno") if coord else None

    # Orden directa (guardia, internación, programada): OR{orden_pk}
    if protocolo.startswith("OR"):
        try:
            orden_pk = int(protocolo[2:])
        except ValueError:
            logger.warning("Protocolo con formato inesperado (esperado OR<int>): %s", protocolo)
            return None
        coord = (
            CoordinadosOrden.objects
            .filter(orden_id=orden_pk)
            .order_by("-fecha_coordinacion")
            .first()
        )
        return (coord, "orden") if coord else None

    logger.warning("Protocolo con prefijo desconocido (esperado T... o OR...): %s", protocolo)
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

        # Buscar por protocolo (partes[3]): T{turno_id} o OR{orden_pk}
        resultado = _buscar_coordinacion(datos["protocolo"])

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
        instancia.numero_protocolo_lis = datos["orden"]  # número de orden (partes[2] del nombre del PDF)
        instancia.save(update_fields=[
            "nombre_archivo_pdf",
            "estado_informe",
            "ruta_archivo_pdf",
            "numero_protocolo_lis",
        ])

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
