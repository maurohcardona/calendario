"""
Management command para sincronizar órdenes existentes (FK) a la nueva relación M2M.

Ejecutar una sola vez después de la migración 0006_add_ordenes_m2m.
"""
from django.core.management.base import BaseCommand
from turnos.models import Turno
from ordenes.models import OrdenLaboratorio


class Command(BaseCommand):
    """Sincroniza órdenes existentes (FK en OrdenLaboratorio) a la nueva relación M2M en Turno."""

    help = "Sincroniza órdenes existentes (FK) a la nueva relación M2M en Turno"

    def handle(self, *args, **options):
        """Ejecuta la sincronización de datos."""
        turnos_sincronizados = 0
        ordenes_sincronizadas = 0

        for turno in Turno.objects.all():
            # Buscar órdenes que apuntan a este turno via FK
            ordenes = OrdenLaboratorio.objects.filter(turno=turno)

            if ordenes.exists():
                # Agregar a M2M (sin duplicar si ya existía la relación)
                turno.ordenes.set(ordenes)
                turnos_sincronizados += 1
                ordenes_sincronizadas += ordenes.count()

                self.stdout.write(
                    f"✓ Turno {turno.pk}: {ordenes.count()} órdenes sincronizadas"
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"\n✅ Sincronización completada:\n"
                f"   - {turnos_sincronizados} turnos procesados\n"
                f"   - {ordenes_sincronizadas} órdenes vinculadas"
            )
        )
