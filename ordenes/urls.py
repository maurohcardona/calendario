from django.urls import path
from . import views

app_name = "ordenes"

urlpatterns = [
    # Médico
    path("nueva/", views.crear_orden, name="crear_orden"),
    path("nueva-programada/", views.crear_orden_programada, name="crear_orden_programada"),
    path("mis-ordenes/", views.mis_ordenes, name="mis_ordenes"),
    path("todas/", views.todas_ordenes, name="todas_ordenes"),
    path("<int:pk>/", views.detalle_orden, name="detalle_orden"),
    # AJAX
    path("ajax/filtrar-mis-ordenes/", views.filtrar_mis_ordenes_ajax, name="filtrar_mis_ordenes_ajax"),
    path("ajax/buscar-paciente/", views.buscar_paciente, name="buscar_paciente"),
    path("ajax/servicios/", views.obtener_servicios, name="obtener_servicios"),
    path("ajax/buscar-ordenes/", views.buscar_ordenes_global, name="buscar_ordenes_global"),
    path("ajax/buscar-orden-pendiente/", views.buscar_orden_pendiente, name="buscar_orden_pendiente"),
    # Laboratorio
    path("cola/", views.cola_laboratorio, name="cola_laboratorio"),
    path("<int:pk>/ingresar/", views.ingresar_orden, name="ingresar_orden"),
    path("<int:pk>/vincular-turno/", views.vincular_turno, name="vincular_turno"),
    path("<int:pk>/completar/", views.completar_orden, name="completar_orden"),
    path("<int:pk>/cancelar/", views.cancelar_orden, name="cancelar_orden"),
]
