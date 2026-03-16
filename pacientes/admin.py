from django.contrib import admin
from .models import Paciente


@admin.register(Paciente)
class PacienteAdmin(admin.ModelAdmin):
    """Configuración del panel de administración para el modelo Paciente."""

    list_display = (
        "iden",
        "apellido",
        "nombre",
        "get_edad",
        "sexo",
        "telefono",
        "email",
    )
    list_filter = ("sexo", "fecha_nacimiento")
    search_fields = ("iden", "apellido", "nombre", "email", "telefono")
    ordering = ("apellido", "nombre")
    readonly_fields = ("get_edad",)

    fieldsets = (
        (
            "Información Personal",
            {"fields": ("iden", "nombre", "apellido", "fecha_nacimiento", "sexo")},
        ),
        ("Información de Contacto", {"fields": ("telefono", "email")}),
        ("Observaciones", {"fields": ("observaciones",), "classes": ("collapse",)}),
    )

    def get_edad(self, obj):
        """Muestra la edad del paciente en años."""
        return f"{obj.edad} años"

    get_edad.short_description = "Edad"
    get_edad.admin_order_field = "fecha_nacimiento"

    # Configuración avanzada
    list_per_page = 25
    date_hierarchy = "fecha_nacimiento"
    save_on_top = True
