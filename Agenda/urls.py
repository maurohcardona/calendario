from django.contrib import admin
from django.urls import path
from turnos import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("calendario/", views.calendario, name="calendario"),
    path("eventos/", views.eventos_calendario, name="eventos"),
    path("dia/<str:fecha>/", views.dia, name="dia"),
    path("buscar/", views.buscar, name="buscar"),
]
