from django.contrib import admin
from django.utils.html import format_html
from .models import Cupo, Turno, Agenda, Coordinados, Feriados, ColaReintentos
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as DefaultUserAdmin


@admin.register(Agenda)
class AgendaAdmin(admin.ModelAdmin):
    """Configuración del panel de administración para Agendas."""

    list_display = ("name", "slug", "get_color_display")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name", "slug")

    fieldsets = (
        ("Información de la Agenda", {"fields": ("name", "slug")}),
        ("Configuración Visual", {"fields": ("color",)}),
        ("Auditoría", {"fields": ("usuario",), "classes": ("collapse",)}),
    )

    def get_color_display(self, obj):
        """Muestra el color con una representación visual."""
        return format_html(
            '<span style="background-color: {}; padding: 5px 15px; border-radius: 3px; color: white; font-weight: bold;">{}</span>',
            obj.color,
            obj.color,
        )

    get_color_display.short_description = "Color"
    get_color_display.admin_order_field = "color"

    list_per_page = 25
    save_on_top = True


@admin.register(Coordinados)
class CoordinadosAdmin(admin.ModelAdmin):
    list_display = (
        "id_turno",
        "get_dni",
        "get_apellido",
        "get_nombre",
        "fecha_coordinacion",
        "mensaje_tipo",
        "get_ack_estado_display",
    )
    list_filter = ("mensaje_tipo", "ack_estado", "fecha_coordinacion")
    search_fields = ("dni__iden", "dni__apellido", "dni__nombre")
    readonly_fields = (
        "fecha_coordinacion",
        "get_mensaje_hl7_preview",
        "get_ack_recibido_preview",
    )
    ordering = ("-fecha_coordinacion", "id_turno")

    fieldsets = (
        (
            "Datos del Turno",
            {"fields": ("id_turno", "dni", "fecha_coordinacion", "determinaciones", "usuario")},
        ),
        (
            "Mensaje HL7 enviado",
            {
                "fields": ("mensaje_tipo", "get_mensaje_hl7_preview"),
                "classes": ("collapse",),
            },
        ),
        (
            "ACK recibido del LIS",
            {
                "fields": ("ack_estado", "get_ack_recibido_preview"),
                "classes": ("collapse",),
            },
        ),
    )

    def get_dni(self, obj):
        return obj.dni.iden if obj.dni else "-"

    get_dni.short_description = "DNI"
    get_dni.admin_order_field = "dni__iden"

    def get_apellido(self, obj):
        return obj.dni.apellido if obj.dni else "-"

    get_apellido.short_description = "Apellido"
    get_apellido.admin_order_field = "dni__apellido"

    def get_nombre(self, obj):
        return obj.dni.nombre if obj.dni else "-"

    get_nombre.short_description = "Nombre"
    get_nombre.admin_order_field = "dni__nombre"

    def get_ack_estado_display(self, obj):
        """Muestra el estado ACK con color semántico."""
        colores = {"AA": "green", "AE": "orange", "AR": "red"}
        if not obj.ack_estado:
            return format_html('<span style="color: gray;">Pendiente</span>')
        color = colores.get(obj.ack_estado, "gray")
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_ack_estado_display(),
        )

    get_ack_estado_display.short_description = "Estado ACK"
    get_ack_estado_display.admin_order_field = "ack_estado"

    def get_mensaje_hl7_preview(self, obj):
        """Muestra los primeros 300 caracteres del mensaje HL7."""
        if not obj.mensaje_hl7:
            return "-"
        preview = obj.mensaje_hl7[:300]
        return format_html('<pre style="font-size: 11px;">{}</pre>', preview)

    get_mensaje_hl7_preview.short_description = "Mensaje HL7 (preview)"

    def get_ack_recibido_preview(self, obj):
        """Muestra los primeros 300 caracteres del ACK recibido."""
        if not obj.ack_recibido:
            return "-"
        preview = obj.ack_recibido[:300]
        return format_html('<pre style="font-size: 11px;">{}</pre>', preview)

    get_ack_recibido_preview.short_description = "ACK recibido (preview)"


