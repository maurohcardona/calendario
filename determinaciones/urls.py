from django.urls import path
from . import views

app_name = "determinaciones"

urlpatterns = [
    path("api/buscar-determinacion/", views.buscar_determinacion_api, name="buscar_determinacion_api"),
    path("api/listar-determinaciones/", views.listar_determinaciones_api, name="listar_determinaciones_api"),
    path("api/buscar-codigo/", views.buscar_codigo_api, name="buscar_codigo_api"),
    path("api/buscar-perfil/", views.buscar_perfil_api, name="buscar_perfil_api"),
]
