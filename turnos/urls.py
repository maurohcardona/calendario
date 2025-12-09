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
    path("api/buscar-paciente/", views.buscar_paciente_api, name="buscar_paciente_api"),
    path("api/buscar-determinacion/", views.buscar_determinacion_api, name="buscar_determinacion_api"),
    path("api/listar-determinaciones/", views.listar_determinaciones_api, name="listar_determinaciones_api"),
    path("api/buscar-codigo/", views.buscar_codigo_api, name="buscar_codigo_api"),
    path("api/buscar-perfil/", views.buscar_perfil_api, name="buscar_perfil_api"),
    path("turno/<int:turno_id>/coordinar/", views.coordinar_turno, name="coordinar_turno"),
    path("api/turnos-historicos/<str:fecha>/", views.turnos_historicos_api, name="turnos_historicos_api"),
]

