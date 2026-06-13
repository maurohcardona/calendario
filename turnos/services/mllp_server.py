"""
Servidor MLLP permanente para recepción de mensajes HL7 entrantes del LIS.

Protocolo MLLP (Minimal Lower Layer Protocol):
  - VT (0x0B) + mensaje HL7 + FS (0x1C) + CR (0x0D)

El servidor escucha en 0.0.0.0:{MLLP_SERVER_PORT} y acepta múltiples
conexiones concurrentes. Por cada conexión:
  1. Lee el mensaje MLLP completo usando el mismo unwrapping del cliente
  2. Detecta el tipo de mensaje (MSH-9): ORU^R01, ORL^O22, u otro
  3. Responde con ACK HL7 inmediatamente
  4. Guarda el mensaje raw en mensajes/hl7/recibidos/
  5. Si es ORU^R01: parsea y actualiza Coordinados

Iniciar con:
  python manage.py iniciar_servidor_mllp [--puerto XXXX]

Configuración (.env):
  MLLP_SERVER_PORT  Puerto TCP de escucha (default: 50001)
"""

import logging
import os
import socket
import threading
from datetime import datetime
from typing import Optional

import django
from django.conf import settings

logger = logging.getLogger("turnos.services")

# ──────────────────────────────────────────────────────────────────────────────
# Constantes MLLP (idénticas al cliente para compatibilidad)
# ──────────────────────────────────────────────────────────────────────────────
VT = b"\x0B"           # Vertical Tab — inicio de mensaje
FS = b"\x1C"           # File Separator — fin de mensaje
CR = b"\x0D"           # Carriage Return — terminador
TERMINADOR = FS + CR   # FS + CR — terminador MLLP completo
BUFFER_SIZE = 8192     # 8 KB por fragmento TCP


class MLLPServerError(Exception):
    """Error específico del servidor MLLP."""


# ──────────────────────────────────────────────────────────────────────────────
# Helpers de bajo nivel (reutilizan misma lógica que MLLPClient)
# ──────────────────────────────────────────────────────────────────────────────

def _wrap_mllp(mensaje: str) -> bytes:
    """
    Envuelve un mensaje HL7 en el protocolo MLLP.

    Normaliza separadores de segmento a CR antes de enviar.

    Args:
        mensaje: Mensaje HL7 en formato ER7 (texto plano)

    Returns:
        Bytes listos para enviar por socket
    """
    mensaje_normalizado = mensaje.replace("\r\n", "\r").replace("\n", "\r")
    return VT + mensaje_normalizado.encode("utf-8") + FS + CR


def _unwrap_mllp(data: bytes) -> str:
    """
    Extrae el mensaje HL7 limpio de su envoltorio MLLP.

    Args:
        data: Bytes crudos recibidos del socket

    Returns:
        Mensaje HL7 en formato ER7 (texto plano)

    Raises:
        MLLPServerError: Si el formato MLLP no es válido
    """
    if not data:
        raise MLLPServerError("Mensaje vacío recibido")

    if not data.startswith(VT):
        raise MLLPServerError(
            f"Mensaje sin VT inicial (0x0B). Primer byte: 0x{data[0]:02X}"
        )

    pos = data.rfind(TERMINADOR)
    if pos == -1:
        raise MLLPServerError("Mensaje sin terminador FS+CR (0x1C 0x0D)")

    contenido = data[1:pos]
    return contenido.decode("utf-8", errors="replace")


def _recibir_mensaje(sock: socket.socket) -> bytes:
    """
    Lee bytes del socket hasta recibir el terminador MLLP completo (FS + CR).

    Lectura incremental para manejar fragmentación TCP.

    Args:
        sock: Socket conectado con timeout ya configurado

    Returns:
        Bytes completos del mensaje MLLP (incluyendo VT y FS+CR)

    Raises:
        MLLPServerError: Si la conexión se cierra antes del terminador
        socket.timeout: Si se agota el timeout esperando datos
    """
    buffer = b""

    while True:
        fragmento = sock.recv(BUFFER_SIZE)
        if not fragmento:
            raise MLLPServerError("Cliente cerró la conexión antes de terminar el mensaje")
        buffer += fragmento
        if TERMINADOR in buffer:
            break

    return buffer


