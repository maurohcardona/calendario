from django.contrib import admin
from django.utils.html import format_html
from .models import Determinacion, PerfilDeterminacion, DeterminacionCompleja


@admin.register(Determinacion)
class DeterminacionAdmin(admin.ModelAdmin):
    """Configuración del panel de administración para Determinación."""

    list_display = ("codigo", "nombre", "tiempo", "get_estado", "get_disponibilidad")
    list_filter = ("visible", "activa", "stock")
    search_fields = ("codigo", "nombre")
    ordering = ("codigo",)

    fieldsets = (
        ("Información Básica", {"fields": ("codigo", "nombre", "tiempo")}),
        ("Estado y Disponibilidad", {"fields": ("visible", "activa", "stock")}),
    )

    def get_estado(self, obj):
        """Muestra el estado de la determinación con colores."""
        if obj.activa:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ Activa</span>'
            )
        return format_html(
            '<span style="color: red; font-weight: bold;">✗ Inactiva</span>'
        )

    get_estado.short_description = "Estado"
    get_estado.admin_order_field = "activa"

    def get_disponibilidad(self, obj):
        """Muestra la disponibilidad de stock."""
        if obj.stock:
            return format_html('<span style="color: green;">✓ En Stock</span>')
        return format_html('<span style="color: orange;">⚠ Sin Stock</span>')

    get_disponibilidad.short_description = "Stock"
    get_disponibilidad.admin_order_field = "stock"

    # Acciones personalizadas
    actions = [
        "activar_determinaciones",
        "desactivar_determinaciones",
        "marcar_con_stock",
    ]

    def activar_determinaciones(self, request, queryset):
        """Activa las determinaciones seleccionadas."""
        count = queryset.update(activa=True)
        self.message_user(request, f"{count} determinación(es) activada(s).")

    activar_determinaciones.short_description = "Activar determinaciones seleccionadas"

    def desactivar_determinaciones(self, request, queryset):
        """Desactiva las determinaciones seleccionadas."""
        count = queryset.update(activa=False)
        self.message_user(request, f"{count} determinación(es) desactivada(s).")

    desactivar_determinaciones.short_description = (
        "Desactivar determinaciones seleccionadas"
    )

    def marcar_con_stock(self, request, queryset):
        """Marca las determinaciones seleccionadas como con stock."""
        count = queryset.update(stock=True)
        self.message_user(request, f"{count} determinación(es) marcada(s) con stock.")

    marcar_con_stock.short_description = "Marcar con stock disponible"

    list_per_page = 50
    save_on_top = True


@admin.register(PerfilDeterminacion)
class PerfilDeterminacionAdmin(admin.ModelAdmin):
    """Configuración del panel de administración para Perfil de Determinación."""

    list_display = ("codigo", "nombre", "get_cantidad_determinaciones")
    search_fields = ("codigo", "nombre")
    ordering = ("codigo",)

    fieldsets = (
        ("Información del Perfil", {"fields": ("codigo", "nombre")}),
        (
            "Determinaciones Incluidas",
            {
                "fields": ("determinaciones",),
                "description": "Lista de códigos de determinaciones incluidas en este perfil",
            },
        ),
    )

    def get_cantidad_determinaciones(self, obj):
        """Muestra la cantidad de determinaciones en el perfil."""
        return len(obj.determinaciones) if obj.determinaciones else 0

    get_cantidad_determinaciones.short_description = "Cantidad de Determinaciones"

    list_per_page = 25
    save_on_top = True


@admin.register(DeterminacionCompleja)
class DeterminacionComplejaAdmin(admin.ModelAdmin):
    """Configuración del panel de administración para Determinación Compleja."""

    list_display = (
        "codigo",
        "nombre",
        "tiempo",
        "get_estado",
        "get_disponibilidad",
        "get_cantidad_determinaciones",
    )
    list_filter = ("visible", "activa", "stock")
    search_fields = ("codigo", "nombre")
    ordering = ("codigo",)

    fieldsets = (
        ("Información Básica", {"fields": ("codigo", "nombre", "tiempo")}),
        ("Estado y Disponibilidad", {"fields": ("visible", "activa", "stock")}),
        (
            "Determinaciones Incluidas",
            {
                "fields": ("determinaciones",),
                "description": "Lista de códigos de determinaciones complejas incluidas",
            },
        ),
    )

    def get_estado(self, obj):
        """Muestra el estado de la determinación con colores."""
        if obj.activa:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ Activa</span>'
            )
        return format_html(
            '<span style="color: red; font-weight: bold;">✗ Inactiva</span>'
        )

    get_estado.short_description = "Estado"
    get_estado.admin_order_field = "activa"

    def get_disponibilidad(self, obj):
        """Muestra la disponibilidad de stock."""
        if obj.stock:
            return format_html('<span style="color: green;">✓ En Stock</span>')
        return format_html('<span style="color: orange;">⚠ Sin Stock</span>')

    get_disponibilidad.short_description = "Stock"
    get_disponibilidad.admin_order_field = "stock"

    def get_cantidad_determinaciones(self, obj):
        """Muestra la cantidad de determinaciones en el complejo."""
        return len(obj.determinaciones) if obj.determinaciones else 0

    get_cantidad_determinaciones.short_description = "Cantidad"

    # Acciones personalizadas
    actions = ["activar_determinaciones", "desactivar_determinaciones"]

    def activar_determinaciones(self, request, queryset):
        """Activa las determinaciones seleccionadas."""
        count = queryset.update(activa=True)
        self.message_user(
            request, f"{count} determinación(es) compleja(s) activada(s)."
        )

    activar_determinaciones.short_description = "Activar determinaciones seleccionadas"

    def desactivar_determinaciones(self, request, queryset):
        """Desactiva las determinaciones seleccionadas."""
        count = queryset.update(activa=False)
        self.message_user(
            request, f"{count} determinación(es) compleja(s) desactivada(s)."
        )

    desactivar_determinaciones.short_description = (
        "Desactivar determinaciones seleccionadas"
    )

    list_per_page = 50
    save_on_top = True
