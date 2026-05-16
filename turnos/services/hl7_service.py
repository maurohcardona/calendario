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
  PV1  → Visita del paciente (ambulatorio)
  ORC  → Orden común (UN solo segmento por mensaje)
  TQ1  → Timing/Prioridad (UN solo segmento, prioridad Routine)
  OBR  → Un segmento por cada determinación (solo campo 4: codigo^nombre)

Formato de archivo: .hl7 (ER7, separado por \\r)
Carpeta de destino: mensajes/hl7/enviados/
"""

import os
import uuid
from datetime import datetime
from typing import Optional

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
_SISTEMA_ORIGEN = "TURNOS"
_INSTITUCION = "HTAL_BALESTRINI"
_SISTEMA_DESTINO = "LIS"
_VERSION_HL7 = "2.5"


def _sexo_hl7(sexo: str) -> str:
    """Convierte sexo del modelo Paciente al código HL7 (M/F/U)."""
    mapa = {"Masculino": "M", "Femenino": "F"}
    return mapa.get(sexo, "U")


def _timestamp() -> str:
    """Retorna timestamp en formato HL7: YYYYMMDDHHMMSS."""
    return datetime.now().strftime("%Y%m%d%H%M%S")


def _control_id() -> str:
    """Genera un Message Control ID único (MSH-10)."""
    return f"MSG{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:4].upper()}"


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

            # Serializar a ER7
            er7 = msg.to_er7()

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
          MSH → PID → PV1 → ORC → TQ1 → OBR(s)
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
        msg.msh.msh_11 = "P"  # P=Production, T=Test
        msg.msh.msh_15 = "AL"
        msg.msh.msh_16 = "ER"

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
        pid.pid_3 = f"{paciente.iden}^^^DNI"
        pid.pid_5 = f"{paciente.apellido.upper()}^{paciente.nombre.upper()}"
        pid.pid_7 = paciente.fecha_nacimiento.strftime("%Y%m%d")
        pid.pid_8 = _sexo_hl7(paciente.sexo)

        # Teléfono (PID-13, componente PRN)
        if paciente.telefono:
            pid.pid_13 = f"^PRN^PH^^^{paciente.telefono}"

        # Email (PID-14)
        if paciente.email:
            try:
                pid.pid_14 = f"^NET^Internet^{paciente.email}"
            except Exception:
                pass  # Campo opcional, no interrumpir si falla

        msg.add(pid)

    @staticmethod
    def _construir_pv1(msg: Message, turno: Turno) -> None:
        """
        PV1 – Patient Visit

        Requerido por el LIS Navify entre PID y ORC.

        PV1-2:  Patient Class → O (Outpatient/Ambulatorio)
                Valores posibles para el futuro:
                  O = Outpatient (Ambulatorio)
                  I = Inpatient (Internación)
                  E = Emergency (Guardia)
        PV1-3:  Assigned Patient Location → ^^69 (código de ubicación fijo)
        PV1-19: Visit Number → {turno_id}^^^^^^^^{institucion}
        """
        pv1 = Segment("PV1", version=_VERSION_HL7)
        pv1.pv1_2 = "O"                                       # Outpatient (ambulatorio)
        pv1.pv1_3 = "^^69"                                    # Código de ubicación
        pv1.pv1_19 = f"{turno.id}^^^^^^^^{_INSTITUCION}"      # Visit Number
        msg.add(pv1)

    @staticmethod
    def _construir_ordenes(
        msg: Message,
        turno: Turno,
        determinaciones: list[dict],
        ts: str,
    ) -> None:
        """
        ORC + TQ1 + OBR(s) – Common Order + Timing/Quantity + Observation Request

        Estructura según formato Navify:
          - UN solo ORC con la info general de la orden
          - UN solo TQ1 con prioridad Routine
          - Múltiples OBRs (uno por cada determinación) con SOLO campo 4

        ORC:
          ORC-1:  Order Control → OR (Order/service request)
          ORC-2:  Placer Order Number → ID del turno
          ORC-9:  Date/Time of Transaction → timestamp
          ORC-12: Ordering Provider → médico

        TQ1:
          TQ1-10: Priority → R (Routine)

        OBR:
          OBR-4:  Universal Service ID → codigo^nombre
                  (campos 1, 2, 3 vacíos según formato Navify)
        """
        turno_id = str(turno.id)
        medico_hl7 = HL7Service._formatear_medico(turno)

        # ── ORC (Common Order) ───────────────────────────────────────────────
        orc = Segment("ORC", version=_VERSION_HL7)
        orc.orc_1 = "OR"       # Order/service request (según Navify)
        orc.orc_2 = turno_id   # Placer Order Number
        orc.orc_9 = ts         # Date/Time of Transaction
        if medico_hl7:
            orc.orc_12 = medico_hl7  # Ordering Provider
        msg.add(orc)

        # ── TQ1 (Timing/Quantity) ────────────────────────────────────────────
        tq1 = Segment("TQ1", version=_VERSION_HL7)
        tq1.tq1_10 = "R"       # Priority: R (Routine)
        msg.add(tq1)

        # ── OBR(s) (Observation Request) ──────────────────────────────────────
        if not determinaciones:
            # Caso sin determinaciones: OBR mínimo para preservar estructura válida
            obr = HL7Service._construir_obr(codigo="", nombre="SIN DETERMINACIONES")
            msg.add(obr)
        else:
            for det in determinaciones:
                obr = HL7Service._construir_obr(
                    codigo=det["codigo"],
                    nombre=det["nombre"],
                )
                msg.add(obr)

    @staticmethod
    def _construir_obr(codigo: str, nombre: str) -> Segment:
        """
        Construye un segmento OBR para una determinación (formato Navify minimalista).

        Según Navify, OBR solo contiene el campo 4 (Universal Service ID):
          OBR||||codigo^nombre

        Campos 1, 2, 3 están vacíos intencionalmente.
        El sistema de codificación (^99LOCAL) se omite — Navify usa solo código^nombre.
        """
        obr = Segment("OBR", version=_VERSION_HL7)
        # OBR-1, OBR-2, OBR-3: vacíos (según formato Navify)
        # OBR-4: Universal Service ID → codigo^nombre
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
        Retorna el médico en formato HL7 XCN:
        ^NOMBRE^^^MATRICULA

        El campo 'nombre' del modelo Medico contiene el nombre completo.
        Lo usamos como apellido HL7 para no depender de un split frágil.

        Retorna cadena vacía si el turno no tiene médico.
        """
        medico = turno.medico
        if not medico:
            return ""
        matricula = medico.matricula or ""
        return f"^{medico.nombre}^^^{matricula}"

    @staticmethod
    def _guardar_archivo(er7: str, turno_id: int) -> str:
        """
        Persiste el mensaje HL7 en mensajes/hl7/enviados/.

        Formato de nombre: oml_{turno_id}_{timestamp}.hl7
        Retorna la ruta completa del archivo creado.
        """
        carpeta = os.path.join(settings.BASE_DIR, "mensajes", "hl7", "enviados")
        os.makedirs(carpeta, exist_ok=True)

        nombre = f"oml_{turno_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.hl7"
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
