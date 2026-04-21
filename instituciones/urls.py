"""URLs de la app instituciones."""

from django.urls import path

from instituciones import views

app_name = "instituciones"

urlpatterns = [
    path("estadisticas/", views.estadisticas_instituciones, name="estadisticas"),
]
