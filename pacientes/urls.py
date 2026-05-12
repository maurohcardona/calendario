from django.urls import path
from . import views

app_name = "pacientes"

urlpatterns = [
    path("api/buscar-paciente/", views.buscar_paciente_api, name="buscar_paciente_api"),
    path("api/buscar-pacientes/", views.buscar_pacientes_parcial_api, name="buscar_pacientes_parcial_api"),
]
