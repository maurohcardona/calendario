"""
Views para la aplicación de turnos.

Este archivo actúa como puente de compatibilidad, importando todas las vistas
desde el módulo views/ que contiene la estructura modular.

Para mantener la compatibilidad con las URLs existentes que importan desde
'turnos.views', todas las vistas se re-exportan aquí.
"""

# Importar todas las vistas desde el módulo modular
from .views import *  # noqa: F401, F403

# Las vistas están organizadas en:
# - views/calendar_views.py: Vistas del calendario y cupos
# - views/turno_views.py: CRUD de turnos
# - views/coordinacion_views.py: Coordinación y tickets
# - views/api_views.py: Endpoints JSON
# - views/admin_views.py: Funciones administrativas
# - views/auth_views.py: Autenticación
