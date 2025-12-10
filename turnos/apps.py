from django.apps import AppConfig


class TurnosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'turnos'

    def ready(self):
        """Importar la configuración de auditoría cuando la app se inicie"""
        import turnos.auditlog
