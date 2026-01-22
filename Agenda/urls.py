from django.contrib import admin
from django.urls import path, include
from turnos import views as turnos_views

urlpatterns = [
    path("admin/", admin.site.urls),
    # App URLs (namespaced)
    path("turnos/", include(("turnos.urls", "turnos"), namespace="turnos")),
    path("pacientes/", include(("pacientes.urls", "pacientes"), namespace="pacientes")),
    path("determinaciones/", include(("determinaciones.urls", "determinaciones"), namespace="determinaciones")),
    # Provide a logout view that accepts GET (redirect) and POST (logout),
    # to avoid 405 errors when a user visits /accounts/logout/.
    path("accounts/logout/", turnos_views.logout_view, name="logout"),
    # Authentication (login/password reset etc.)
    path("accounts/", include("django.contrib.auth.urls")),
]
