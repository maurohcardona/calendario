from django.contrib import admin
from .models import Medico


@admin.register(Medico)
class MedicoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'matricula')
    search_fields = ('nombre', 'matricula')
    ordering = ('nombre',)