def _extraer_tipo_mensaje(mensaje_er7: str) -> str:
    """
    Detecta el tipo de mensaje desde MSH-9.

    Lee los primeros 300 caracteres del ER7 para localizar el tipo
    sin parsear el mensaje completo (más eficiente y resiliente).

    Args:
        mensaje_er7: Mensaje HL7 en formato ER7

    Returns:
        Tipo de mensaje: 'ORU^R01', 'ORL^O22', 'ACK', u 'OTRO'
    """
    encabezado = mensaje_er7[:300]
    if "ORU^R01" in encabezado:
        return "ORU^R01"
    if "ORL^O22" in encabezado or "ORL" in encabezado[:200]:
        return "ORL^O22"
    if "ACK" in encabezado[:100]:
        return "ACK"
    return "OTRO"


def _extraer_control_id(mensaje_er7: str) -> str:
    """
    Extrae MSH-10 (Message Control ID) de un mensaje HL7.

    Parseo manual para evitar dependencia de hl7apy en el ACK.

    Args:
        mensaje_er7: Mensaje HL7 en formato ER7

    Returns:
        Control ID o cadena vacía si no se pudo extraer
    """
    try:
        for linea in mensaje_er7.split("\r"):
            if linea.startswith("MSH"):
                campos = linea.split("|")
                return campos[9] if len(campos) > 9 else ""
    except Exception:
        pass
    return ""


def _guardar_recibido(mensaje: str, tipo: str, identificador: str = "srv") -> None:
    """
    Guarda un mensaje HL7 recibido en mensajes/hl7/recibidos/ para auditoría.

    Nombre del archivo: {TIPO}_{identificador}_{YYYYMMDDHHMMSS}.hl7
    Ejemplo: ORU_srv_20260525143022.hl7

    No lanza excepciones — fallo silencioso para no interrumpir el flujo.

    Args:
        mensaje:       Texto completo del mensaje HL7 en formato ER7
        tipo:          Prefijo del archivo (ej: "ORU", "ORL", "ACK")
        identificador: Identificador adicional (turno_id o 'srv')
    """
    try:
        base_dir = getattr(settings, "BASE_DIR", ".")
        carpeta = os.path.join(base_dir, "mensajes", "hl7", "recibidos")
        os.makedirs(carpeta, exist_ok=True)

        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        nombre = f"{tipo}_{identificador}_{ts}.hl7"
        ruta = os.path.join(carpeta, nombre)

        with open(ruta, "w", encoding="utf-8") as f:
            f.write(mensaje)

        logger.debug("MLLP-SRV | Mensaje %s guardado: %s", tipo, ruta)
    except Exception as exc:
        logger.warning(
            "MLLP-SRV | No se pudo guardar auditoría de %s: %s", tipo, exc
        )


def _construir_ack(mensaje_er7: str, estado: str = "AA") -> str:
    """
    Construye un ACK HL7 v2.5 para responder al LIS, adaptado para Navify.

    Formato Navify:
      - MSH-3=HOST, MSH-4=vacío, MSH-5=LIS, MSH-6=vacío
      - MSA-1=CA (Commit Accept) para éxito, AE para error

    Args:
        mensaje_er7: Mensaje original (para extraer el control ID)
        estado:      Estado del ACK: 'AA' (aceptado) o 'AE' (error)

    Returns:
        Mensaje ACK en formato ER7 con separadores CR
    """
    control_id = _extraer_control_id(mensaje_er7)
    ts = datetime.now().strftime("%Y%m%d%H%M%S")

    # Mapear estado genérico a estado específico de Navify
    estado_msa = "CA" if estado == "AA" else "AE"

    ack = (
        f"MSH|^~\\&|HOST||LIS||{ts}||ACK^R01\r"
        f"MSA|{estado_msa}|{control_id}\r"
    )
    return ack


# ──────────────────────────────────────────────────────────────────────────────
# Procesamiento de mensajes
# ──────────────────────────────────────────────────────────────────────────────

