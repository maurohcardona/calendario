"""
Comando de management para limpiar registros de Informes con email_destino inválido.

Este comando busca informes con email_destino None, vacío o 'none', y:
1. Actualiza el email_destino con el email actual del paciente si lo tiene
2. Marca como ERROR los informes de pacientes que siguen sin email

Uso:
    python manage.py limpiar_informes_sin_email
"""

from django.core.management.base import BaseCommand
from django.db.models import Q

from informes.models import Informes


class Command(BaseCommand):
    help = "Limpia registros de Informes con email_destino inválido"

    def handle(self, *args, **options):
        self.stdout.write("=" * 70)
        self.stdout.write(self.style.WARNING("LIMPIEZA DE INFORMES CON EMAIL INVÁLIDO"))
        self.stdout.write("=" * 70)

        # Buscar informes con email_destino None, vacío o 'none'
        informes_sin_email = Informes.objects.filter(
            Q(email_destino__isnull=True)
            | Q(email_destino="")
            | Q(email_destino="none")
        ).select_related("paciente")

        count = informes_sin_email.count()
        self.stdout.write(f"\n📊 Encontrados {count} informes con email inválido\n")

        if count == 0:
            self.stdout.write(self.style.SUCCESS("✅ No hay informes que limpiar"))
            return

        actualizados = 0
        marcados_error = 0

        for informe in informes_sin_email:
            # Intentar actualizar con el email actual del paciente
            if informe.paciente.email:
                informe.email_destino = informe.paciente.email
                # Reiniciar estado para permitir reintento
                if informe.estado == "ERROR":
                    informe.estado = "PENDIENTE"
                    informe.mensaje_error = ""
                informe.save()
                actualizados += 1
                self.stdout.write(
                    f"  ✓ Actualizado informe ID={informe.id} "
                    f"(orden={informe.numero_orden}, protocolo={informe.numero_protocolo}) "
                    f"con email {informe.paciente.email}"
                )
            else:
                # Marcar como ERROR si el paciente sigue sin email
                informe.estado = "ERROR"
                informe.mensaje_error = "Paciente sin email registrado"
                informe.save()
                marcados_error += 1
                self.stdout.write(
                    f"  ✗ Marcado como ERROR informe ID={informe.id} "
                    f"(orden={informe.numero_orden}, protocolo={informe.numero_protocolo}) "
                    f"- Paciente DNI={informe.paciente.iden} sin email"
                )

        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(
            self.style.SUCCESS(
                f"\n✅ COMPLETADO:\n"
                f"   - {actualizados} informes actualizados con email del paciente\n"
                f"   - {marcados_error} informes marcados como ERROR (paciente sin email)\n"
            )
        )
        self.stdout.write("=" * 70 + "\n")

        if actualizados > 0:
            self.stdout.write(
                self.style.WARNING(
                    f"\n⚠️  NOTA: Los {actualizados} informes actualizados ahora están en estado PENDIENTE.\n"
                    f"   Asegúrate de que sus archivos PDF estén en la carpeta 'pendientes/'\n"
                    f"   para que puedan procesarse correctamente.\n"
                )
            )
