"""
Management command para iniciar el monitoreo en tiempo real de PDFs de Navify.

Usa watchdog para escuchar eventos del filesystem sobre INFORMES_PENDIENTES_DIR.
Este comando es persistente: queda corriendo hasta que se interrumpa con Ctrl+C
o se detenga el proceso.

Uso:
    python manage.py monitorear_informes

En producción, manejar con systemd o supervisor para reinicio automático.
"""

import time

from django.conf import settings
from django.core.management.base import BaseCommand
from watchdog.observers import Observer

from informes.pdf_monitor_service import PDFInformeEventHandler


class Command(BaseCommand):
    help = "Inicia el monitoreo en tiempo real de PDFs de Navify usando watchdog."

    def handle(self, *args, **options):
        carpeta = getattr(settings, "INFORMES_PENDIENTES_DIR", None)

        if not carpeta:
            self.stderr.write(
                self.style.ERROR(
                    "INFORMES_PENDIENTES_DIR no está configurado en settings. "
                    "Definí la variable de entorno o agregala a settings.py."
                )
            )
            return

        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS("MONITOR DE INFORMES PDF — Navify"))
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(f"Carpeta monitoreada: {carpeta}")
        self.stdout.write("Esperando archivos PDF... (Ctrl+C para detener)\n")

        event_handler = PDFInformeEventHandler()
        observer = Observer()
        observer.schedule(event_handler, str(carpeta), recursive=False)
        observer.start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stdout.write("\nSeñal de interrupción recibida. Deteniendo monitor...")
            observer.stop()

        observer.join()
        self.stdout.write(self.style.SUCCESS("Monitor detenido correctamente."))