def _procesar_oru(mensaje_er7: str) -> None:
    """
    Procesa un ORU^R01 recibido del LIS.

    Extrae el Placer Order Number (turno_id) y el Filler Order Number
    (número de protocolo del LIS), busca el Coordinados correspondiente
    y actualiza los campos oru_recibido y numero_protocolo_lis.

    Import diferido de modelos para evitar problemas con el setup de Django
    en contexto de management command o threading.

    Args:
        mensaje_er7: Mensaje ORU^R01 en formato ER7
    """
    try:
        from turnos.models import Coordinados
        from turnos.services.hl7_parser import HL7Parser

        resultado = HL7Parser.parsear_oru(mensaje_er7)

        if not resultado.valido:
            logger.warning(
                "MLLP-SRV | ORU^R01 con error de parseo: %s", resultado.error_parsing
            )
            return

        # Extraer turno_id (OBR-2 / Placer Order Number) — lo ecoa Navify desde el OML
        turno_id_raw = resultado.turno_id
        if not turno_id_raw:
            logger.warning("MLLP-SRV | ORU^R01 sin Placer Order Number (OBR-2)")
            return

        try:
            turno_id = int(turno_id_raw.split("^")[0])
        except (ValueError, TypeError):
            logger.warning(
                "MLLP-SRV | ORU^R01 con turno_id no numérico: %r", turno_id_raw
            )
            return

        # Extraer Filler Order Number (OBR-3) — número de protocolo del LIS
        numero_protocolo_lis = _extraer_filler_order_number(mensaje_er7)

        actualizado = Coordinados.objects.filter(id_turno=turno_id).update(
            oru_recibido=mensaje_er7,
            numero_protocolo_lis=numero_protocolo_lis,
        )

        if actualizado == 0:
            logger.warning(
                "MLLP-SRV | ORU^R01: no se encontró Coordinados con id_turno=%d",
                turno_id,
            )
        else:
            logger.info(
                "MLLP-SRV | ORU^R01 procesado: turno_id=%d numero_protocolo_lis=%r "
                "paciente=%s observaciones=%d",
                turno_id,
                numero_protocolo_lis,
                resultado.nombre_paciente,
                len(resultado.observaciones),
            )

    except Exception as exc:
        logger.exception("MLLP-SRV | Error inesperado procesando ORU^R01: %s", exc)


def _extraer_filler_order_number(mensaje_er7: str) -> str:
    """
    Extrae OBR-3 (Filler Order Number) de un mensaje HL7.

    El Filler Order Number es el número de protocolo que el LIS asigna
    a la orden (distinto del Placer Order Number que nosotros generamos).

    Args:
        mensaje_er7: Mensaje HL7 en formato ER7

    Returns:
        Filler Order Number (primer componente) o cadena vacía
    """
    try:
        for linea in mensaje_er7.split("\r"):
            if linea.startswith("OBR"):
                campos = linea.split("|")
                # OBR-3 está en índice 3
                obr3 = campos[3] if len(campos) > 3 else ""
                # Tomar solo el primer componente (puede ser NUMERO^NAMESPACE)
                return obr3.split("^")[0].strip()
    except Exception:
        pass
    return ""


def _extraer_orc3(mensaje_er7: str) -> str:
    """
    Extrae ORC-3 (Filler Order Number) de un mensaje HL7.

    En el ORL^O22 de Navify, ORC-3 contiene el número de protocolo
    interno asignado por el LIS a la orden.

    Args:
        mensaje_er7: Mensaje HL7 en formato ER7

    Returns:
        Filler Order Number (primer componente) o cadena vacía
    """
    try:
        for linea in mensaje_er7.split("\r"):
            if linea.startswith("ORC"):
                campos = linea.split("|")
                # ORC-3 está en índice 3
                orc3 = campos[3] if len(campos) > 3 else ""
                return orc3.split("^")[0].strip()
    except Exception:
        pass
    return ""


