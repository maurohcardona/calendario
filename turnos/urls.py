from django.urls import path
from . import views

app_name = "turnos"

urlpatterns = [
    path("calendario/", views.calendario, name="calendario"),
    path("cupo/nuevo/", views.nuevo_cupo, name="nuevo_cupo"),
    path("eventos/", views.eventos_calendario, name="eventos"),
    path("dia/<str:fecha>/", views.dia, name="dia"),
    path("buscar/", views.buscar, name="buscar"),
]

