"""
Management command para iniciar el servidor MLLP permanente.

El servidor escucha conexiones entrantes del LIS (Navify/Roche) y recibe
mensajes HL7 ORU^R01 y ORL^O22, actualizando el modelo Coordinados
con los datos recibidos.

Uso:
    python manage.py iniciar_servidor_mllp
    python manage.py iniciar_servidor_mllp --puerto 50001

El proceso queda activo hasta recibir Ctrl+C o SIGTERM.
"""

import logging
import time

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from turnos.services.mllp_server import MLLPServer

logger = logging.getLogger("turnos.services")


class Command(BaseCommand):
    """Inicia el servidor MLLP permanente para recibir mensajes HL7 del LIS."""

    help = (
        "Inicia el servidor MLLP que escucha conexiones entrantes del LIS (Navify). "
        "Procesa mensajes ORU^R01 y ORL^O22 y actualiza el modelo Coordinados."
    )

    def add_arguments(self, parser) -> None:
        """Define argumentos opcionales del comando."""
        parser.add_argument(
            "--puerto",
            type=int,
            default=None,
            help=(
                "Puerto TCP en el que escucha el servidor MLLP. "
                f"Por defecto usa MLLP_SERVER_PORT de settings "
                f"(actualmente: {getattr(settings, 'MLLP_SERVER_PORT', 50001)})."
            ),
        )

    def handle(self, *args, **options) -> None:
        """
        Arranca el servidor MLLP y mantiene el proceso activo.

        El servidor corre en un thread daemon; este loop principal
        mantiene el proceso vivo y permite interceptar Ctrl+C para
        un apagado limpio.
        """
        puerto = options.get("puerto") or getattr(settings, "MLLP_SERVER_PORT", 50001)

        self.stdout.write(
            self.style.NOTICE(f"Iniciando servidor MLLP en puerto {puerto}...")
        )

        servidor = MLLPServer(puerto=puerto)

        try:
            servidor.iniciar()
        except OSError as exc:
            raise CommandError(
                f"No se pudo iniciar el servidor MLLP en puerto {puerto}: {exc}\n"
                f"Verificá que el puerto esté libre y que tengas permisos suficientes."
            ) from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Servidor MLLP escuchando en puerto {puerto}. "
                f"Presioná Ctrl+C para detener."
            )
        )
        logger.info("MLLP-SRV | Servidor iniciado desde management command en puerto %d", puerto)

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("\nDeteniendo servidor MLLP..."))
            servidor.detener()
            self.stdout.write(self.style.SUCCESS("Servidor MLLP detenido."))
            logger.info("MLLP-SRV | Servidor detenido por KeyboardInterrupt")
