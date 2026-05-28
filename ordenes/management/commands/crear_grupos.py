from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """Comando para crear los grupos medicos y laboratorio."""

    help = "Crea los grupos medicos y laboratorio"

    def handle(self, *args, **kwargs):
        Group.objects.get_or_create(name="medicos")
        Group.objects.get_or_create(name="laboratorio")
        self.stdout.write(self.style.SUCCESS("Grupos creados correctamente."))
