from django.contrib import admin
from .models import Determinacion, PerfilDeterminacion, DeterminacionCompleja


@admin.register(Determinacion)
class DeterminacionAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'tiempo', 'visible', 'activa', 'stock')
    list_filter = ('visible', 'activa')
    search_fields = ('codigo', 'nombre')
    ordering = ('codigo',)


@admin.register(PerfilDeterminacion)
class PerfilDeterminacionAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'determinaciones')
    search_fields = ('codigo', 'nombre')
    ordering = ('codigo',)


@admin.register(DeterminacionCompleja)
class DeterminacionComplejaAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'tiempo', 'stock', 'activa', 'visible', 'determinaciones')
    search_fields = ('codigo', 'nombre',)
    ordering = ('codigo',)