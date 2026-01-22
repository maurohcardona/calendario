from django.contrib import admin
from .models import Determinacion, PerfilDeterminacion


@admin.register(Determinacion)
class DeterminacionAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'visible', 'activa')
    list_filter = ('visible', 'activa')
    search_fields = ('codigo', 'nombre')
    ordering = ('codigo',)


@admin.register(PerfilDeterminacion)
class PerfilDeterminacionAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'determinaciones')
    search_fields = ('codigo',)
    ordering = ('codigo',)
