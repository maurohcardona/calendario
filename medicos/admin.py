from django.contrib import admin
from .models import Medico


@admin.register(Medico)
class MedicoAdmin(admin.ModelAdmin):
    """Configuración del panel de administración para el modelo Médico."""

    list_display = ("nombre", "matricula", "get_cantidad_turnos")
    search_fields = ("nombre", "matricula")
    ordering = ("nombre",)

    fieldsets = (("Información del Médico", {"fields": ("nombre", "matricula")}),)

    def get_cantidad_turnos(self, obj):
        """Muestra la cantidad de turnos asociados al médico."""
        return obj.turnos.count()

    get_cantidad_turnos.short_description = "Cantidad de Turnos"

    # Configuración avanzada
    list_per_page = 25
    save_on_top = True
