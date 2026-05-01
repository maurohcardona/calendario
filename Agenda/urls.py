from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from turnos import views as turnos_views
from django.conf import settings
from django.urls import include, path
from ordenes.views import MedicoAwareLoginView

# Configurar la URL del sitio para el botón "Ver sitio" del admin
admin.site.site_url = "/turnos/calendario"

urlpatterns = [
    path("admin/", admin.site.urls),
    # App URLs (namespaced)
    path("turnos/", include(("turnos.urls", "turnos"), namespace="turnos")),
    path("informes/", include(("informes.urls", "informes"), namespace="informes")),
    path("pacientes/", include(("pacientes.urls", "pacientes"), namespace="pacientes")),
    path(
        "determinaciones/",
        include(
            ("determinaciones.urls", "determinaciones"), namespace="determinaciones"
        ),
    ),
    path("medicos/", include(("medicos.urls", "medicos"), namespace="medicos")),
    path(
        "ordenes/",
        include(("ordenes.urls", "ordenes"), namespace="ordenes"),
    ),
    path(
        "instituciones/",
        include(("instituciones.urls", "instituciones"), namespace="instituciones"),
    ),
    # Provide a logout view that accepts GET (redirect) and POST (logout),
    # to avoid 405 errors when a user visits /accounts/logout/.
    path("accounts/logout/", turnos_views.logout_view, name="logout"),
    # Login custom: redirige médicos a mis_ordenes post-login
    path("accounts/login/", MedicoAwareLoginView.as_view(), name="login"),
    # Authentication (login/password reset etc.)
    path("accounts/", include("django.contrib.auth.urls")),
    # PWA: página offline (fallback cuando no hay conexión)
    path("offline/", TemplateView.as_view(template_name="offline.html"), name="offline"),
]


# Debug Toolbar (Desactivado)
# if settings.DEBUG:
#     import debug_toolbar
#     urlpatterns = [
#         path("__debug__/", include(debug_toolbar.urls)),
#     ] + urlpatterns
