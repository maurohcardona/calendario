"""
Servicio para parsing de mensajes HL7 entrantes.

Soporta:
  - ACK^O21: Confirmación de orden recibida del LIS
  - ORU^R01: Resultado de laboratorio (parseo básico, expansión futura)

Los mensajes HL7 usan \\r (CR, 0x0D) como separador de segmentos.
"""

import os
import logging
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional

from django.conf import settings

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Data classes de resultado
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class ResultadoACK:
    """
    Resultado del parsing de un mensaje ACK^O21.

    Atributos:
        estado:        Código MSA-1 → AA (Accepted), AE (Application Error), AR (Rejected)
        turno_id:      Placer Order Number extraído de MSA-2 (Message Control ID)
        mensaje:       Texto libre de MSA-3 (Text Message)
        timestamp:     Fecha/hora del mensaje (MSH-7)
        valido:        True si el mensaje se parseó correctamente
        error_parsing: Descripción del error si valido=False
    """
    estado: str = ""
    turno_id: str = ""
    mensaje: str = ""
    timestamp: Optional[datetime] = None
    valido: bool = False
    error_parsing: str = ""

    @property
    def aceptado(self) -> bool:
        """True si el LIS aceptó la orden.

        Navify usa enhanced acknowledgment mode y responde CA (Commit Accept)
        en lugar del AA (Application Accept) del modo original.
        Ambos son respuestas de aceptación válidas.
        """
        return self.estado in ("AA", "CA")

    @property
    def rechazado(self) -> bool:
        """True si el LIS rechazó la orden (AE / AR / CE / CR)."""
        return self.estado in ("AE", "AR", "CE", "CR")


@dataclass
class Observacion:
    """Una observación/resultado dentro de un ORU^R01 (segmento OBX)."""
    set_id: str = ""
    codigo: str = ""
    descripcion: str = ""
    valor: str = ""
    unidades: str = ""
    rango_referencia: str = ""
    estado: str = ""        # F=Final, P=Preliminary, C=Correction


@dataclass
class ResultadoORU:
    """
    Resultado del parsing de un mensaje ORU^R01.

    Atributos:
        turno_id:       Placer Order Number del OBR
        dni_paciente:   DNI extraído de PID-3
        nombre_paciente: Nombre del paciente de PID-5
        observaciones:  Lista de Observacion (segmentos OBX)
        timestamp:      Fecha/hora del mensaje
        valido:         True si el mensaje se parseó correctamente
        error_parsing:  Descripción del error si valido=False
    """
    turno_id: str = ""
    dni_paciente: str = ""
    nombre_paciente: str = ""
    observaciones: list[Observacion] = field(default_factory=list)
    timestamp: Optional[datetime] = None
    valido: bool = False
    error_parsing: str = ""


@dataclass
class ResultadoORL:
    """Resultado del parsing de un mensaje ORL^O22 (Laboratory Order Response)."""
    valido: bool
    turno_id: str
    orden_estado: str        # ORC-1: UA/IP/CM/SC
    orden_estado_desc: str   # Descripción legible del estado
    mensaje_control_id: str  # MSH-10 del ORL (para construir ACK)
    error_parsing: str


# ──────────────────────────────────────────────────────────────────────────────
# Parser principal
# ──────────────────────────────────────────────────────────────────────────────


