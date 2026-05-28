from django.contrib import admin
from .models import Servicio, OrdenLaboratorio
from determinaciones.models import Determinacion, DeterminacionCompleja


class DeterminacionesInline(admin.TabularInline):
    model = OrdenLaboratorio.determinaciones.through
    extra = 0
    verbose_name = "Determinación"
    verbose_name_plural = "Determinaciones"


class DeterminacionesComplejasInline(admin.TabularInline):
    model = OrdenLaboratorio.determinaciones_complejas.through
    extra = 0
    verbose_name = "Determinación Compleja"
    verbose_name_plural = "Determinaciones Complejas"


@admin.register(Servicio)
class ServicioAdmin(admin.ModelAdmin):
    list_display = ("nombre", "origen", "activo")
    list_filter = ("origen", "activo")
    search_fields = ("nombre",)


@admin.register(OrdenLaboratorio)
class OrdenLaboratorioAdmin(admin.ModelAdmin):
    list_display = ("pk", "paciente", "medico", "tipo_origen", "estado", "fecha_programada", "fecha_creacion")
    list_filter = ("estado", "tipo_origen", "fecha_programada")
    search_fields = ("paciente__apellido", "paciente__iden", "numero_orden_lab")
    readonly_fields = ("fecha_creacion", "fecha_actualizacion", "creado_por")
    inlines = [DeterminacionesInline, DeterminacionesComplejasInline]
    exclude = ("determinaciones", "determinaciones_complejas")
