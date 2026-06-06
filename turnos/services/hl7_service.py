"""
Servicio para generación de mensajes HL7 v2.5 OML^O21 (Laboratory Order Message).

Reemplaza ASTMService para la coordinación de turnos con el laboratorio.

Mapeo ASTM → HL7:
  Header (H)  → MSH (Message Header)
  Patient (P) → PID (Patient Identification)
  Patient Visit → PV1
  Order (O)   → ORC + TQ1 + OBR por cada determinación
  Terminator  → implícito en el formato HL7

Estructura del mensaje (formato Navify):
  MSH  → Cabecera del mensaje
  PID  → Identificación del paciente
  PV1  → Visita del paciente
  ORC  → Orden común (UN solo segmento por mensaje)
  TQ1  → Timing/Prioridad (R o S según tipo y origen)
  OBR  → Un segmento por cada determinación (solo campo 4: codigo^nombre)
  NTE  → Comentario de la orden (opcional)
  DG1  → Diagnóstico (opcional)
  SPM  → Tipo de muestra (opcional)

Lógica condicional según tipo y origen:

  Identificadores (ORC-2, PV1-19):
    Turnos  → T{id}
    Órdenes → O{id}

  PV1-2 Patient Class:
    Turno / Orden AMBULATORIO          → O (Outpatient)
    Orden GUARDIA / INTERNACION / PROGRAMADAS → I (Inpatient)

  TQ1-9 Prioridad:
    Turno / Orden AMBULATORIO / PROGRAMADAS → R (Routine)
    Orden GUARDIA                           → S (Stat)
    Orden INTERNACION 07:00–12:30           → R (Routine)
    Orden INTERNACION 12:31–06:59           → S (Stat)

  PV1-3 Patient Location:
    Si orden.sala tiene valor → ^^{sala}
    Si está vacío             → ^^

Formato de archivo: .hl7 (ER7, separado por \\r)
Carpeta de destino: mensajes/hl7/enviados/
"""

import os
import uuid
from datetime import datetime
from typing import Any, Optional

from django.conf import settings
from django.contrib.auth.models import User

from hl7apy.core import Message, Segment
from hl7apy import consts

from pacientes.models import Paciente
from turnos.models import Turno, Coordinados
from .determinacion_service import DeterminacionService

# Nivel de validación: TOLERANT permite construir el mensaje sin errores por
# campos opcionales ausentes; la validación de negocio la manejamos nosotros.
_VALIDATION = consts.VALIDATION_LEVEL.TOLERANT

# Identificadores fijos del sistema emisor
_SISTEMA_ORIGEN = "HOST"
_INSTITUCION = "HTAL_BALESTRINI"
_SISTEMA_DESTINO = "LIS"
_VERSION_HL7 = "2.5"


def _calcular_prioridad(obj: Any) -> str:
    """
    Calcula la prioridad HL7 (TQ1-9) según tipo y origen del objeto.

    Reglas:
      - Turno (sin tipo_origen):                  siempre R
      - Orden AMBULATORIO:                         siempre R
      - Orden ORDENES_PROGRAMADAS:                 siempre R
      - Orden GUARDIA:                             siempre S
      - Orden INTERNACION 07:00–12:30:             R
      - Orden INTERNACION 12:31–06:59:             S

    Args:
        obj: Turno o _OrdenAdapter (duck-typing)

    Returns:
        'R' (Routine) o 'S' (Stat/Urgente)
    """
    from datetime import time

    if not hasattr(obj, "tipo_origen"):
        return "R"

    origen = obj.tipo_origen

    if origen in ("AMBULATORIO", "ORDENES_PROGRAMADAS"):
        return "R"

    if origen == "GUARDIA":
        return "S"

    if origen == "INTERNACION":
        hora = obj.fecha_creacion.time()
        if time(7, 0) <= hora <= time(12, 30):
            return "R"
        return "S"

    return "R"