@admin.register(Cupo)
class CupoAdmin(admin.ModelAdmin):
    """Configuración del panel de administración para Cupos."""

    list_display = (
        "agenda",
        "fecha",
        "cantidad_total",
        "get_disponibles",
        "get_ocupacion",
    )
    list_filter = ("agenda", "fecha")
    search_fields = ("agenda__name",)
    date_hierarchy = "fecha"
    actions = ["crear_cupos_rango"]

    fieldsets = (
        ("Información del Cupo", {"fields": ("agenda", "fecha", "cantidad_total")}),
        ("Auditoría", {"fields": ("usuario",), "classes": ("collapse",)}),
    )

    def get_disponibles(self, obj):
        """Muestra los cupos disponibles."""
        disponibles = obj.disponibles()
        color = "green" if disponibles > 0 else "red"
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>', color, disponibles
        )

    get_disponibles.short_description = "Disponibles"

    def get_ocupacion(self, obj):
        """Muestra el porcentaje de ocupación."""
        if obj.cantidad_total == 0:
            return "0%"
        usados = obj.cantidad_total - obj.disponibles()
        porcentaje = int((usados / obj.cantidad_total) * 100)

        if porcentaje >= 90:
            color = "red"
        elif porcentaje >= 70:
            color = "orange"
        else:
            color = "green"

        return format_html(
            '<span style="color: {}; font-weight: bold;">{}%</span>', color, porcentaje
        )

    get_ocupacion.short_description = "Ocupación"

    def crear_cupos_rango(self, request, queryset):
        """Admin action: crear cupos de lunes a viernes en un rango de fechas con cantidad configurable."""
        from django.shortcuts import render
        from django import forms
        from datetime import datetime, timedelta
        from django.contrib import messages

        class _CreateCuposForm(forms.Form):
            agenda = forms.ModelChoiceField(
                queryset=Agenda.objects.all(), label="Agenda"
            )
            start = forms.DateField(
                required=True,
                widget=forms.DateInput(attrs={"type": "date"}),
                label="Desde",
            )
            end = forms.DateField(
                required=True,
                widget=forms.DateInput(attrs={"type": "date"}),
                label="Hasta",
            )
            cantidad = forms.IntegerField(
                required=True, initial=5, min_value=1, label="Cantidad de cupos"
            )

        if "apply" in request.POST:
            form = _CreateCuposForm(request.POST)
            if form.is_valid():
                start = form.cleaned_data["start"]
                end = form.cleaned_data["end"]
                cantidad = form.cleaned_data["cantidad"]
                agenda = form.cleaned_data["agenda"]

                total_created = 0
                total_skipped = 0

                # Iterar desde start hasta end, solo de lunes a viernes
                cur = start
                while cur <= end:
                    # weekday(): 0=Lunes, 1=Martes, ..., 4=Viernes, 5=Sábado, 6=Domingo
                    if cur.weekday() < 5:  # Solo lunes a viernes
                        obj, created = Cupo.objects.get_or_create(
                            agenda=agenda,
                            fecha=cur,
                            defaults={"cantidad_total": cantidad},
                        )
                        if created:
                            total_created += 1
                        else:
                            total_skipped += 1
                    cur += timedelta(days=1)

                messages.success(
                    request,
                    f"✅ Cupos creados: {total_created} nuevos (lunes-viernes). Existentes omitidos: {total_skipped}. Rango: {start} a {end}.",
                )
                return None
        else:
            form = _CreateCuposForm()

        return render(
            request,
            "admin/turnos/cupo_create_range.html",
            {"form": form, "title": "Crear Cupos en Rango de Fechas (Lunes-Viernes)"},
        )

    crear_cupos_rango.short_description = (
        "Crear cupos en rango de fechas (Lunes-Viernes)"
    )