class HL7Parser:
    """
    Parser de mensajes HL7 entrantes.

    Implementa parsing manual (sin hl7apy) para mayor resiliencia ante
    mensajes malformados del LIS — los ACK y ORU que vienen del LIS real
    pueden tener campos extra o estar levemente fuera de spec.

    Uso:
        resultado = HL7Parser.parsear_ack(raw_str)
        if resultado.aceptado:
            ...

        resultado = HL7Parser.parsear_oru(raw_str)
        for obs in resultado.observaciones:
            print(obs.codigo, obs.valor)
    """

    # ──────────────────────────────────────────────────────────────────────────
    # Métodos públicos
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def parsear_ack(raw: str) -> ResultadoACK:
        """
        Parsea un mensaje ACK^O21.

        Segmentos esperados:
          MSH|...|ACK^O21^...|...|
          MSA|AA|MSG_CONTROL_ID|Texto opcional

        Args:
            raw: Mensaje HL7 crudo en formato ER7

        Returns:
            ResultadoACK con los campos extraídos
        """
        resultado = ResultadoACK()
        try:
            segmentos = HL7Parser._segmentar(raw)
            if not segmentos:
                resultado.error_parsing = "Mensaje vacío"
                return resultado

            # MSH — nota: en MSH el campo de encoding characters ocupa la posición 1
            # después del split por '|', por lo que MSH-7 queda en índice 6.
            msh = HL7Parser._buscar_segmento(segmentos, "MSH")
            if msh:
                resultado.timestamp = HL7Parser._parsear_timestamp(
                    HL7Parser._campo(msh, 6)
                )

            # MSA — obligatorio en ACK
            msa = HL7Parser._buscar_segmento(segmentos, "MSA")
            if not msa:
                resultado.error_parsing = "Falta segmento MSA en el ACK"
                return resultado

            resultado.estado = HL7Parser._campo(msa, 1)       # AA / AE / AR
            resultado.turno_id = HL7Parser._campo(msa, 2)     # Message Control ID
            resultado.mensaje = HL7Parser._campo(msa, 3)      # Text Message

            # ERR (opcional) — si hay error, enriquece el mensaje
            err = HL7Parser._buscar_segmento(segmentos, "ERR")
            if err and not resultado.mensaje:
                resultado.mensaje = HL7Parser._campo(err, 3) or HL7Parser._campo(err, 1)

            resultado.valido = bool(resultado.estado)

            # Guardar en disco para auditoría
            HL7Parser._guardar_recibido(raw, "ack")

        except Exception as exc:
            logger.exception("Error parseando ACK: %s", exc)
            resultado.error_parsing = str(exc)

        return resultado

    @staticmethod
    def parsear_oru(raw: str) -> ResultadoORU:
        """
        Parsea un mensaje ORU^R01 (resultado de laboratorio).

        Segmentos esperados:
          MSH|...|ORU^R01^...|...
          PID|1||DNI^^^DNI||APELLIDO^NOMBRE
          OBR|1|TURNO_ID||...
          OBX|1|NM|CODIGO^DESC||VALOR|UNIDAD|RANGO|...||F

        Args:
            raw: Mensaje HL7 crudo en formato ER7

        Returns:
            ResultadoORU con los campos extraídos
        """
        resultado = ResultadoORU()
        try:
            segmentos = HL7Parser._segmentar(raw)
            if not segmentos:
                resultado.error_parsing = "Mensaje vacío"
                return resultado

            # MSH — nota: en MSH el campo de encoding characters ocupa la posición 1
            # después del split por '|', por lo que MSH-7 queda en índice 6.
            msh = HL7Parser._buscar_segmento(segmentos, "MSH")
            if msh:
                resultado.timestamp = HL7Parser._parsear_timestamp(
                    HL7Parser._campo(msh, 6)
                )

            # PID
            pid = HL7Parser._buscar_segmento(segmentos, "PID")
            if pid:
                pid3 = HL7Parser._campo(pid, 3)
                resultado.dni_paciente = pid3.split("^")[0] if pid3 else ""
                pid5 = HL7Parser._campo(pid, 5)
                resultado.nombre_paciente = pid5.replace("^", " ").strip() if pid5 else ""

            # OBR — tomar el primero para el ID de turno
            obr = HL7Parser._buscar_segmento(segmentos, "OBR")
            if obr:
                resultado.turno_id = HL7Parser._campo(obr, 2)  # Placer Order Number

            # OBX — uno por resultado/determinación
            for seg in segmentos:
                if seg and seg[0] == "OBX":
                    obs = HL7Parser._parsear_obx(seg)
                    resultado.observaciones.append(obs)

            resultado.valido = bool(resultado.turno_id or resultado.dni_paciente)

            # Guardar en disco para auditoría
            HL7Parser._guardar_recibido(raw, "oru")

        except Exception as exc:
            logger.exception("Error parseando ORU: %s", exc)
            resultado.error_parsing = str(exc)

        return resultado

    @staticmethod
    def parsear_orl(mensaje: str) -> "ResultadoORL":
        """
        Parsea un mensaje ORL^O22 (Laboratory Order Response) del LIS.

        Extrae el estado de la orden (ORC-1), el ID del turno (ORC-2)
        y el Message Control ID (MSH-10) necesario para construir el ACK.

        Estados posibles en ORC-1:
          UA → Unable to Accept (orden rechazada)
          IP → In Progress (orden en proceso)
          CM → Complete (orden completada)
          SC → Status Changed (estado modificado)

        Args:
            mensaje: Texto HL7 ER7 del ORL^O22

        Returns:
            ResultadoORL con los campos extraídos o error_parsing si falla
        """
        _ESTADOS = {
            "UA": "Unable to Accept - Orden rechazada",
            "IP": "In Progress - Orden en proceso",
            "CM": "Complete - Orden completada",
            "SC": "Status Changed - Estado modificado",
        }

        try:
            segmentos = HL7Parser._segmentar(mensaje)
            if not segmentos:
                return ResultadoORL(
                    valido=False,
                    turno_id="",
                    orden_estado="",
                    orden_estado_desc="",
                    mensaje_control_id="",
                    error_parsing="Mensaje vacío",
                )

            msh = HL7Parser._buscar_segmento(segmentos, "MSH")
            if not msh:
                return ResultadoORL(
                    valido=False,
                    turno_id="",
                    orden_estado="",
                    orden_estado_desc="",
                    mensaje_control_id="",
                    error_parsing="Falta segmento MSH",
                )

            # MSH-10 está en índice 9 (contando desde 0)
            control_id = HL7Parser._campo(msh, 9)

            # ORC puede no estar presente en todos los ORL
            try:
                orc = HL7Parser._buscar_segmento(segmentos, "ORC")
                if orc:
                    orden_estado = HL7Parser._campo(orc, 1)
                    turno_id_raw = HL7Parser._campo(orc, 2)
                    turno_id = turno_id_raw.split("^")[0]
                else:
                    orden_estado = ""
                    turno_id = ""
            except Exception:
                orden_estado = ""
                turno_id = ""

            return ResultadoORL(
                valido=True,
                turno_id=turno_id,
                orden_estado=orden_estado,
                orden_estado_desc=_ESTADOS.get(
                    orden_estado, f"Estado desconocido: {orden_estado}"
                ),
                mensaje_control_id=control_id,
                error_parsing="",
            )

        except Exception as exc:
            return ResultadoORL(
                valido=False,
                turno_id="",
                orden_estado="",
                orden_estado_desc="",
                mensaje_control_id="",
                error_parsing=str(exc),
            )

    # ──────────────────────────────────────────────────────────────────────────
    # Helpers de parsing
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _segmentar(raw: str) -> list[list[str]]:
        """
        Divide el mensaje ER7 en segmentos y campos.

        HL7 usa \\r (CR) como separador de segmentos y | como separador de campos.
        """
        # Normalizar separadores: algunos sistemas usan \\n o \\r\\n
        raw = raw.replace("\r\n", "\r").replace("\n", "\r")
        lineas = [l for l in raw.split("\r") if l.strip()]
        return [linea.split("|") for linea in lineas]

    @staticmethod
    def _buscar_segmento(segmentos: list[list[str]], nombre: str) -> Optional[list[str]]:
        """Retorna el primer segmento que coincida con el nombre dado."""
        for seg in segmentos:
            if seg and seg[0] == nombre:
                return seg
        return None

    @staticmethod
    def _campo(segmento: list[str], posicion: int) -> str:
        """
        Retorna el valor del campo en la posición dada (1-indexed como en HL7).
        Retorna cadena vacía si la posición no existe.
        """
        try:
            return segmento[posicion].strip()
        except IndexError:
            return ""

    @staticmethod
    def _parsear_obx(seg: list[str]) -> Observacion:
        """Convierte un segmento OBX en una instancia Observacion."""
        obs = Observacion()
        obs.set_id = HL7Parser._campo(seg, 1)

        # OBX-3: Observation Identifier → CODIGO^DESCRIPCION^SISTEMA
        obx3 = HL7Parser._campo(seg, 3)
        partes = obx3.split("^")
        obs.codigo = partes[0] if partes else ""
        obs.descripcion = partes[1] if len(partes) > 1 else ""

        obs.valor = HL7Parser._campo(seg, 5)
        obs.unidades = HL7Parser._campo(seg, 6)
        obs.rango_referencia = HL7Parser._campo(seg, 7)
        obs.estado = HL7Parser._campo(seg, 11) or HL7Parser._campo(seg, 10)  # F/P/C
        return obs

    @staticmethod
    def _parsear_timestamp(valor: str) -> Optional[datetime]:
        """
        Parsea timestamp HL7 (YYYYMMDDHHMMSS o YYYYMMDD).
        Retorna None si el valor está vacío o no es parseable.
        """
        if not valor:
            return None
        # Longitudes esperadas: 14=YYYYMMDDHHMMSS, 12=YYYYMMDDHHMM, 8=YYYYMMDD
        pares = [
            (14, "%Y%m%d%H%M%S"),
            (12, "%Y%m%d%H%M"),
            (8,  "%Y%m%d"),
        ]
        for largo, fmt in pares:
            try:
                return datetime.strptime(valor[:largo], fmt)
            except ValueError:
                continue
        return None

    @staticmethod
    def _guardar_recibido(raw: str, tipo: str) -> None:
        """
        Persiste el mensaje recibido en mensajes/hl7/recibidos/ para auditoría.
        No lanza excepciones — fallo silencioso para no interrumpir el flujo.
        """
        try:
            carpeta = os.path.join(settings.BASE_DIR, "mensajes", "hl7", "recibidos")
            os.makedirs(carpeta, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            nombre = f"{tipo}_{ts}.hl7"
            with open(os.path.join(carpeta, nombre), "w", encoding="utf-8", newline="") as f:
                f.write(raw)
        except Exception as exc:
            logger.warning("No se pudo guardar mensaje HL7 recibido: %s", exc)
