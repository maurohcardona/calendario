"""
Cliente MLLP para envío bidireccional de mensajes HL7 al LIS.

Protocolo MLLP (Minimal Lower Layer Protocol):
  - VT (0x0B) + mensaje HL7 + FS (0x1C) + CR (0x0D)
  - Conexión TCP sincrónica: abrir → enviar → recibir ACK → (escuchar ORU 30s) → cerrar

Flujo de envío:
  1. Conectar al LIS como cliente TCP (host/puerto configurado en settings)
  2. Enviar OML^O21 con wrapping MLLP
  3. Esperar ACK^O21 (timeout LIS_TIMEOUT_ACK segundos)
  4. Parsear ACK y actualizar Coordinados.ack_recibido + ack_estado
  5. Si ACK exitoso (AA): lanzar thread listener ORU (LIS_TIMEOUT_ORU segundos)
  6. Si falla envío o timeout: registrar en ColaReintentos para reintento automático

Recepción ORU:
  - El LIS reutiliza la misma conexión para enviar ORU^R01 (no inicia conexión nueva)
  - Thread escucha LIS_TIMEOUT_ORU segundos y guarda auditoría en mensajes/hl7/recibidos/
  - Por ahora solo auditoría (procesamiento de resultados: módulo futuro)

Configuración (settings.py / .env):
  LIS_HOST              IP del LIS           (default: 192.168.211.128)
  LIS_PORT              Puerto TCP            (default: 50000)
  LIS_TIMEOUT_CONEXION  Timeout conexión TCP  (default: 5s)
  LIS_TIMEOUT_ACK       Timeout espera ACK    (default: 10s)
  LIS_TIMEOUT_ORU       Ventana listener ORU  (default: 30s)
  LIS_MAX_REINTENTOS    Máx intentos en cola  (default: 3)
"""

import logging
import os
import socket
import threading
from datetime import datetime
from typing import Optional, Tuple

from django.conf import settings
from django.utils import timezone

from .hl7_parser import HL7Parser, ResultadoORL

logger = logging.getLogger(__name__)


def _settings_int(nombre: str, default: int) -> int:
    """Lee un entero desde settings con fallback seguro."""
    return int(getattr(settings, nombre, default))


class MLLPError(Exception):
    """Error específico de transporte MLLP."""


