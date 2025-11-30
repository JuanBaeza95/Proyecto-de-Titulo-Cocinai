from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User, Group
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from functools import wraps
from .forms import UsuarioCrearForm, UsuarioEditarForm, CambiarContrasenaForm
from .menus import MENUS_POR_SECCION, obtener_secciones


def superuser_required(view_func):
    """Decorador para verificar que el usuario sea superuser.
    Debe usarse después de @login_required para asegurar que el usuario esté autenticado.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        # Como @login_required ya verifica la autenticación, solo verificamos si es superuser
        if not request.user.is_superuser:
            messages.error(request, 'No tienes permisos para acceder a esta sección. Solo los administradores pueden gestionar usuarios.')
            return redirect('dashboard')
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view


@login_required 
def dashboard(request):
    """Dashboard principal - movido aquí desde usuarios para evitar importación circular"""
    # Obtener nombres de grupos del usuario para verificar acceso
    grupos_usuario = [g.name for g in request.user.groups.all()]
    
    # Limpiar la marca de mensaje de permiso después de mostrar el dashboard
    if 'permiso_denegado_mensaje' in request.session:
        del request.session['permiso_denegado_mensaje']
    
    context = {
        'username': request.user.username,
        'title': 'Dashboard Principal de CocinAI',
        'grupos_usuario': grupos_usuario,
    }
    return render(request, 'dashboard.html', context)


@login_required
@superuser_required
def lista_usuarios(request):
    """Lista todos los usuarios (solo superuser)"""
    usuarios = User.objects.all().order_by('username')
    
    # Filtros
    busqueda = request.GET.get('busqueda', '')
    if busqueda:
        usuarios = usuarios.filter(
            Q(username__icontains=busqueda) |
            Q(email__icontains=busqueda) |
            Q(first_name__icontains=busqueda) |
            Q(last_name__icontains=busqueda)
        )
    
    # Paginación
    paginator = Paginator(usuarios, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'title': 'Gestión de Usuarios',
        'page_obj': page_obj,
        'busqueda': busqueda,
    }
    return render(request, 'usuarios/lista.html', context)


@login_required
@superuser_required
def crear_usuario(request):
    """Crear un nuevo usuario (solo superuser)"""
    if request.method == 'POST':
        form = UsuarioCrearForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f'Usuario "{user.username}" creado exitosamente.')
            return redirect('usuarios:lista_usuarios')
    else:
        form = UsuarioCrearForm()
    
    context = {
        'title': 'Crear Usuario',
        'form': form,
        'menus_por_seccion': MENUS_POR_SECCION,
        'secciones': obtener_secciones(),
    }
    return render(request, 'usuarios/crear.html', context)


@login_required
@superuser_required
def editar_usuario(request, user_id):
    """Editar un usuario (solo superuser)"""
    usuario = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        form = UsuarioEditarForm(request.POST, instance=usuario)
        if form.is_valid():
            form.save()
            messages.success(request, f'Usuario "{usuario.username}" actualizado exitosamente.')
            return redirect('usuarios:lista_usuarios')
    else:
        form = UsuarioEditarForm(instance=usuario)
    
    context = {
        'title': 'Editar Usuario',
        'form': form,
        'usuario': usuario,
        'menus_por_seccion': MENUS_POR_SECCION,
        'secciones': obtener_secciones(),
    }
    return render(request, 'usuarios/editar.html', context)


@login_required
@superuser_required
def eliminar_usuario(request, user_id):
    """Eliminar un usuario (solo superuser)"""
    usuario = get_object_or_404(User, id=user_id)
    
    # No permitir eliminar al superuser actual
    if usuario == request.user:
        messages.error(request, 'No puedes eliminar tu propio usuario.')
        return redirect('usuarios:lista_usuarios')
    
    if request.method == 'POST':
        username = usuario.username
        usuario.delete()
        messages.success(request, f'Usuario "{username}" eliminado exitosamente.')
        return redirect('usuarios:lista_usuarios')
    
    context = {
        'title': 'Eliminar Usuario',
        'usuario': usuario,
    }
    return render(request, 'usuarios/eliminar.html', context)


@login_required
def cambiar_contrasena(request):
    """Cambiar contraseña (cualquier usuario puede cambiar la suya)"""
    if request.method == 'POST':
        form = CambiarContrasenaForm(user=request.user, data=request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Tu contraseña ha sido cambiada exitosamente.')
            return redirect('dashboard')
    else:
        form = CambiarContrasenaForm(user=request.user)
    
    context = {
        'title': 'Cambiar Contraseña',
        'form': form,
    }
    return render(request, 'usuarios/cambiar_contrasena.html', context)


@login_required
def index(request):
    """Página principal de usuarios - accesible para todos los usuarios autenticados
    Los superusers ven el dashboard completo, los demás solo ven la opción de cambiar contraseña
    """
    # Limpiar mensajes de permisos acumulados al entrar a usuarios
    # Consumir todos los mensajes de permisos para evitar que se muestren
    storage = messages.get_messages(request)
    for message in storage:
        # Los mensajes se consumen automáticamente al iterar
        pass
    
    context = {
        'title': 'Gestión de Usuarios',
    }
    
    # Solo cargar estadísticas si es superuser (para mostrar en el template)
    if request.user.is_superuser:
        usuarios_count = User.objects.count()
        usuarios_activos = User.objects.filter(is_active=True).count()
        usuarios_inactivos = usuarios_count - usuarios_activos
        context['usuarios_count'] = usuarios_count
        context['usuarios_activos'] = usuarios_activos
        context['usuarios_inactivos'] = usuarios_inactivos
    
    return render(request, 'usuarios/index.html', context)