def _procesar_orl(mensaje_er7: str) -> None:
    """
    Procesa un ORL^O22 recibido del LIS (Laboratory Order Response).

    Parsea el estado de la orden y actualiza Coordinados.

    Args:
        mensaje_er7: Mensaje ORL^O22 en formato ER7
    """
    try:
        from turnos.models import Coordinados
        from turnos.services.hl7_parser import HL7Parser

        resultado = HL7Parser.parsear_orl(mensaje_er7)

        if not resultado.valido:
            logger.warning(
                "MLLP-SRV | ORL^O22 con error de parseo: %s", resultado.error_parsing
            )
            return

        if not resultado.turno_id:
            logger.warning("MLLP-SRV | ORL^O22 sin turno_id (ORC-2)")
            return

        try:
            turno_id = int(resultado.turno_id.split("^")[0])
        except (ValueError, TypeError):
            logger.warning(
                "MLLP-SRV | ORL^O22 con turno_id no numérico: %r", resultado.turno_id
            )
            return

        # Extraer Filler Order Number (ORC-3) — número de protocolo del LIS
        numero_protocolo_lis = _extraer_orc3(mensaje_er7)

        campos_update = dict(
            orl_recibido=mensaje_er7,
            orden_estado=resultado.orden_estado,
        )
        if numero_protocolo_lis:
            campos_update["numero_protocolo_lis"] = numero_protocolo_lis

        actualizado = Coordinados.objects.filter(id_turno=turno_id).update(
            **campos_update
        )

        if actualizado == 0:
            logger.warning(
                "MLLP-SRV | ORL^O22: no se encontró Coordinados con id_turno=%d",
                turno_id,
            )
        else:
            logger.info(
                "MLLP-SRV | ORL^O22 procesado: turno_id=%d estado=%s (%s) "
                "numero_protocolo_lis=%r",
                turno_id,
                resultado.orden_estado,
                resultado.orden_estado_desc,
                numero_protocolo_lis,
            )

    except Exception as exc:
        logger.exception("MLLP-SRV | Error inesperado procesando ORL^O22: %s", exc)


# ──────────────────────────────────────────────────────────────────────────────
# Handler de conexión (se ejecuta en thread por cada cliente)
# ──────────────────────────────────────────────────────────────────────────────

def _manejar_conexion(conn: socket.socket, addr: tuple) -> None:
    """
    Maneja una conexión entrante del LIS.

    Corre en un thread daemon independiente. Procesa todos los mensajes
    que lleguen en la conexión hasta que el cliente la cierre o haya
    un error irrecuperable.

    Args:
        conn: Socket de la conexión aceptada
        addr: Tupla (host, puerto) del cliente (el LIS)
    """
    host_cliente = f"{addr[0]}:{addr[1]}"
    logger.info("MLLP-SRV | Conexión entrante de %s", host_cliente)

    try:
        conn.settimeout(120)  # 2 minutos de inactividad máxima

        while True:
            # 1. Leer mensaje MLLP completo
            try:
                raw = _recibir_mensaje(conn)
            except socket.timeout:
                logger.info(
                    "MLLP-SRV | Timeout de inactividad para %s — cerrando", host_cliente
                )
                break
            except MLLPServerError as exc:
                logger.info(
                    "MLLP-SRV | Conexión cerrada por %s: %s", host_cliente, exc
                )
                break

            # 2. Unwrap MLLP
            try:
                mensaje_er7 = _unwrap_mllp(raw)
            except MLLPServerError as exc:
                logger.warning(
                    "MLLP-SRV | Mensaje MLLP inválido de %s: %s", host_cliente, exc
                )
                # Enviar ACK de error y continuar escuchando
                try:
                    ack_error = _construir_ack("", estado="AE")
                    conn.sendall(_wrap_mllp(ack_error))
                except Exception:
                    pass
                continue

            # 3. Detectar tipo de mensaje
            tipo = _extraer_tipo_mensaje(mensaje_er7)
            logger.info(
                "MLLP-SRV | Mensaje recibido de %s: tipo=%s largo=%d chars",
                host_cliente,
                tipo,
                len(mensaje_er7),
            )

            # 4. Guardar auditoría antes de responder
            # Intenta extraer turno_id para nombre de archivo más descriptivo
            turno_id_audit = "srv"
            try:
                for linea in mensaje_er7.split("\r"):
                    if linea.startswith("OBR"):
                        campos = linea.split("|")
                        turno_id_audit = campos[2].split("^")[0] if len(campos) > 2 else "srv"
                        break
            except Exception:
                pass
            _guardar_recibido(mensaje_er7, tipo.replace("^", "_"), turno_id_audit)

            # 5. Responder con ACK inmediato
            try:
                ack = _construir_ack(mensaje_er7, estado="AA")
                conn.sendall(_wrap_mllp(ack))
                logger.debug(
                    "MLLP-SRV | ACK AA enviado a %s para mensaje %s", host_cliente, tipo
                )
            except Exception as exc:
                logger.error(
                    "MLLP-SRV | No se pudo enviar ACK a %s: %s", host_cliente, exc
                )
                break

            # 6. Procesar según tipo (en el mismo thread — DB ops son rápidas)
            if tipo == "ORU^R01":
                _procesar_oru(mensaje_er7)
            elif tipo == "ORL^O22":
                _procesar_orl(mensaje_er7)
            else:
                logger.info(
                    "MLLP-SRV | Tipo de mensaje '%s' recibido de %s — solo auditoría",
                    tipo,
                    host_cliente,
                )

    except Exception as exc:
        logger.exception(
            "MLLP-SRV | Error inesperado manejando conexión de %s: %s", host_cliente, exc
        )
    finally:
        try:
            conn.close()
        except OSError:
            pass
        logger.info("MLLP-SRV | Conexión cerrada: %s", host_cliente)


