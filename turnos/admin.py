from django.contrib import admin
from .models import Cupo, Turno, CapacidadDia


admin.site.register(Cupo)
admin.site.register(Turno)
admin.site.register(CapacidadDia)

# Registered Cupo so admins can manage daily capacities
