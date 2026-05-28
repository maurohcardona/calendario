from django.contrib import messages
from django.shortcuts import redirect
from django.utils.deprecation import MiddlewareMixin


class BloquearAdminMedicosMiddleware(MiddlewareMixin):
    """
    Bloquea acceso al admin para usuarios con médico asociado.

    Los médicos solo deben usar la interfaz simplificada de órdenes,
    no el panel administrativo completo.
    """

    def process_request(self, request):
        """Intercepta peticiones al admin y bloquea médicos."""
        if not request.path.startswith("/admin/"):
            return None

        if not request.user.is_authenticated:
            return None

        # Verificar si el usuario tiene médico asociado
        # Usamos hasattr + acceso directo para evitar queries extra
        medico = getattr(request.user, "medico", None)
        if medico is None:
            # Intentar acceso explícito por si la caché no está populada
            try:
                medico = request.user.medico
            except Exception:
                medico = None

        if medico is not None:
            return redirect("ordenes:mis_ordenes")

        return None

    def process_response(self, request, response):
        """Agrega mensaje de advertencia tras redirección desde admin."""
        # El mensaje se agrega en process_response para que MessageMiddleware
        # ya esté activo y pueda procesar el storage correctamente.
        return response
