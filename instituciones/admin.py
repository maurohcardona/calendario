from django.contrib import admin

from .models import Institucion


@admin.register(Institucion)
class InstitucionAdmin(admin.ModelAdmin):
    """Admin para el modelo Institucion."""

    list_display = ("nombre", "activa")
    list_filter = ("activa",)
    search_fields = ("nombre",)
    list_editable = ("activa",)