def _calcular_patient_class(obj: Any) -> str:
    """
    Calcula PV1-2 (Patient Class) según tipo y origen del objeto.

    Reglas:
      - Turno (sin tipo_origen):   O (Outpatient)
      - Orden AMBULATORIO:         O (Outpatient)
      - Resto (GUARDIA, INTERNACION, ORDENES_PROGRAMADAS): I (Inpatient)

    Args:
        obj: Turno o _OrdenAdapter (duck-typing)

    Returns:
        'O' (Outpatient) o 'I' (Inpatient)
    """
    if not hasattr(obj, "tipo_origen"):
        return "O"

    if obj.tipo_origen == "AMBULATORIO":
        return "O"

    return "I"


def _calcular_origen_orc13(obj: Any) -> str:
    """
    Calcula ORC-13 (código de origen) según tipo y origen del objeto.

    Reglas:
      - Turno (sin tipo_origen):   1
      - Orden AMBULATORIO:         1
      - Orden INTERNACION:         2
      - Orden ORDENES_PROGRAMADAS: 2
      - Orden GUARDIA:             3

    Args:
        obj: Turno o _OrdenAdapter (duck-typing)

    Returns:
        str: '1', '2' o '3'
    """
    if not hasattr(obj, "tipo_origen"):
        return "1"

    origen = obj.tipo_origen

    if origen == "AMBULATORIO":
        return "1"
    if origen in ("INTERNACION", "ORDENES_PROGRAMADAS"):
        return "2"
    if origen == "GUARDIA":
        return "3"

    return "1"


def _calcular_servicio_orc17(obj: Any) -> str:
    """
    Calcula ORC-17 (ID de servicio) según tipo y origen del objeto.

    Reglas:
      - Turno (sin tipo_origen):         siempre '1'
      - Orden con servicio asignado:     str(orden.servicio.id)
      - Orden sin servicio (None):       '1'

    Args:
        obj: Turno o _OrdenAdapter (duck-typing)

    Returns:
        str: ID del servicio o '1' como fallback
    """
    servicio = getattr(obj, "servicio", None)
    if servicio and servicio.id:
        return str(servicio.id)
    return "1"


def _generar_identificador(obj: Any) -> str:
    """
    Genera el identificador con prefijo T (turno) u O (orden).

    - Turno (sin tipo_origen): T{id}
    - OrdenAdapter (con tipo_origen): O{id}

    Usado en ORC-2, OBR-2 y PV1-19.

    Args:
        obj: Turno o _OrdenAdapter (duck-typing)

    Returns:
        str: 'T{id}' o 'OR{id}'
    """
    prefijo = "OR" if hasattr(obj, "tipo_origen") else "T"
    return f"{prefijo}{obj.id}"


def _sexo_hl7(sexo: str) -> str:
    """Convierte sexo del modelo Paciente al código HL7 (M/F/U)."""
    mapa = {"Masculino": "M", "Femenino": "F"}
    return mapa.get(sexo, "U")


def _timestamp() -> str:
    """Retorna timestamp en formato HL7: YYYYMMDDHHMMSS."""
    return datetime.now().strftime("%Y%m%d%H%M%S")


def _control_id() -> str:
    """Genera un Message Control ID único (MSH-10)."""
    return f"{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:4].upper()}"


