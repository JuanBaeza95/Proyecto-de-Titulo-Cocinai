"""
Sistema de permisos granulares basado en grupos de Django.
Cada menú tiene un grupo con formato: seccion.menu
"""
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from .menus import MENUS_POR_SECCION


def menu_required(seccion, menu):
    """
    Decorador para verificar que el usuario tenga acceso a un menú específico.
    
    Args:
        seccion: Nombre de la sección (ej: 'inventario', 'compras')
        menu: Nombre del menú (ej: 'insumos', 'proveedores')
    
    Uso:
        @menu_required('inventario', 'insumos')
        def lista_insumos(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            # Superusers tienen acceso a todo
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            
            # Verificar si el usuario está autenticado
            if not request.user.is_authenticated:
                messages.error(request, 'Debes iniciar sesión para acceder a esta sección.')
                return redirect('login')
            
            # Verificar acceso - SOLO basado en menús específicos, NO en sección completa
            grupos_usuario = [g.name for g in request.user.groups.all()]
            
            # Verificar acceso al menú específico
            menu_group = f'{seccion}.{menu}'
            tiene_menu = menu_group in grupos_usuario
            
            # DEBUG: Log para depuración (puedes quitar esto después)
            import logging
            logger = logging.getLogger(__name__)
            logger.debug(f"Usuario: {request.user.username}, Sección: {seccion}, Menú: {menu}")
            logger.debug(f"Grupos del usuario: {grupos_usuario}")
            logger.debug(f"Tiene menú específico: {tiene_menu}")
            
            # Lógica de permisos:
            # - SOLO se verifica el menú específico, NO la sección completa
            # - La sección completa solo sirve para mostrar/ocultar el acordeón en el formulario
            if tiene_menu:
                # Tiene acceso solo a este menú específico
                return view_func(request, *args, **kwargs)
            
            # No tiene acceso - usar un mensaje único genérico para evitar acumulación
            # Usar una clave en la sesión para evitar múltiples mensajes
            session_key = 'permiso_denegado_mensaje'
            if not request.session.get(session_key, False):
                messages.warning(
                    request, 
                    'No tienes permisos para acceder a esta sección. Contacta al administrador para solicitar acceso.'
                )
                # Marcar en la sesión que ya se mostró el mensaje (expira después de esta request)
                request.session[session_key] = True
            return redirect('dashboard')
        
        return _wrapped_view
    return decorator


def tiene_acceso_menu(user, seccion, menu):
    """
    Función helper para verificar si un usuario tiene acceso a un menú.
    
    Args:
        user: Usuario de Django
        seccion: Nombre de la sección
        menu: Nombre del menú
    
    Returns:
        bool: True si el usuario tiene acceso, False en caso contrario
    """
    if user.is_superuser:
        return True
    
    if not user.is_authenticated:
        return False
    
    grupos_usuario = [g.name for g in user.groups.all()]
    
    # Lógica de permisos:
    # - SOLO se verifica el menú específico, NO la sección completa
    # - La sección completa solo sirve para mostrar/ocultar el acordeón en el formulario
    menu_group = f'{seccion}.{menu}'
    tiene_menu = menu_group in grupos_usuario
    
    return tiene_menu


def obtener_menus_accesibles(user, seccion):
    """
    Obtiene la lista de menús a los que el usuario tiene acceso en una sección.
    
    Args:
        user: Usuario de Django
        seccion: Nombre de la sección
    
    Returns:
        list: Lista de IDs de menús a los que tiene acceso
    """
    if user.is_superuser:
        # Superuser tiene acceso a todos los menús
        return [menu_id for menu_id, _ in MENUS_POR_SECCION.get(seccion, [])]
    
    if not user.is_authenticated:
        return []
    
    grupos_usuario = [g.name for g in user.groups.all()]
    
    # Obtener SOLO los menús específicos que tiene marcados
    # La sección completa NO otorga acceso automático
    menus_accesibles = []
    for menu_id, _ in MENUS_POR_SECCION.get(seccion, []):
        menu_group = f'{seccion}.{menu_id}'
        if menu_group in grupos_usuario:
            menus_accesibles.append(menu_id)
    
    return menus_accesibles