@admin.register(Turno)
class TurnoAdmin(admin.ModelAdmin):
    list_display = ("id", "agenda", "fecha", "get_dni", "usuario", "creado")
    list_filter = (
        "agenda",
        "fecha",
    )
    search_fields = ("dni__iden", "dni__apellido", "dni__nombre", "medico__nombre")
    readonly_fields = ("creado",)
    fieldsets = (
        ("Información del Paciente", {"fields": ("dni",)}),
        ("Turno", {"fields": ("agenda", "fecha", "medico")}),
        ("Información Adicional", {"fields": ("determinaciones", "nota_interna")}),
        ("Auditoría", {"fields": ("usuario", "creado"), "classes": ("collapse",)}),
    )

    def get_search_results(self, request, queryset, search_term):
        """Personalizar búsqueda para incluir búsqueda de médicos."""
        queryset, use_distinct = super().get_search_results(
            request, queryset, search_term
        )
        return queryset, use_distinct

    def get_dni(self, obj):
        return obj.dni.iden if obj.dni else "-"

    get_dni.short_description = "DNI"
    get_dni.admin_order_field = "dni__iden"


@admin.register(Feriados)
class FeriadosAdmin(admin.ModelAdmin):
    list_display = ("fecha", "descripcion")
    list_filter = ("fecha",)
    search_fields = ("descripcion",)
    ordering = ("-fecha",)


@admin.register(ColaReintentos)
class ColaReintentosAdmin(admin.ModelAdmin):
    """Admin para monitorear y gestionar mensajes HL7 pendientes de reenvío."""

    list_display = (
        "turno_id",
        "intentos",
        "fecha_creacion",
        "fecha_ultimo_intento",
        "get_error_truncado",
        "get_estado_visual",
    )
    list_filter = ("intentos", "fecha_creacion")
    search_fields = ("turno_id", "ultimo_error")
    readonly_fields = (
        "fecha_creacion",
        "fecha_ultimo_intento",
        "get_mensaje_hl7_preview",
    )
    ordering = ("-fecha_creacion",)

    fieldsets = (
        (
            "Identificación",
            {"fields": ("turno_id", "intentos", "fecha_creacion", "fecha_ultimo_intento")},
        ),
        (
            "Error",
            {"fields": ("ultimo_error",)},
        ),
        (
            "Mensaje HL7",
            {"fields": ("get_mensaje_hl7_preview",), "classes": ("collapse",)},
        ),
    )

    def get_error_truncado(self, obj):
        if not obj.ultimo_error:
            return "-"
        return obj.ultimo_error[:60] + ("..." if len(obj.ultimo_error) > 60 else "")

    get_error_truncado.short_description = "Último error"

    def get_estado_visual(self, obj):
        """Semáforo visual según cantidad de intentos."""
        from django.conf import settings as s
        max_r = getattr(s, "LIS_MAX_REINTENTOS", 3)
        if obj.intentos >= max_r - 1:
            return format_html(
                '<span style="color: red; font-weight: bold;">CRÍTICO ({}/{})</span>',
                obj.intentos,
                max_r,
            )
        return format_html(
            '<span style="color: orange;">{}/{}</span>',
            obj.intentos,
            max_r,
        )

    get_estado_visual.short_description = "Estado"

    def get_mensaje_hl7_preview(self, obj):
        preview = obj.mensaje_hl7[:300] if obj.mensaje_hl7 else "-"
        return format_html('<pre style="font-size: 11px;">{}</pre>', preview)

    get_mensaje_hl7_preview.short_description = "Mensaje HL7 (preview)"


# Mostrar nombre y apellido en el admin de usuarios
class UserAdmin(DefaultUserAdmin):
    list_display = ("username", "first_name", "last_name", "email", "is_staff")
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "username",
                    "first_name",
                    "last_name",
                    "email",
                    "password1",
                    "password2",
                ),
            },
        ),
    )


try:
    admin.site.unregister(User)
except Exception:
    pass
admin.site.register(User, UserAdmin)
