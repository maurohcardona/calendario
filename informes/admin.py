from django.contrib import admin
from django.utils.html import format_html
from .models import Informes


@admin.register(Informes)
class InformesAdmin(admin.ModelAdmin):
    """Configuración del panel de administración para Informes Médicos."""

    list_display = (
        "nombre_archivo",
        "get_iden_paciente",
        "get_nombre_paciente",
        "numero_orden",
        "numero_protocolo",
        "get_estado_color",
        "fecha_envio",
        "intentos_envio",
        "get_whatsapp_status",
    )
    list_filter = ("estado", "fecha_creacion", "fecha_envio", "whatsapp_enviado")
    search_fields = (
        "paciente__iden",
        "paciente__nombre",
        "paciente__apellido",
        "numero_orden",
        "numero_protocolo",
        "email_destino",
        "whatsapp_telefono",
    )
    readonly_fields = (
        "fecha_creacion",
        "fecha_envio",
        "intentos_envio",
        "mensaje_error",
        "whatsapp_error",
    )
    ordering = ["-fecha_creacion"]
    date_hierarchy = "fecha_creacion"

    fieldsets = (
        ("Información del Paciente", {"fields": ("paciente", "id_turno")}),
        (
            "Datos del Informe",
            {"fields": ("numero_orden", "numero_protocolo", "nombre_archivo")},
        ),
        (
            "Estado del Envío por Email",
            {
                "fields": (
                    "estado",
                    "email_destino",
                    "fecha_creacion",
                    "fecha_envio",
                    "intentos_envio",
                    "mensaje_error",
                )
            },
        ),
        (
            "Estado del Envío por WhatsApp",
            {
                "fields": ("whatsapp_enviado", "whatsapp_telefono", "whatsapp_error"),
                "classes": ("collapse",),
            },
        ),
    )

    def get_iden_paciente(self, obj):
        """Muestra la identificación del paciente."""
        return obj.paciente.iden if obj.paciente else "-"

    get_iden_paciente.short_description = "Identificación"
    get_iden_paciente.admin_order_field = "paciente__iden"

    def get_nombre_paciente(self, obj):
        """Muestra el nombre completo del paciente."""
        if obj.paciente:
            return f"{obj.paciente.apellido}, {obj.paciente.nombre}"
        return "-"

    get_nombre_paciente.short_description = "Paciente"
    get_nombre_paciente.admin_order_field = "paciente__apellido"

    def get_estado_color(self, obj):
        """Muestra el estado con colores distintivos."""
        colores = {
            "PENDIENTE": ("orange", "⏳"),
            "ENVIADO": ("green", "✓"),
            "ERROR": ("red", "✗"),
        }
        color, icono = colores.get(obj.estado, ("gray", "?"))
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {}</span>',
            color,
            icono,
            obj.get_estado_display(),
        )

    get_estado_color.short_description = "Estado"
    get_estado_color.admin_order_field = "estado"

    def get_whatsapp_status(self, obj):
        """Muestra el estado del envío por WhatsApp."""
        if obj.whatsapp_enviado:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ Enviado</span>'
            )
        elif obj.whatsapp_error:
            return format_html('<span style="color: red;">✗ Error</span>')
        return format_html('<span style="color: gray;">- No enviado</span>')

    get_whatsapp_status.short_description = "WhatsApp"
    get_whatsapp_status.admin_order_field = "whatsapp_enviado"

    # Acciones personalizadas
    actions = ["marcar_como_pendiente", "reintentar_envio", "marcar_como_enviado"]

    def marcar_como_pendiente(self, request, queryset):
        """Marca informes seleccionados como pendientes."""
        count = queryset.update(estado="PENDIENTE")
        self.message_user(request, f"{count} informe(s) marcado(s) como pendiente.")

    marcar_como_pendiente.short_description = "Marcar como pendiente"

    def reintentar_envio(self, request, queryset):
        """Reinicia el contador de intentos para volver a enviar."""
        count = queryset.filter(estado="ERROR").update(
            estado="PENDIENTE", intentos_envio=0, mensaje_error=""
        )
        self.message_user(request, f"{count} informe(s) preparado(s) para reenvío.")

    reintentar_envio.short_description = "Reintentar envío (solo con ERROR)"

    def marcar_como_enviado(self, request, queryset):
        """Marca informes seleccionados como enviados manualmente."""
        from django.utils import timezone

        count = queryset.update(estado="ENVIADO", fecha_envio=timezone.now())
        self.message_user(request, f"{count} informe(s) marcado(s) como enviado.")

    marcar_como_enviado.short_description = "Marcar como enviado manualmente"

    # Configuración avanzada
    list_per_page = 25
    save_on_top = True
    list_select_related = ["paciente", "id_turno"]