class MLLPClient:
    """
    Cliente MLLP para comunicación bidireccional con el LIS.

    Cada llamada a enviar_y_esperar_ack() abre una conexión TCP nueva,
    envía el mensaje OML^O21, espera el ACK y opcionalmente escucha ORU
    en un thread de segundo plano.

    No mantiene estado entre llamadas (stateless por diseño).
    """

    # Constantes del protocolo MLLP
    VT = b"\x0B"  # Vertical Tab — marca inicio de mensaje
    FS = b"\x1C"  # File Separator — marca fin de mensaje
    CR = b"\x0D"  # Carriage Return — terminador

    BUFFER_SIZE = 8192  # 8 KB; suficiente para ACK/ORU típicos

    # ──────────────────────────────────────────────────────────────────────────
    # API pública
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def enviar_y_esperar_ack(
        mensaje_er7: str,
        turno_id: int,
    ) -> Tuple[bool, str, str]:
        """
        Envía un mensaje HL7 OML^O21 al LIS y espera la respuesta.

        Abre una conexión TCP al LIS, envía el mensaje con wrapping MLLP,
        espera la respuesta del LIS (ORL^O22 o ACK^O21), y actualiza el
        registro Coordinados con el resultado.

        Navify/cobas infinity responde directamente con ORL^O22 (no hay
        ACK^O21 previo). Cuando se detecta ORL, se envía el ACK^O22
        correspondiente en el mismo ciclo y se lanza el listener para
        mensajes posteriores (ORU u otro ORL).

        Si el envío falla, registra en ColaReintentos.

        Args:
            mensaje_er7: Mensaje HL7 en formato ER7 (segmentos separados por \\r)
            turno_id:    ID del turno; debe existir en Coordinados

        Returns:
            (exito, ack_texto, mensaje_error)
            - exito:          True si el LIS devolvió ACK/ORL con estado AA
            - ack_texto:      Texto completo de la respuesta (o vacío si falló)
            - mensaje_error:  Descripción del error (o vacío si fue exitoso)
        """
        host = getattr(settings, "LIS_HOST", "192.168.211.128")
        puerto = _settings_int("LIS_PORT", 50000)
        timeout_conexion = _settings_int("LIS_TIMEOUT_CONEXION", 5)
        timeout_ack = _settings_int("LIS_TIMEOUT_ACK", 30)
        timeout_oru = _settings_int("LIS_TIMEOUT_ORU", 30)

        sock: Optional[socket.socket] = None

        try:
            logger.info(
                "MLLP | Conectando a LIS %s:%d para turno_id=%d",
                host,
                puerto,
                turno_id,
            )

            # 1. Abrir conexión TCP
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout_conexion)
            sock.connect((host, puerto))

            logger.info("MLLP | Conexión establecida con %s:%d", host, puerto)

            # 2. Enviar mensaje con wrapping MLLP
            datos = MLLPClient._wrap_mllp(mensaje_er7)
            sock.settimeout(timeout_ack)
            sock.sendall(datos)

            logger.info(
                "MLLP | Mensaje OML^O21 enviado (%d bytes), esperando ACK...",
                len(datos),
            )

            # 3. Recibir respuesta del LIS (puede ser ACK^O21 o directamente ORL^O22)
            # Navify/cobas infinity responde con ORL^O22 directamente (sin ACK previo).
            ack_raw = MLLPClient._recibir_mensaje(sock)
            ack_texto = MLLPClient._unwrap_mllp(ack_raw)

            # Determinar tipo de respuesta para guardar con nombre correcto
            es_orl = "ORL" in ack_texto[:200]
            tipo_recibido = "ORL" if es_orl else "ACK"
            MLLPClient._guardar_recibido(ack_texto, turno_id, tipo_recibido)

            # 4. Parsear estado (funciona tanto para ACK como para ORL, ambos tienen MSA)
            resultado_ack = HL7Parser.parsear_ack(ack_texto)

            if not resultado_ack.valido:
                raise MLLPError(
                    f"ACK inválido o no parseable: {resultado_ack.error_parsing}"
                )

            estado = resultado_ack.estado  # AA / AE / AR
            logger.info(
                "MLLP | %s recibido para turno_id=%d: estado=%s mensaje=%s",
                tipo_recibido,
                turno_id,
                estado,
                resultado_ack.mensaje,
            )

            # 5. Actualizar Coordinados
            MLLPClient._actualizar_coordinados(turno_id, ack_texto, estado)

            # 5b. Si recibimos ORL^O22 directamente, procesarlo.
            # Navify no espera ACK de nuestra parte para el ORL — enviarlo
            # causa error 42114 ("Channel ACK to IN not configured").
            if es_orl:
                resultado_orl = HL7Parser.parsear_orl(ack_texto)
                if resultado_orl.valido:
                    MLLPClient._actualizar_estado_orl(turno_id, resultado_orl)
                    logger.info(
                        "MLLP | ORL^O22 (respuesta directa) para turno_id=%d: "
                        "orden_estado=%s",
                        turno_id,
                        resultado_orl.orden_estado,
                    )
                else:
                    logger.warning(
                        "MLLP | ORL^O22 con error de parseo para turno_id=%d: %s",
                        turno_id,
                        resultado_orl.error_parsing,
                    )
                # No enviamos ACK al ORL — Navify no lo espera en esta conexión.

            # 6. Si LIS aceptó la orden: lanzar listener para mensajes adicionales
            # (por si el LIS envía ORU u otro ORL a continuación)
            if resultado_ack.aceptado:
                thread = threading.Thread(
                    target=MLLPClient._escuchar_oru_async,
                    args=(sock, turno_id, timeout_oru),
                    name=f"oru-listener-turno-{turno_id}",
                    daemon=True,
                )
                thread.start()
                # La responsabilidad de cerrar el socket pasa al thread
                sock = None

            exito = resultado_ack.aceptado
            error = "" if exito else f"LIS rechazó la orden: estado={estado} — {resultado_ack.mensaje}"
            return exito, ack_texto, error

        except socket.timeout as exc:
            msg = f"Timeout al comunicar con LIS {host}:{puerto} — {exc}"
            logger.error("MLLP | %s (turno_id=%d)", msg, turno_id)
            MLLPClient._registrar_en_cola(turno_id, mensaje_er7, msg)
            return False, "", msg

        except ConnectionRefusedError as exc:
            msg = f"LIS rechazó la conexión en {host}:{puerto} — {exc}"
            logger.error("MLLP | %s (turno_id=%d)", msg, turno_id)
            MLLPClient._registrar_en_cola(turno_id, mensaje_er7, msg)
            return False, "", msg

        except OSError as exc:
            msg = f"Error de red al conectar con LIS — {exc}"
            logger.error("MLLP | %s (turno_id=%d)", msg, turno_id)
            MLLPClient._registrar_en_cola(turno_id, mensaje_er7, msg)
            return False, "", msg

        except MLLPError as exc:
            msg = str(exc)
            logger.error("MLLP | %s (turno_id=%d)", msg, turno_id)
            MLLPClient._registrar_en_cola(turno_id, mensaje_er7, msg)
            return False, "", msg

        except Exception as exc:
            msg = f"Error inesperado en MLLP: {exc}"
            logger.exception("MLLP | %s (turno_id=%d)", msg, turno_id)
            MLLPClient._registrar_en_cola(turno_id, mensaje_er7, msg)
            return False, "", msg

        finally:
            # Cerrar socket solo si no fue cedido al thread listener
            if sock is not None:
                try:
                    sock.close()
                except OSError:
                    pass

    # ──────────────────────────────────────────────────────────────────────────
    # Wrapping / Unwrapping MLLP
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _wrap_mllp(mensaje: str) -> bytes:
        """
        Envuelve un mensaje HL7 con el protocolo MLLP.

        Formato: VT (0x0B) + mensaje_utf8 + FS (0x1C) + CR (0x0D)

        Normaliza separadores de segmento a CR (0x0D) antes de enviar.
        hl7apy puede generar \\n (LF) en lugar de \\r (CR); el estándar
        HL7 v2 exige CR como separador de segmentos.

        Args:
            mensaje: Mensaje HL7 en formato ER7 (texto plano)

        Returns:
            Bytes listos para enviar por socket
        """
        # Normalizar: reemplazar LF sueltos por CR (sin tocar CRLF existentes)
        mensaje_normalizado = mensaje.replace("\r\n", "\r").replace("\n", "\r")
        return MLLPClient.VT + mensaje_normalizado.encode("utf-8") + MLLPClient.FS + MLLPClient.CR

    @staticmethod
    def _unwrap_mllp(data: bytes) -> str:
        """
        Extrae el mensaje HL7 limpio de su envoltorio MLLP.

        Valida presencia de VT inicial y FS+CR final, luego decodifica.

        Args:
            data: Bytes crudos recibidos del socket

        Returns:
            Mensaje HL7 en formato ER7 (texto plano)

        Raises:
            MLLPError: Si el formato MLLP no es válido
        """
        if not data:
            raise MLLPError("Respuesta vacía del LIS")

        if not data.startswith(MLLPClient.VT):
            raise MLLPError(
                f"Respuesta sin VT inicial (0x0B). Primer byte: 0x{data[0]:02X}"
            )

        # Buscar FS+CR al final (pueden haber datos después del último FS+CR)
        terminador = MLLPClient.FS + MLLPClient.CR
        pos = data.rfind(terminador)
        if pos == -1:
            raise MLLPError("Respuesta sin terminador FS+CR (0x1C 0x0D)")

        # Extraer contenido entre VT y FS
        contenido = data[1:pos]
        return contenido.decode("utf-8", errors="replace")

    # ──────────────────────────────────────────────────────────────────────────
    # Recepción
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _recibir_mensaje(sock: socket.socket) -> bytes:
        """
        Lee bytes del socket hasta recibir el terminador MLLP (FS + CR).

        Usa lectura incremental para manejar mensajes que llegan en
        múltiples fragmentos TCP (chunking).

        Args:
            sock: Socket conectado con timeout ya configurado

        Returns:
            Bytes completos del mensaje MLLP (incluyendo VT y FS+CR)

        Raises:
            MLLPError: Si la conexión se cierra antes del terminador
            socket.timeout: Si se agota el timeout esperando datos
        """
        buffer = b""
        terminador = MLLPClient.FS + MLLPClient.CR

        while True:
            fragmento = sock.recv(MLLPClient.BUFFER_SIZE)
            if not fragmento:
                raise MLLPError("LIS cerró la conexión antes de enviar respuesta completa")
            buffer += fragmento
            if terminador in buffer:
                break

        return buffer

    # ──────────────────────────────────────────────────────────────────────────
    # Listener ORU (thread de segundo plano)
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _escuchar_oru_async(
        sock: socket.socket,
        turno_id: int,
        timeout: int,
    ) -> None:
        """
        Escucha mensajes ORL^O22 / ORU^R01 en la conexión existente tras recibir el ACK.

        El LIS reutiliza la misma conexión TCP para enviar resultados;
        este método corre en un thread daemon durante `timeout` segundos.

        Al recibir un ORL^O22:
          - Guarda el archivo en mensajes/hl7/recibidos/ORL_{turno_id}_{ts}.hl7
          - Parsea con HL7Parser.parsear_orl() y actualiza Coordinados.orden_estado
          - Envía ACK^O22 con MSH-3=HOST (mismo sending app que el OML original)
          - Cierra el listener (el ORL es la respuesta final de Navify)

        Al recibir un ORU^R01:
          - Guarda el archivo en mensajes/hl7/recibidos/ORU_{turno_id}_{ts}.hl7
          - Parsea con HL7Parser.parsear_oru() y logea el resumen
          - Envía ACK de confirmación al LIS (AA simple)

        Args:
            sock:     Socket TCP conectado al LIS (cedido por enviar_y_esperar_ack)
            turno_id: ID del turno, para nombre del archivo de auditoría
            timeout:  Segundos de espera; al vencer, cierra la conexión
        """
        try:
            sock.settimeout(timeout)
            logger.info(
                "MLLP | Listener ORU iniciado para turno_id=%d (timeout=%ds)",
                turno_id,
                timeout,
            )

            while True:
                try:
                    oru_raw = MLLPClient._recibir_mensaje(sock)
                except socket.timeout:
                    logger.info(
                        "MLLP | Listener ORU: timeout de %ds alcanzado para turno_id=%d",
                        timeout,
                        turno_id,
                    )
                    break
                except MLLPError as exc:
                    # Conexión cerrada por el LIS o mensaje inválido
                    logger.info(
                        "MLLP | Listener ORU: conexión cerrada para turno_id=%d (%s)",
                        turno_id,
                        exc,
                    )
                    break

                try:
                    oru_texto = MLLPClient._unwrap_mllp(oru_raw)
                except MLLPError as exc:
                    logger.warning(
                        "MLLP | Listener ORU: mensaje inválido para turno_id=%d: %s",
                        turno_id,
                        exc,
                    )
                    continue

                # Determinar tipo de mensaje recibido
                # Detectar tipo de mensaje — buscar en los primeros 200 chars del ER7
                # El MSH de Navify es largo (~130 chars) por lo que [:80] no alcanza
                if "ORL" in oru_texto[:200]:
                    tipo = "ORL"
                elif "ORU^R01" in oru_texto[:200]:
                    tipo = "ORU"
                else:
                    tipo = "MSG"

                # Guardar auditoría
                MLLPClient._guardar_recibido(oru_texto, turno_id, tipo)

                # Parsear y loguear si es ORU^R01
                if "ORU" in oru_texto[:20]:
                    resultado = HL7Parser.parsear_oru(oru_texto)
                    if resultado.valido:
                        logger.info(
                            "MLLP | ORU^R01 recibido para turno_id=%d: "
                            "paciente_dni=%s nombre=%s observaciones=%d",
                            turno_id,
                            resultado.dni_paciente,
                            resultado.nombre_paciente,
                            len(resultado.observaciones),
                        )
                    else:
                        logger.warning(
                            "MLLP | ORU^R01 con error de parseo para turno_id=%d: %s",
                            turno_id,
                            resultado.error_parsing,
                        )

                    # Enviar ACK de confirmación al LIS
                    MLLPClient._enviar_ack_oru(sock, oru_texto)

                elif tipo == "ORL":
                    resultado_orl = HL7Parser.parsear_orl(oru_texto)
                    if resultado_orl.valido:
                        logger.info(
                            "MLLP | ORL^O22 recibido para turno_id=%d: estado=%s (%s)",
                            turno_id,
                            resultado_orl.orden_estado,
                            resultado_orl.orden_estado_desc,
                        )
                        MLLPClient._actualizar_estado_orl(turno_id, resultado_orl)
                    else:
                        logger.warning(
                            "MLLP | ORL^O22 con error de parseo para turno_id=%d: %s",
                            turno_id,
                            resultado_orl.error_parsing,
                        )
                    # Enviar ACK^O22 con MSH-3=HOST para que coincida con el OML enviado.
                    # Sin este ACK Navify deja mensajes "Pendiente" en la traza.
                    MLLPClient._enviar_ack_orl(sock, oru_texto)
                    # Cerrar listener después del ORL (opción A: flujo síncrono)
                    logger.info(
                        "MLLP | Cerrando listener tras recibir ORL^O22 para turno_id=%d",
                        turno_id,
                    )
                    break

        except Exception as exc:
            logger.exception(
                "MLLP | Error inesperado en listener ORU turno_id=%d: %s",
                turno_id,
                exc,
            )
        finally:
            try:
                sock.close()
            except OSError:
                pass
            logger.info(
                "MLLP | Listener ORU finalizado para turno_id=%d", turno_id
            )

    @staticmethod
    def _enviar_ack_oru(sock: socket.socket, oru_texto: str) -> None:
        """
        Envía un ACK AA mínimo al LIS para confirmar recepción del ORU.

        Construye un ACK HL7 v2.5 simple con MSH y MSA.
        No bloquea ante fallo (el LIS ya tiene el ORU registrado).

        Args:
            sock:      Socket conectado al LIS
            oru_texto: ORU original para extraer MSH-10 (Control ID)
        """
        try:
            # Extraer Control ID del ORU para incluir en el ACK
            control_id = MLLPClient._extraer_control_id(oru_texto)
            ts = datetime.now().strftime("%Y%m%d%H%M%S")

            ack = (
                f"MSH|^~\\&|LIS|HTAL_BALESTRINI|TURNOS|HTAL_BALESTRINI|"
                f"{ts}||ACK^R01|ACK{ts}|P|2.5\r"
                f"MSA|AA|{control_id}|Mensaje recibido correctamente\r"
            )
            sock.sendall(MLLPClient._wrap_mllp(ack))
            logger.debug("MLLP | ACK ORU enviado al LIS (control_id=%s)", control_id)

        except Exception as exc:
            logger.warning("MLLP | No se pudo enviar ACK de ORU: %s", exc)

    @staticmethod
    def _enviar_ack_orl(sock: socket.socket, orl_texto: str) -> None:
        """
        Envía ACK^O22 al LIS para confirmar recepción del ORL^O22.

        CRÍTICO: Sin este ACK, Navify marca timeout y rechaza la orden
        con error ID=90 (action defined).

        Args:
            sock: Socket TCP conectado al LIS
            orl_texto: Mensaje ORL^O22 recibido (para extraer control ID)
        """
        try:
            control_id = MLLPClient._extraer_control_id(orl_texto)
            ts = datetime.now().strftime("%Y%m%d%H%M%S")
            # MSH-3 debe coincidir con el SendingApplication del OML (HOST),
            # de lo contrario Navify rechaza con error 42114 (unknown application).
            # MSH-9: usar tipo genérico ACK (no ACK^O22) para coincidir con el
            # canal "HL7-AMBU Rec. ACK" configurado en cobas infinity.
            ack = (
                f"MSH|^~\\&|HOST|HTAL_BALESTRINI|LIS|ROCHE|{ts}||ACK|ACK{ts}|P|2.5\r"
                f"MSA|AA|{control_id}\r"
            )
            ack_wrapped = MLLPClient._wrap_mllp(ack)
            sock.sendall(ack_wrapped)
            logger.info(
                "MLLP | ACK^O22 enviado al LIS (control_id=%s)", control_id
            )
        except Exception as exc:
            logger.warning(
                "MLLP | Falló envío de ACK^O22: %s"
                " (no crítico, orden puede quedar en estado UA)",
                exc,
            )

    @staticmethod
    def _actualizar_estado_orl(turno_id: int, resultado: ResultadoORL) -> None:
        """
        Actualiza el registro Coordinados con el estado de la orden del ORL^O22.

        Guarda el control_id del ORL y el estado de la orden (UA/IP/CM/SC).

        Args:
            turno_id: ID del turno coordinado
            resultado: ResultadoORL parseado con estado y control_id
        """
        try:
            from turnos.models import Coordinados

            coord = Coordinados.objects.filter(id_turno=turno_id).first()
            if coord:
                coord.orl_recibido = resultado.mensaje_control_id
                coord.orden_estado = resultado.orden_estado
                coord.save(update_fields=["orl_recibido", "orden_estado"])
                logger.info(
                    "MLLP | Coordinados actualizado turno_id=%d: orden_estado=%s",
                    turno_id,
                    resultado.orden_estado,
                )
            else:
                logger.warning(
                    "MLLP | No se encontró Coordinados con id_turno=%d"
                    " para actualizar estado ORL",
                    turno_id,
                )
        except Exception as exc:
            logger.warning(
                "MLLP | Error al actualizar estado ORL para turno_id=%d: %s",
                turno_id,
                exc,
            )

    @staticmethod
    def _extraer_control_id(mensaje: str) -> str:
        """
        Extrae MSH-10 (Message Control ID) de un mensaje HL7.

        Parseo manual para evitar dependencia de hl7apy en el ACK de ORU.

        Args:
            mensaje: Mensaje HL7 en formato ER7

        Returns:
            Control ID o cadena vacía si no se pudo extraer
        """
        try:
            for linea in mensaje.split("\r"):
                if linea.startswith("MSH"):
                    campos = linea.split("|")
                    # MSH-10 está en índice 9 (MSH-1=|, MSH-2=^~\& → índices 1,2)
                    return campos[9] if len(campos) > 9 else ""
        except Exception:
            pass
        return ""

    # ──────────────────────────────────────────────────────────────────────────
    # Persistencia
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _actualizar_coordinados(turno_id: int, ack_texto: str, estado: str) -> None:
        """
        Actualiza el registro Coordinados con el ACK recibido del LIS.

        Args:
            turno_id:  ID del turno
            ack_texto: Texto completo del ACK en formato ER7
            estado:    Código de estado ACK (AA / AE / AR)
        """
        # Import diferido para evitar importaciones circulares en tests
        from turnos.models import Coordinados

        actualizados = Coordinados.objects.filter(id_turno=turno_id).update(
            ack_recibido=ack_texto,
            ack_estado=estado,
        )
        if actualizados == 0:
            logger.warning(
                "MLLP | No se encontró Coordinados con id_turno=%d para actualizar ACK",
                turno_id,
            )
        else:
            logger.debug(
                "MLLP | Coordinados actualizado: id_turno=%d ack_estado=%s",
                turno_id,
                estado,
            )

    @staticmethod
    def _registrar_en_cola(
        turno_id: int,
        mensaje_er7: str,
        error: str,
    ) -> None:
        """
        Registra un mensaje fallido en ColaReintentos para procesamiento posterior.

        No falla silenciosamente: si no puede guardar en BD, logea el error
        para que el operador lo detecte.

        Args:
            turno_id:    ID del turno
            mensaje_er7: Mensaje HL7 completo a reenviar
            error:       Descripción del error que causó el fallo
        """
        from turnos.models import ColaReintentos

        try:
            ColaReintentos.objects.create(
                turno_id=turno_id,
                mensaje_hl7=mensaje_er7,
                intentos=1,
                ultimo_error=error[:2000],  # Limitar para no saturar la columna
                fecha_ultimo_intento=timezone.now(),
            )
            logger.info(
                "MLLP | Mensaje de turno_id=%d registrado en ColaReintentos",
                turno_id,
            )
        except Exception as exc:
            logger.critical(
                "MLLP | CRÍTICO: No se pudo registrar turno_id=%d en ColaReintentos: %s",
                turno_id,
                exc,
            )

    @staticmethod
    def _guardar_recibido(
        mensaje: str,
        turno_id: int,
        tipo: str,
    ) -> None:
        """
        Guarda un mensaje HL7 recibido en mensajes/hl7/recibidos/ para auditoría.

        Nombre del archivo: {TIPO}_{turno_id}_{YYYYMMDDHHMMSS}.hl7
        Ejemplo: ACK_123_20260515143022.hl7

        No falla ante errores de escritura (solo logea warning).

        Args:
            mensaje:  Texto completo del mensaje HL7 en formato ER7
            turno_id: ID del turno (para nombre del archivo)
            tipo:     Prefijo del archivo (ej: "ACK", "ORU")
        """
        try:
            base_dir = getattr(settings, "BASE_DIR", ".")
            carpeta = os.path.join(base_dir, "mensajes", "hl7", "recibidos")
            os.makedirs(carpeta, exist_ok=True)

            ts = datetime.now().strftime("%Y%m%d%H%M%S")
            nombre = f"{tipo}_{turno_id}_{ts}.hl7"
            ruta = os.path.join(carpeta, nombre)

            with open(ruta, "w", encoding="utf-8") as f:
                f.write(mensaje)

            logger.debug(
                "MLLP | Mensaje %s guardado en auditoría: %s", tipo, ruta
            )
        except Exception as exc:
            logger.warning(
                "MLLP | No se pudo guardar auditoría de %s para turno_id=%d: %s",
                tipo,
                turno_id,
                exc,
            )
