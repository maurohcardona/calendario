"""
Comando para procesar la cola de mensajes HL7 que fallaron al enviarse al LIS.

Uso:
    python manage.py procesar_cola_hl7

Configurar en cron para ejecución automática cada 5 minutos:
    */5 * * * * cd /ruta/proyecto && .venv/bin/python manage.py procesar_cola_hl7 >> /var/log/hl7_reintentos.log 2>&1

Flujo por cada mensaje en cola:
  1. Intenta reenviar por MLLP al LIS
  2. Si exitoso → elimina el registro de la cola
  3. Si falla → incrementa intentos y actualiza ultimo_error
  4. Si intentos >= LIS_MAX_REINTENTOS → mueve a mensajes/hl7/error/ y elimina de cola
"""

import logging
import os
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from turnos.models import ColaReintentos
from turnos.services.mllp_client import MLLPClient

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Procesa la cola de mensajes HL7 pendientes de envío al LIS."""

    help = "Procesa la cola de mensajes HL7 que fallaron al enviarse al LIS por MLLP"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Muestra los mensajes en cola sin procesarlos",
        )

    def handle(self, *args, **options):
        """Punto de entrada del comando."""
        max_reintentos = getattr(settings, "LIS_MAX_REINTENTOS", 3)
        dry_run = options.get("dry_run", False)

        if dry_run:
            self._mostrar_cola(max_reintentos)
            return

        self._procesar_cola(max_reintentos)

    # ──────────────────────────────────────────────────────────────────────────
    # Lógica principal
    # ──────────────────────────────────────────────────────────────────────────

    def _procesar_cola(self, max_reintentos: int) -> None:
        """
        Itera los mensajes en cola y reintenta enviarlos al LIS.

        Args:
            max_reintentos: Máximo de intentos antes de descartar permanentemente
        """
        pendientes = ColaReintentos.objects.filter(
            intentos__lt=max_reintentos
        ).order_by("fecha_creacion")

        total = pendientes.count()

        if total == 0:
            self.stdout.write("No hay mensajes en cola para procesar.")
            logger.info("procesar_cola_hl7 | Cola vacía, nada que procesar")
            return

        self.stdout.write(
            self.style.WARNING(f"Procesando {total} mensaje(s) en cola...")
        )
        logger.info("procesar_cola_hl7 | Iniciando procesamiento de %d mensajes", total)

        exitosos = 0
        fallidos = 0

        for item in pendientes:
            self.stdout.write(
                f"  → Turno {item.turno_id} (intento {item.intentos + 1}/{max_reintentos})... ",
                ending="",
            )

            enviado, ack_texto, error = MLLPClient.enviar_y_esperar_ack(
                item.mensaje_hl7,
                item.turno_id,
            )

            if enviado:
                self.stdout.write(self.style.SUCCESS("OK"))
                logger.info(
                    "procesar_cola_hl7 | Turno %d reenviado exitosamente", item.turno_id
                )
                # Eliminar de la cola al tener éxito
                item.delete()
                exitosos += 1
            else:
                # El propio MLLPClient ya actualizó ColaReintentos si es un reintento
                # desde la vista; acá lo que hacemos es incrementar para los registros
                # que ya estaban en cola.
                nuevos_intentos = item.intentos + 1

                if nuevos_intentos >= max_reintentos:
                    # Error permanente: mover a carpeta de error y eliminar de cola
                    self.stdout.write(
                        self.style.ERROR(f"PERMANENTE ({nuevos_intentos} intentos)")
                    )
                    self._mover_a_error(item)
                    item.delete()
                    logger.error(
                        "procesar_cola_hl7 | Turno %d descartado tras %d intentos: %s",
                        item.turno_id,
                        nuevos_intentos,
                        error,
                    )
                else:
                    self.stdout.write(self.style.ERROR(f"FALLÓ: {error[:60]}"))
                    item.intentos = nuevos_intentos
                    item.ultimo_error = error[:2000]
                    item.fecha_ultimo_intento = timezone.now()
                    item.save()
                    logger.warning(
                        "procesar_cola_hl7 | Turno %d falló (intento %d/%d): %s",
                        item.turno_id,
                        nuevos_intentos,
                        max_reintentos,
                        error,
                    )

                fallidos += 1

        resumen = f"Completado: {exitosos} exitosos, {fallidos} fallidos de {total} total."
        self.stdout.write(self.style.SUCCESS(resumen))
        logger.info("procesar_cola_hl7 | %s", resumen)

    # ──────────────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _mover_a_error(self, item: ColaReintentos) -> None:
        """
        Guarda el mensaje en mensajes/hl7/error/ para revisión manual.

        El archivo incluye el último error en un comentario de cabecera
        para facilitar el diagnóstico.

        Args:
            item: Registro de ColaReintentos a persistir como error permanente
        """
        try:
            base_dir = getattr(settings, "BASE_DIR", ".")
            carpeta = os.path.join(base_dir, "mensajes", "hl7", "error")
            os.makedirs(carpeta, exist_ok=True)

            ts = datetime.now().strftime("%Y%m%d%H%M%S")
            nombre = f"ERROR_turno{item.turno_id}_{ts}.hl7"
            ruta = os.path.join(carpeta, nombre)

            cabecera = (
                f"# MENSAJE CON ERROR PERMANENTE\n"
                f"# Turno ID: {item.turno_id}\n"
                f"# Intentos: {item.intentos}\n"
                f"# Fecha creación: {item.fecha_creacion}\n"
                f"# Último error: {item.ultimo_error}\n"
                f"# ─────────────────────────────────────────────\n"
            )

            with open(ruta, "w", encoding="utf-8") as f:
                f.write(cabecera)
                f.write(item.mensaje_hl7)

            self.stdout.write(f"    Guardado en: {ruta}")
            logger.info(
                "procesar_cola_hl7 | Mensaje de turno %d movido a error: %s",
                item.turno_id,
                ruta,
            )

        except Exception as exc:
            logger.error(
                "procesar_cola_hl7 | No se pudo mover turno %d a carpeta error: %s",
                item.turno_id,
                exc,
            )

    def _mostrar_cola(self, max_reintentos: int) -> None:
        """
        Muestra el estado actual de la cola sin procesar nada (--dry-run).

        Args:
            max_reintentos: Para calcular cuántos están próximos al límite
        """
        todos = ColaReintentos.objects.order_by("fecha_creacion")
        total = todos.count()

        if total == 0:
            self.stdout.write("Cola vacía.")
            return

        self.stdout.write(f"\n{'─' * 60}")
        self.stdout.write(f"COLA DE REINTENTOS HL7 — {total} mensaje(s)\n")

        for item in todos:
            estado = (
                self.style.ERROR("CRÍTICO")
                if item.intentos >= max_reintentos - 1
                else self.style.WARNING(f"intento {item.intentos}/{max_reintentos}")
            )
            self.stdout.write(
                f"  Turno {item.turno_id:>6} | {estado} | "
                f"Creado: {item.fecha_creacion.strftime('%Y-%m-%d %H:%M')} | "
                f"Error: {item.ultimo_error[:50]}"
            )

        self.stdout.write(f"{'─' * 60}\n")
