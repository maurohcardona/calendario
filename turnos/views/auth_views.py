"""
Vistas relacionadas con autenticación.
"""

from django.conf import settings
from django.contrib.auth import logout
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect


def logout_view(request: HttpRequest) -> HttpResponse:
    """
    Cierra sesión del usuario y redirige a la página de login.

    Acepta GET y POST. POST cierra sesión, GET simplemente redirige.

    Args:
            request: Objeto HttpRequest.

    Returns:
            HttpResponse con redirección a la URL de logout configurada o /accounts/login/.

    Example:
            GET/POST /logout/
            Cierra sesión y redirige a login
    """
    if request.method == "POST":
        logout(request)
        return redirect(settings.LOGOUT_REDIRECT_URL or "/accounts/login/")
    # Para requests GET, simplemente redirige a la página de login
    return redirect(settings.LOGOUT_REDIRECT_URL or "/accounts/login/")
