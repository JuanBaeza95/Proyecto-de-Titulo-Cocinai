from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def seccion_required(*nombres_secciones):
    """
    Decorador para verificar que el usuario tenga acceso a una o más secciones.
    Los nombres de secciones deben coincidir con los nombres de los grupos.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            
            # Los superusers tienen acceso a todo
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            
            # Verificar que el usuario tenga al menos uno de los grupos requeridos
            grupos_usuario = [g.name for g in request.user.groups.all()]
            tiene_acceso = any(seccion in grupos_usuario for seccion in nombres_secciones)
            
            if not tiene_acceso:
                messages.error(
                    request, 
                    f'No tienes permisos para acceder a esta sección. '
                    f'Contacta al administrador para solicitar acceso.'
                )
                return redirect('dashboard')
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

