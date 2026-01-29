from django.contrib import admin
from .models import Paciente


@admin.register(Paciente)
class PacienteAdmin(admin.ModelAdmin):
    list_display = ('iden', 'apellido', 'nombre', 'fecha_nacimiento', 'sexo', 'telefono', 'email')
    list_filter = ('sexo', 'fecha_nacimiento')
    search_fields = ('iden', 'apellido', 'nombre', 'email', 'telefono')
    ordering = ('apellido', 'nombre')
