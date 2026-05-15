"""
Servicio para generación de mensajes HL7 v2.5 OML^O21 (Laboratory Order Message).

Reemplaza ASTMService para la coordinación de turnos con el laboratorio.

Mapeo ASTM → HL7:
  Header (H)  → MSH (Message Header)
  Patient (P) → PID (Patient Identification) + NTE (notas)
  Order (O)   → ORC (Common Order) + OBR por cada determinación
  Terminator  → implícito en el formato HL7

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

# Sistema de codificación para determinaciones locales
_SISTEMA_CODIGOS = "99LOCAL"


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
            nombre_impresora: Nombre de la impresora de destino (va en OBR-18)
            usuario: Username del operador que coordina (va en ORC-10)

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
                nombre_impresora=nombre_impresora,
                usuario=usuario,
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
        nombre_impresora: str,
        usuario: str,
    ) -> Message:
        """Construye y retorna el objeto Message HL7 OML^O21 completo."""
        ts = _timestamp()
        msg = Message("OML_O21", version=_VERSION_HL7, validation_level=_VALIDATION)

        HL7Service._construir_msh(msg, ts)
        HL7Service._construir_pid(msg, paciente)
        HL7Service._construir_nte_paciente(msg, turno, paciente)
        HL7Service._construir_ordenes(msg, turno, determinaciones, nombre_impresora, usuario, ts)

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
          MSH-9: Message Type
          MSH-10: Message Control ID
          MSH-11: Processing ID
        """
        msg.msh.msh_3 = _SISTEMA_ORIGEN
        msg.msh.msh_4 = _INSTITUCION
        msg.msh.msh_5 = _SISTEMA_DESTINO
        msg.msh.msh_6 = "ROCHE"
        msg.msh.msh_7 = ts
        msg.msh.msh_9 = "OML^O21^OML_O21"
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

        # Email (segundo repetidor de PID-13)
        if paciente.email:
            # hl7apy en modo TOLERANT acepta el campo completo como string
            # El email va en un segundo repetidor de PID-13
            try:
                pid.pid_14 = f"^NET^Internet^{paciente.email}"
            except Exception:
                pass  # Campo opcional, no interrumpir si falla

        msg.add(pid)

    @staticmethod
    def _construir_nte_paciente(msg: Message, turno: Turno, paciente: Paciente) -> None:
        """
        NTE – Notes and Comments (después de PID)

        Se generan hasta dos segmentos NTE:
        - Uno para nota_interna del turno
        - Uno para observaciones del paciente
        """
        notas = [
            (turno.nota_interna or "").strip(),
            (paciente.observaciones or "").strip(),
        ]
        for idx, nota in enumerate(notas, start=1):
            if nota:
                nte = Segment("NTE", version=_VERSION_HL7)
                nte.nte_1 = str(idx)
                nte.nte_2 = "P"   # Comment type: P = Patient
                nte.nte_3 = nota
                msg.add(nte)

    @staticmethod
    def _construir_ordenes(
        msg: Message,
        turno: Turno,
        determinaciones: list[dict],
        nombre_impresora: str,
        usuario: str,
        ts: str,
    ) -> None:
        """
        ORC + OBR(s) – Common Order + Observation Request

        Se genera un único ORC y un OBR por cada determinación.
        Si no hay determinaciones, se genera un OBR vacío para preservar
        la estructura mínima del mensaje.

        ORC:
          ORC-1:  Order Control → NW (New Order)
          ORC-2:  Placer Order Number → ID del turno
          ORC-5:  Order Status → SC (Scheduled)
          ORC-10: Entered By → usuario coordinador
          ORC-12: Ordering Provider → médico

        OBR:
          OBR-1:  Set ID
          OBR-2:  Placer Order Number (igual que ORC-2)
          OBR-4:  Universal Service ID → CODIGO^NOMBRE^99LOCAL
          OBR-16: Ordering Provider → médico (mismo que ORC-12)
          OBR-18: Placer Field 1 → nombre impresora destino
        """
        turno_id = str(turno.id)
        medico_hl7 = HL7Service._formatear_medico(turno)
        usuario_hl7 = f"^{usuario}" if usuario else ""

        # ── ORC ──────────────────────────────────────────────────────────────
        orc = Segment("ORC", version=_VERSION_HL7)
        orc.orc_1 = "NW"          # New Order
        orc.orc_2 = turno_id
        orc.orc_5 = "SC"          # Scheduled
        if usuario_hl7:
            orc.orc_10 = usuario_hl7
        if medico_hl7:
            orc.orc_12 = medico_hl7
        msg.add(orc)

        # ── OBR(s) ────────────────────────────────────────────────────────────
        if not determinaciones:
            # Mensaje válido con OBR mínimo (sin determinación específica)
            obr = HL7Service._construir_obr(
                set_id=1,
                turno_id=turno_id,
                codigo="",
                nombre="SIN DETERMINACIONES",
                medico_hl7=medico_hl7,
                nombre_impresora=nombre_impresora,
                ts=ts,
            )
            msg.add(obr)
        else:
            for idx, det in enumerate(determinaciones, start=1):
                obr = HL7Service._construir_obr(
                    set_id=idx,
                    turno_id=turno_id,
                    codigo=det["codigo"],
                    nombre=det["nombre"],
                    medico_hl7=medico_hl7,
                    nombre_impresora=nombre_impresora,
                    ts=ts,
                )
                msg.add(obr)

    @staticmethod
    def _construir_obr(
        set_id: int,
        turno_id: str,
        codigo: str,
        nombre: str,
        medico_hl7: str,
        nombre_impresora: str,
        ts: str,
    ) -> Segment:
        """Construye un segmento OBR para una determinación."""
        obr = Segment("OBR", version=_VERSION_HL7)
        obr.obr_1 = str(set_id)
        obr.obr_2 = turno_id
        if codigo:
            obr.obr_4 = f"{codigo}^{nombre}^{_SISTEMA_CODIGOS}"
        else:
            obr.obr_4 = nombre
        obr.obr_6 = ts  # Requested Date/Time
        if medico_hl7:
            obr.obr_16 = medico_hl7
        if nombre_impresora:
            obr.obr_18 = nombre_impresora  # Placer Field 1 → impresora destino
        return obr

    # ──────────────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _formatear_medico(turno: Turno) -> str:
        """
        Retorna el médico en formato HL7 XCN:
        ID^APELLIDO^NOMBRE^^^MATRICULA

        Retorna cadena vacía si el turno no tiene médico.
        """
        medico = turno.medico
        if not medico:
            return ""
        # El campo 'nombre' del modelo Medico contiene "Nombre Apellido" completo.
        # Lo usamos como apellido HL7 para no depender de un split frágil.
        return f"^{medico.nombre}^^^{medico.matricula or ''}"

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