class HL7Service:
    """
    Servicio para generación y gestión de mensajes HL7 v2.5 OML^O21.

    Responsabilidades:
    - Generar mensaje OML^O21 a partir de un Turno
    - Validar estructura mínima antes de guardar
    - Persistir archivo .hl7 en mensajes/hl7/enviados/
    - Registrar la coordinación en el modelo Coordinados

    Uso:
        exito, ruta, error = HL7Service.generar_mensaje_oml(turno, "IMP001", "usuario")
    """

    # ──────────────────────────────────────────────────────────────────────────
    # Método público principal
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def generar_mensaje_oml(
        turno: Turno,
        nombre_impresora: str,
        usuario: str,
    ) -> tuple[bool, str, str]:
        """
        Genera un archivo HL7 OML^O21 para coordinación de turno.

        Args:
            turno: Instancia del Turno a coordinar
            nombre_impresora: Nombre de la impresora de destino (reservado para uso futuro)
            usuario: Username del operador que coordina (reservado para uso futuro)

        Returns:
            Tupla (exito, ruta_archivo, mensaje_error)
        """
        try:
            # Guardia: no coordinar dos veces el mismo turno
            if Coordinados.objects.filter(id_turno=turno.id).exists():
                return False, "", "Este turno ya fue coordinado anteriormente"

            paciente = turno.dni
            if not paciente:
                return False, "", "Paciente no encontrado"

            if not (paciente.iden or "").strip():
                return False, "", "El paciente no tiene DNI registrado. No se puede coordinar."

            # Obtener determinaciones expandidas en formato HL7
            determinaciones = DeterminacionService.mapear_determinaciones_a_hl7(
                turno.determinaciones or ""
            )

            # Construir mensaje
            msg = HL7Service._construir_mensaje(
                turno=turno,
                paciente=paciente,
                determinaciones=determinaciones,
            )

            # Serializar a ER7 y post-procesar
            er7 = HL7Service._limpiar_er7(msg.to_er7())

            # Guardar archivo
            ruta = HL7Service._guardar_archivo(er7, turno.id)

            # Obtener instancia User si existe
            usuario_obj = HL7Service._obtener_usuario(usuario)

            # Registrar en Coordinados
            Coordinados.objects.create(
                id_turno=turno.id,
                fecha_coordinacion=datetime.now(),
                usuario=usuario_obj,
                dni=paciente,
                determinaciones=turno.determinaciones or "",
                mensaje_tipo="HL7",
                mensaje_hl7=er7,
            )

            return True, ruta, ""

        except Exception as exc:
            return False, "", f"Error al generar mensaje HL7: {exc}"

    @staticmethod
    def verificar_coordinado(turno_id: int) -> bool:
        """Retorna True si el turno ya fue coordinado."""
        return Coordinados.objects.filter(id_turno=turno_id).exists()

    @staticmethod
    def generar_mensaje_oml_desde_orden(
        orden: "Any",
        nombre_impresora: str,
        usuario: str,
    ) -> tuple[bool, str, str]:
        """
        Genera un archivo HL7 OML^O21 desde una OrdenLaboratorio.

        Similar a generar_mensaje_oml() pero adaptado para OrdenLaboratorio:
        - Usa orden.paciente en lugar de turno.dni.
        - Convierte determinaciones M2M a CSV antes de procesarlas.
        - Registra en CoordinadosOrden en lugar de Coordinados.
        - NO valida duplicados: permite múltiples ingresos de la misma orden.

        Args:
            orden: Instancia de OrdenLaboratorio a coordinar.
            nombre_impresora: Nombre de la impresora/etiquetadora seleccionada.
            usuario: Username del operador que ingresa la orden.

        Returns:
            Tupla (exito, ruta_archivo, mensaje_error)
        """
        try:
            from ordenes.models import CoordinadosOrden
            from django.utils import timezone as tz

            paciente = orden.paciente
            if not paciente:
                return False, "", "La orden no tiene paciente asociado"

            if not (paciente.iden or "").strip():
                return False, "", "El paciente no tiene DNI registrado. No se puede coordinar."

            # Serializar determinaciones M2M → CSV para reutilizar la lógica HL7
            determinaciones_csv = DeterminacionService.serializar_determinaciones_orden(orden)

            if not determinaciones_csv:
                return False, "", "La orden no tiene determinaciones registradas"

            # Mapear determinaciones a formato HL7
            determinaciones_hl7 = DeterminacionService.mapear_determinaciones_a_hl7(
                determinaciones_csv
            )

            # Adapter: expone los mismos atributos que Turno espera en _construir_*
            class _OrdenAdapter:
                id = orden.pk
                dni = paciente
                determinaciones = determinaciones_csv
                fecha = orden.fecha_programada or tz.localdate()
                medico = orden.medico
                nota_interna = orden.observaciones or ""
                agenda = None
                institucion = None
                # Campos para lógica condicional HL7
                tipo_origen = orden.tipo_origen
                sala = orden.sala or ""
                fecha_creacion = orden.fecha_creacion
                servicio = orden.servicio  # FK a Servicio (puede ser None)

            adapter = _OrdenAdapter()

            # Construir mensaje reutilizando métodos privados existentes
            ts = _timestamp()
            msg = Message("OML_O21", version=_VERSION_HL7, validation_level=_VALIDATION)
            HL7Service._construir_msh(msg, ts)
            HL7Service._construir_pid(msg, paciente)
            HL7Service._construir_pv1(msg, adapter)
            HL7Service._construir_ordenes(msg, adapter, determinaciones_hl7, ts)

            # Serializar y limpiar
            er7 = HL7Service._limpiar_er7(msg.to_er7())

            # Guardar archivo con prefijo "orden" para distinguirlo de turnos
            ruta = HL7Service._guardar_archivo(er7, orden.pk, prefijo="orden")

            # Obtener instancia User
            usuario_obj = HL7Service._obtener_usuario(usuario)

            # Registrar en CoordinadosOrden
            CoordinadosOrden.objects.create(
                orden=orden,
                usuario=usuario_obj,
                determinaciones=determinaciones_csv,
                mensaje_tipo="HL7",
                mensaje_hl7=er7,
            )

            return True, ruta, ""

        except Exception as exc:
            return False, "", f"Error al generar mensaje HL7 desde orden: {exc}"

    # ──────────────────────────────────────────────────────────────────────────
    # Construcción del mensaje
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _construir_mensaje(
        turno: Turno,
        paciente: Paciente,
        determinaciones: list[dict],
    ) -> Message:
        """
        Construye y retorna el objeto Message HL7 OML^O21 completo.

        Estructura del mensaje (formato Navify):
          MSH → PID → PV1 → ORC → TQ1 → OBR(s) → NTE → DG1 → SPM
        """
        ts = _timestamp()
        msg = Message("OML_O21", version=_VERSION_HL7, validation_level=_VALIDATION)

        HL7Service._construir_msh(msg, ts)
        HL7Service._construir_pid(msg, paciente)
        HL7Service._construir_pv1(msg, turno)
        HL7Service._construir_ordenes(msg, turno, determinaciones, ts)

        return msg

    @staticmethod
    def _construir_msh(msg: Message, ts: str) -> None:
        """
        MSH – Message Header

        Campos obligatorios según HL7 v2.5:
          MSH-3: Sending Application
          MSH-4: Sending Facility
          MSH-5: Receiving Application
          MSH-7: Date/Time of Message
          MSH-9: Message Type (simplificado: OML^O21)
          MSH-10: Message Control ID
          MSH-11: Processing ID
        """
        msg.msh.msh_3 = _SISTEMA_ORIGEN
        msg.msh.msh_4 = _INSTITUCION
        msg.msh.msh_5 = _SISTEMA_DESTINO
        msg.msh.msh_6 = "ROCHE"
        msg.msh.msh_7 = ts
        msg.msh.msh_9 = "OML^O21"
        msg.msh.msh_10 = _control_id()

    @staticmethod
    def _construir_pid(msg: Message, paciente: Paciente) -> None:
        """
        PID – Patient Identification

        PID-1:  Set ID (1)
        PID-3:  Patient ID → DNI^^^DNI
        PID-5:  Patient Name → APELLIDO^NOMBRE
        PID-7:  Date of Birth → YYYYMMDD
        PID-8:  Administrative Sex → M/F/U
        PID-13: Phone/Email (opcional)
        """
        pid = Segment("PID", version=_VERSION_HL7)
        pid.pid_1 = "1"
        pid.pid_3 = paciente.iden                                          # Solo número DNI
        pid.pid_5 = f"{paciente.apellido.upper()}^{paciente.nombre.upper()}"
        pid.pid_6 = ""
        pid.pid_7 = paciente.fecha_nacimiento.strftime("%Y%m%d")
        pid.pid_8 = _sexo_hl7(paciente.sexo)
        pid.pid_11 = paciente.email

        if paciente.telefono:
            pid.pid_13 = f"^^^^^^^^^^^{paciente.telefono}"                         # Solo ^^^telefono

        msg.add(pid)

    @staticmethod
    def _construir_pv1(msg: Message, turno: Any) -> None:
        """
        PV1 – Patient Visit

        Requerido por el LIS Navify entre PID y ORC.

        PV1-2:  Patient Class
                  O = Outpatient (Turno / Orden Ambulatorio)
                  I = Inpatient  (Orden Guardia / Internación / Programadas)
        PV1-3:  Assigned Patient Location → ^^{sala} si existe, sino ^^
        PV1-19: Visit Number → T{id} para turnos, O{id} para órdenes
        """
        pv1 = Segment("PV1", version=_VERSION_HL7)
        pv1.pv1_2 = _calcular_patient_class(turno)
        sala = getattr(turno, "sala", "") or ""
        pv1.pv1_3 = f"^^{sala}" if sala else "^^"
        pv1.pv1_19 = _generar_identificador(turno)
        msg.add(pv1)

    @staticmethod
    def _construir_ordenes(
        msg: Message,
        turno: Turno,
        determinaciones: list[dict],
        ts: str,
    ) -> None:
        """
        ORC + TQ1 + OBR(s) + NTE + DG1 + SPM

        Estructura según formato Navify (basada en ejemplo del manual NLAB 3.08):
          - UN solo ORC con la info general de la orden
          - UN solo TQ1 con prioridad Routine
          - Múltiples OBRs (uno por cada determinación) con SOLO campo 4
          - NTE → vacío (NTE||||)
          - DG1 → vacío (DG1||||)
          - SPM → tipo de muestra (1^SUERO)

        ORC:
          ORC-1:  Order Control → OR (según ejemplo Navify)
          ORC-2:  Placer Order Number → turno_id solo numérico
                  (Navify valida formato estricto: solo acepta numérico)
          ORC-9:  Date/Time of Transaction → timestamp
          ORC-12: vacío
          ORC-13: Ordering Provider → matricula^nombre
          ORC-14: hardcodeado 1
          ORC-17: vacío
          ORC-18: 1^Consultorios Externos-Ambulatorio

        TQ1:
          TQ1-9: Priority → R (Routine)
                 (campo 9, no 10, según ejemplo: TQ1|||||||||R)
                 R = Modulo General S = Modulo de Emergencia

        OBR:
          OBR-1: Set ID
          OBR-4: Universal Service ID → codigo^nombre

        NTE: todos los campos vacíos → NTE||||
        DG1: todos los campos vacíos → DG1||||
        SPM: SPM-1 → 1^SUERO
        """
        turno_id = str(turno.id)
        identificador = _generar_identificador(turno)
        medico_hl7 = HL7Service._formatear_medico(turno)

        # ── ORC (Common Order) ───────────────────────────────────────────────
        orc = Segment("ORC", version=_VERSION_HL7)
        orc.orc_1 = "OR"
        orc.orc_2 = f"{identificador}^TURNOS"  # T{id} o O{id} ^ SystemName
        orc.orc_9 = ts
        if medico_hl7:
            orc.orc_12 = medico_hl7
        orc.orc_13 = _calcular_origen_orc13(turno)   # 1=Amb, 2=Int/Prog, 3=Guardia
        orc.orc_16 = f"{turno.nota_interna}"
        orc.orc_17 = _calcular_servicio_orc17(turno)  # ID servicio o '1' como fallback
        msg.add(orc)

        # ── TQ1 (Timing/Quantity) ────────────────────────────────────────────
        # TQ1-9: R (Routine) o S (Stat/Urgente) según reglas de negocio
        tq1 = Segment("TQ1", version=_VERSION_HL7)
        tq1.tq1_9 = _calcular_prioridad(turno)
        msg.add(tq1)

        # ── OBR(s) (Observation Request) ──────────────────────────────────────
        if not determinaciones:
            obr = HL7Service._construir_obr(set_id=1, codigo="", nombre="SIN DETERMINACIONES")
            msg.add(obr)
        else:
            for idx, det in enumerate(determinaciones, start=1):
                obr = HL7Service._construir_obr(
                    set_id=idx,
                    codigo=det["codigo"],
                    nombre=det["nombre"],
                )
                msg.add(obr)

        # ── NTE (Notes and Comments) ──────────────────────────────────────────
        # Asignamos hasta campo 4 vacío para forzar NTE||||
        nte = Segment("NTE", version=_VERSION_HL7)
        nte.nte_1 = ""
        nte.nte_2 = ""
        nte.nte_3 = ""
        msg.add(nte)

        # ── DG1 (Diagnosis) ───────────────────────────────────────────────────
        # Asignamos hasta campo 4 vacío para forzar DG1||||
        dg1 = Segment("DG1", version=_VERSION_HL7)
        dg1.dg1_1 = ""
        dg1.dg1_2 = ""
        dg1.dg1_3 = ""
        dg1.dg1_4 = ""
        msg.add(dg1)

        # ── SPM (Specimen) ────────────────────────────────────────────────────
        spm = Segment("SPM", version=_VERSION_HL7)
        spm.spm_4 = ""
        msg.add(spm)

    @staticmethod
    def _construir_obr(set_id: int, codigo: str, nombre: str) -> Segment:
        """
        Construye un segmento OBR para una determinación.

        Formato: OBR|set_id|||codigo^nombre
          OBR-1: Set ID
          OBR-4: Universal Service ID → codigo^nombre (ambos en campo 4)

        Nota: separar código y nombre en campos 4 y 5 hace que Navify
        pierda el TestName en su XML interno. Se mantiene codigo^nombre en campo 4.
        """
        obr = Segment("OBR", version=_VERSION_HL7)
        #obr.obr_1 = str(set_id)
        obr.obr_1 = ""
        if codigo:
            obr.obr_4 = f"{codigo}^{nombre}"
        else:
            obr.obr_4 = nombre
        return obr

    # ──────────────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _formatear_medico(turno: Turno) -> str:
        """
        Retorna el médico en formato HL7 para ORC-13:
        {matricula}^{nombre}

        Retorna cadena vacía si el turno no tiene médico.
        """
        medico = turno.medico
        if not medico:
            return ""
        matricula = medico.matricula or ""
        return f"{matricula}^{medico.nombre}"

    @staticmethod
    def _limpiar_er7(er7: str) -> str:
        """
        Post-procesa el ER7 generado por hl7apy para ajustarlo al formato Navify:

        1. MSH: recorta todo lo que hl7apy agrega automáticamente después de MSH-10
           (campos 11=ProcessingID, 12=VersionID, etc.)
           Resultado: MSH|^~\\&|TURNOS|HTAL_BALESTRINI|LIS|ROCHE|ts||OML^O21|control_id

        2. NTE/DG1: hl7apy puede colapsar segmentos vacíos — no necesita corrección
           porque los campos se asignan explícitamente hasta el campo 4.
        """
        separador = "\r" if "\r" in er7 else "\n"
        lineas = er7.split(separador)

        resultado = []
        for linea in lineas:
            if linea.startswith("MSH|"):
                campos = linea.split("|")
                # MSH tiene campos 0-10 (índices): MSH + ^~\& + 9 campos de datos
                # campo 10 = MSH-10 (Message Control ID) → índice 10
                linea = "|".join(campos[:11]).rstrip("|")
            resultado.append(linea)

        return separador.join(resultado)

    @staticmethod
    def _guardar_archivo(er7: str, ref_id: int, prefijo: str = "oml") -> str:
        """
        Persiste el mensaje HL7 en mensajes/hl7/enviados/.

        Args:
            er7: Mensaje en formato ER7.
            ref_id: ID de referencia (turno_id u orden_id).
            prefijo: Prefijo para el nombre del archivo.
                     "oml" para turnos (default), "orden" para OrdenLaboratorio.

        Formato de nombre: {prefijo}_{ref_id}_{timestamp}.hl7
        Retorna la ruta completa del archivo creado.
        """
        carpeta = os.path.join(settings.BASE_DIR, "mensajes", "hl7", "enviados")
        os.makedirs(carpeta, exist_ok=True)

        nombre = f"{prefijo}_{ref_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.hl7"
        ruta = os.path.join(carpeta, nombre)

        # Los mensajes HL7 usan \r como separador de segmentos (CR, 0x0D)
        with open(ruta, "w", encoding="utf-8", newline="") as f:
            f.write(er7)

        return ruta

    @staticmethod
    def _obtener_usuario(username: str) -> Optional[User]:
        """Retorna la instancia User o None si no existe."""
        if not username:
            return None
        try:
            return User.objects.get(username=username)
        except User.DoesNotExist:
            return None
