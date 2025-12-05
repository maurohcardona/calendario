from django.urls import path
from . import views

app_name = "turnos"

urlpatterns = [
    path("calendario/", views.calendario, name="calendario"),
    path("cupo/nuevo/", views.nuevo_cupo, name="nuevo_cupo"),
    path("eventos/", views.eventos_calendario, name="eventos"),
    path("dia/<str:fecha>/", views.dia, name="dia"),
    path("buscar/", views.buscar, name="buscar"),
    path("turno/<int:turno_id>/editar/", views.editar_turno, name="editar_turno"),
    path("turno/<int:turno_id>/eliminar/", views.eliminar_turno, name="eliminar_turno"),
    path("generar-cupos/", views.generar_cupos_masivo, name="generar_cupos_masivo"),
    path("borrar-cupos/", views.borrar_cupos_masivo, name="borrar_cupos_masivo"),
]