# ──────────────────────────────────────────────────────────────────────────────
# Servidor principal
# ──────────────────────────────────────────────────────────────────────────────

class MLLPServer:
    """
    Servidor MLLP permanente para recepción de mensajes HL7 del LIS.

    Escucha en 0.0.0.0:{puerto} y acepta múltiples conexiones concurrentes
    usando un thread daemon por conexión. El servidor en sí corre en un
    thread daemon al llamar a iniciar().

    Uso desde management command:
        servidor = MLLPServer(puerto=50001)
        servidor.iniciar()   # no bloquea — arranca thread daemon
        # ... loop principal del command ...
        servidor.detener()

    No mantiene estado de las conexiones individuales.
    """

    def __init__(self, puerto: Optional[int] = None) -> None:
        """
        Inicializa el servidor MLLP.

        Args:
            puerto: Puerto TCP de escucha. Si es None, usa MLLP_SERVER_PORT
                    de settings (default 50001).
        """
        if puerto is not None:
            self.puerto = puerto
        else:
            self.puerto = int(getattr(settings, "MLLP_SERVER_PORT", 50001))

        self._servidor_socket: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._activo = False

    def iniciar(self) -> None:
        """
        Arranca el servidor en un thread daemon.

        Abre el socket de escucha y lanza el loop en segundo plano.
        No bloquea — retorna inmediatamente.

        Raises:
            OSError: Si el puerto ya está en uso o no hay permisos
        """
        self._servidor_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._servidor_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._servidor_socket.bind(("0.0.0.0", self.puerto))
        self._servidor_socket.listen(10)
        self._activo = True

        self._thread = threading.Thread(
            target=self._loop_aceptar,
            name="mllp-server",
            daemon=True,
        )
        self._thread.start()

        logger.info(
            "MLLP-SRV | Servidor MLLP escuchando en puerto %d", self.puerto
        )

    def detener(self) -> None:
        """
        Detiene el servidor cerrando el socket de escucha.

        Las conexiones activas en sus threads no se interrumpen;
        finalizarán naturalmente por timeout o cierre del cliente.
        """
        self._activo = False
        if self._servidor_socket is not None:
            try:
                self._servidor_socket.close()
            except OSError:
                pass
            self._servidor_socket = None
        logger.info("MLLP-SRV | Servidor MLLP detenido")

    def _loop_aceptar(self) -> None:
        """
        Loop principal del servidor: acepta conexiones e inicia un thread por cada una.

        Corre en el thread daemon 'mllp-server' hasta que _activo sea False
        o el socket sea cerrado.
        """
        logger.info(
            "MLLP-SRV | Loop de aceptación iniciado en puerto %d", self.puerto
        )
        while self._activo:
            try:
                conn, addr = self._servidor_socket.accept()
            except OSError:
                # Socket cerrado por detener() — salir del loop limpiamente
                if self._activo:
                    logger.error("MLLP-SRV | Error al aceptar conexión — servidor detenido")
                break

            hilo = threading.Thread(
                target=_manejar_conexion,
                args=(conn, addr),
                name=f"mllp-conn-{addr[0]}-{addr[1]}",
                daemon=True,
            )
            hilo.start()
            logger.debug(
                "MLLP-SRV | Thread %s iniciado para conexión de %s:%d",
                hilo.name,
                addr[0],
                addr[1],
            )

        logger.info("MLLP-SRV | Loop de aceptación finalizado")
