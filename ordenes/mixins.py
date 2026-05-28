from functools import wraps
from django.contrib import messages
from django.shortcuts import redirect


def medico_requerido(view_func):
    """Decorator que requiere que el usuario tenga un médico asociado."""

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("login")
        try:
            _ = request.user.medico
        except Exception:
            messages.error(request, "Tu usuario no tiene un médico asociado.")
            return redirect("turnos:calendario")
        return view_func(request, *args, **kwargs)

    return wrapper


def operador_lab_requerido(view_func):
    """Decorator que requiere que el usuario sea operador de laboratorio o superusuario."""

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("login")
        if not (request.user.is_superuser or request.user.groups.filter(name="laboratorio").exists()):
            messages.error(request, "No tenés permisos para acceder a esta sección.")
            return redirect("turnos:calendario")
        return view_func(request, *args, **kwargs)

    return wrapper
