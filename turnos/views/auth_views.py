"""
Vistas relacionadas con autenticación.
"""
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.conf import settings


def logout_view(request):
    """Accept GET and POST. POST logs out the user. GET redirects to login."""
    if request.method == 'POST':
        logout(request)
        return redirect(settings.LOGOUT_REDIRECT_URL or '/accounts/login/')
    # For GET requests, just redirect to the login page
    return redirect(settings.LOGOUT_REDIRECT_URL or '/accounts/login/')
