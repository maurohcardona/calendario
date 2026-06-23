from django.urls import path

from . import views

app_name = "informes"

urlpatterns = [
    path("", views.listado_informes, name="listado"),
    path("archivo/<str:estado>/<str:nombre_archivo>/", views.ver_pdf, name="ver_pdf"),
    path(
        "enviar/<str:estado>/<str:nombre_archivo>/",
        views.enviar_informe,
        name="enviar_informe",
    ),
    path(
        "actualizar-email/<str:dni>/",
        views.actualizar_email_paciente,
        name="actualizar_email",
    ),
    # Sirve PDFs por coordinación (turno o orden) — requiere autenticación
    path(
        "pdf/<str:tipo>/<int:pk>/",
        views.servir_informe_orden,
        name="servir_pdf_orden",
    ),
]
