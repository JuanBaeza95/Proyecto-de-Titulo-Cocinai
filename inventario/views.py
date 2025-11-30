from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone
from django.db import transaction
from datetime import datetime, timedelta, date
from functools import wraps
import json
from .models import Insumo, Proveedor, Ubicacion, CausaMerma, Plato, Lote, CategoriaProducto, UnidadMedida, MovimientoStock, DetalleCompra, Usuario, Merma, PlatoProducido
from .forms import InsumoForm, ProveedorForm, UbicacionForm, CausaMermaForm, PlatoForm, CategoriaProductoForm, UnidadMedidaForm, MovimientoStockForm, MermaLoteForm, MermaPlatoForm
from usuarios.permissions import menu_required

# Create your views here.

def admin_required(view_func):
    """Decorador para verificar que el usuario sea administrador"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_staff:
            messages.error(request, 'No tienes permisos para acceder a esta sección.')
            return redirect('inventario:index')
        return view_func(request, *args, **kwargs)
    return _wrapped_view

@login_required
def index(request):
    context = {
        'title': 'Inventario - CocinAI',
        'message': 'Módulo de Inventario en desarrollo'
    }
    return render(request, 'inventario/index.html', context)

# ===== GESTIÓN DE INSUMOS =====

@login_required
@menu_required('inventario', 'insumos')
def lista_insumos(request):
    """Lista todos los insumos con filtros y paginación"""
    insumos = Insumo.objects.all()
    
    # Filtros
    busqueda = request.GET.get('busqueda', '')
    
    if busqueda:
        insumos = insumos.filter(
            Q(nombre_insumo__icontains=busqueda) |
            Q(unidad_medida__icontains=busqueda) |
            Q(codigo__icontains=busqueda)
        )
    
    # Paginación
    paginator = Paginator(insumos, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'title': 'Maestro de Insumos',
        'page_obj': page_obj,
        'busqueda': busqueda,
    }
    return render(request, 'inventario/insumos/lista.html', context)

@login_required
@menu_required('inventario', 'insumos')
def crear_insumo(request):
    """Crear un nuevo insumo"""
    if request.method == 'POST':
        form = InsumoForm(request.POST)
        if form.is_valid():
            insumo = form.save()
            messages.success(request, f'Insumo "{insumo.nombre_insumo}" creado exitosamente.')
            return redirect('inventario:lista_insumos')
    else:
        form = InsumoForm()
    
    context = {
        'title': 'Crear Insumo',
        'form': form,
    }
    return render(request, 'inventario/insumos/crear.html', context)

@login_required
@menu_required('inventario', 'insumos')
def editar_insumo(request, insumo_id):
    """Editar un insumo existente"""
    insumo = get_object_or_404(Insumo, id_insumo=insumo_id)
    
    if request.method == 'POST':
        form = InsumoForm(request.POST, instance=insumo)
        if form.is_valid():
            form.save()
            messages.success(request, f'Insumo "{insumo.nombre_insumo}" actualizado exitosamente.')
            return redirect('inventario:lista_insumos')
    else:
        form = InsumoForm(instance=insumo)
    
    context = {
        'title': f'Editar Insumo - {insumo.nombre_insumo}',
        'form': form,
        'insumo': insumo,
    }
    return render(request, 'inventario/insumos/editar.html', context)

@login_required
@menu_required('inventario', 'insumos')
def eliminar_insumo(request, insumo_id):
    """Eliminar un insumo"""
    insumo = get_object_or_404(Insumo, id_insumo=insumo_id)
    
    if request.method == 'POST':
        insumo.delete()
        messages.success(request, f'Insumo "{insumo.nombre_insumo}" eliminado exitosamente.')
        return redirect('inventario:lista_insumos')
    
    context = {
        'title': 'Eliminar Insumo',
        'insumo': insumo,
    }
    return render(request, 'inventario/insumos/eliminar.html', context)

# ===== GESTIÓN DE CATEGORÍAS =====

@login_required
@menu_required('inventario', 'categorias')
def lista_categorias(request):
    """Lista todas las categorías"""
    categorias = CategoriaProducto.objects.all()
    
    context = {
        'title': 'Categorías de Productos',
        'categorias': categorias,
    }
    return render(request, 'inventario/categorias/lista.html', context)

@login_required
@menu_required('inventario', 'categorias')
def crear_categoria(request):
    """Crear una nueva categoría"""
    if request.method == 'POST':
        form = CategoriaProductoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Categoría creada exitosamente.')
            return redirect('inventario:lista_categorias')
    else:
        form = CategoriaProductoForm()
    
    context = {
        'title': 'Crear Categoría',
        'form': form,
    }
    return render(request, 'inventario/categorias/crear.html', context)

# ===== GESTIÓN DE UNIDADES DE MEDIDA =====

@login_required
@menu_required('inventario', 'unidades')
def lista_unidades(request):
    """Lista todas las unidades de medida"""
    unidades = UnidadMedida.objects.all()
    
    context = {
        'title': 'Unidades de Medida',
        'unidades': unidades,
    }
    return render(request, 'inventario/unidades/lista.html', context)

@login_required
@menu_required('inventario', 'unidades')
def crear_unidad(request):
    """Crear una nueva unidad de medida"""
    if request.method == 'POST':
        form = UnidadMedidaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Unidad de medida creada exitosamente.')
            return redirect('inventario:lista_unidades')
    else:
        form = UnidadMedidaForm()
    
    context = {
        'title': 'Crear Unidad de Medida',
        'form': form,
    }
    return render(request, 'inventario/unidades/crear.html', context)

# ===== GESTIÓN DE PROVEEDORES =====

@login_required
@menu_required('inventario', 'proveedores')
def lista_proveedores(request):
    """Lista todos los proveedores con filtros y paginación"""
    proveedores = Proveedor.objects.all()
    
    # Filtros
    busqueda = request.GET.get('busqueda', '')
    
    if busqueda:
        proveedores = proveedores.filter(
            Q(nombre_proveedor__icontains=busqueda) |
            Q(direccion_proveedor__icontains=busqueda) |
            Q(correo_proveedor__icontains=busqueda) |
            Q(telefono_proveedor__icontains=busqueda)
        )
    
    # Paginación
    paginator = Paginator(proveedores, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'title': 'Gestión de Proveedores',
        'page_obj': page_obj,
        'busqueda': busqueda,
    }
    return render(request, 'inventario/proveedores/lista.html', context)

@login_required
@menu_required('inventario', 'proveedores')
def crear_proveedor(request):
    """Crear un nuevo proveedor"""
    if request.method == 'POST':
        form = ProveedorForm(request.POST)
        if form.is_valid():
            proveedor = form.save()
            messages.success(request, f'Proveedor "{proveedor.nombre_proveedor}" creado exitosamente.')
            return redirect('inventario:lista_proveedores')
    else:
        form = ProveedorForm()
    
    context = {
        'title': 'Crear Proveedor',
        'form': form,
    }
    return render(request, 'inventario/proveedores/crear.html', context)

@login_required
@menu_required('inventario', 'proveedores')
def editar_proveedor(request, proveedor_id):
    """Editar un proveedor existente"""
    proveedor = get_object_or_404(Proveedor, id_proveedor=proveedor_id)
    
    if request.method == 'POST':
        form = ProveedorForm(request.POST, instance=proveedor)
        if form.is_valid():
            form.save()
            messages.success(request, f'Proveedor "{proveedor.nombre_proveedor}" actualizado exitosamente.')
            return redirect('inventario:lista_proveedores')
    else:
        form = ProveedorForm(instance=proveedor)
    
    context = {
        'title': f'Editar Proveedor - {proveedor.nombre_proveedor}',
        'form': form,
        'proveedor': proveedor,
    }
    return render(request, 'inventario/proveedores/editar.html', context)

@login_required
@menu_required('inventario', 'proveedores')
def eliminar_proveedor(request, proveedor_id):
    """Eliminar un proveedor"""
    proveedor = get_object_or_404(Proveedor, id_proveedor=proveedor_id)
    
    # Verificar si el proveedor tiene órdenes de compra asociadas
    ordenes_compra = proveedor.ordencompra_set.exists()
    
    if request.method == 'POST':
        proveedor.delete()
        messages.success(request, f'Proveedor "{proveedor.nombre_proveedor}" eliminado exitosamente.')
        return redirect('inventario:lista_proveedores')
    
    context = {
        'title': 'Eliminar Proveedor',
        'proveedor': proveedor,
        'tiene_ordenes': ordenes_compra,
    }
    return render(request, 'inventario/proveedores/eliminar.html', context)

# ===== GESTIÓN DE UBICACIONES =====

@login_required
@menu_required('inventario', 'ubicaciones')
def lista_ubicaciones(request):
    """Lista todas las ubicaciones con filtros y paginación"""
    ubicaciones = Ubicacion.objects.all()
    
    # Filtros
    busqueda = request.GET.get('busqueda', '')
    tipo_filtro = request.GET.get('tipo', '')
    
    if busqueda:
        ubicaciones = ubicaciones.filter(
            Q(nombre_ubicacion__icontains=busqueda) |
            Q(tipo_ubicacion__icontains=busqueda)
        )
    
    if tipo_filtro:
        ubicaciones = ubicaciones.filter(tipo_ubicacion=tipo_filtro)
    
    # Paginación
    paginator = Paginator(ubicaciones, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Tipos de ubicación únicos para el filtro
    tipos_ubicacion = Ubicacion.objects.values_list('tipo_ubicacion', flat=True).distinct()
    
    context = {
        'title': 'Gestión de Ubicaciones',
        'page_obj': page_obj,
        'busqueda': busqueda,
        'tipo_filtro': tipo_filtro,
        'tipos_ubicacion': tipos_ubicacion,
    }
    return render(request, 'inventario/ubicaciones/lista.html', context)

@login_required
@menu_required('inventario', 'ubicaciones')
def crear_ubicacion(request):
    """Crear una nueva ubicación"""
    if request.method == 'POST':
        form = UbicacionForm(request.POST)
        if form.is_valid():
            ubicacion = form.save()
            messages.success(request, f'Ubicación "{ubicacion.nombre_ubicacion}" creada exitosamente.')
            return redirect('inventario:lista_ubicaciones')
    else:
        form = UbicacionForm()
    
    context = {
        'title': 'Crear Ubicación',
        'form': form,
    }
    return render(request, 'inventario/ubicaciones/crear.html', context)

@login_required
@menu_required('inventario', 'ubicaciones')
def editar_ubicacion(request, ubicacion_id):
    """Editar una ubicación existente"""
    ubicacion = get_object_or_404(Ubicacion, id_ubicacion=ubicacion_id)
    
    if request.method == 'POST':
        form = UbicacionForm(request.POST, instance=ubicacion)
        if form.is_valid():
            form.save()
            messages.success(request, f'Ubicación "{ubicacion.nombre_ubicacion}" actualizada exitosamente.')
            return redirect('inventario:lista_ubicaciones')
    else:
        form = UbicacionForm(instance=ubicacion)
    
    context = {
        'title': f'Editar Ubicación - {ubicacion.nombre_ubicacion}',
        'form': form,
        'ubicacion': ubicacion,
    }
    return render(request, 'inventario/ubicaciones/editar.html', context)

@login_required
@menu_required('inventario', 'ubicaciones')
def eliminar_ubicacion(request, ubicacion_id):
    """Eliminar una ubicación"""
    ubicacion = get_object_or_404(Ubicacion, id_ubicacion=ubicacion_id)
    
    # Verificar si la ubicación tiene lotes asociados
    tiene_lotes = ubicacion.lote_set.exists()
    
    if request.method == 'POST':
        ubicacion.delete()
        messages.success(request, f'Ubicación "{ubicacion.nombre_ubicacion}" eliminada exitosamente.')
        return redirect('inventario:lista_ubicaciones')
    
    context = {
        'title': 'Eliminar Ubicación',
        'ubicacion': ubicacion,
        'tiene_lotes': tiene_lotes,
    }
    return render(request, 'inventario/ubicaciones/eliminar.html', context)

# ===== GESTIÓN DE LOTES =====

@login_required
@menu_required('inventario', 'lotes')
def lista_lotes(request):
    """Lista todos los lotes disponibles con filtros avanzados"""
    # Obtener solo lotes con cantidad > 0
    lotes = Lote.objects.filter(cantidad_actual__gt=0)
    
    # Filtros
    busqueda = request.GET.get('busqueda', '')
    ubicacion_id = request.GET.get('ubicacion', '')
    fecha_vencimiento_desde = request.GET.get('fecha_vencimiento_desde', '')
    fecha_vencimiento_hasta = request.GET.get('fecha_vencimiento_hasta', '')
    fecha_ingreso_desde = request.GET.get('fecha_ingreso_desde', '')
    fecha_ingreso_hasta = request.GET.get('fecha_ingreso_hasta', '')
    numero_lote = request.GET.get('numero_lote', '')
    estado_vencimiento = request.GET.get('estado_vencimiento', '')
    orden = request.GET.get('orden', 'fecha_vencimiento')  # Default: ordenar por fecha de vencimiento (FEFO)
    
    # Aplicar filtros
    if busqueda:
        lotes = lotes.filter(
            Q(id_insumo__nombre_insumo__icontains=busqueda) |
            Q(id_insumo__codigo__icontains=busqueda) |
            Q(numero_lote__icontains=busqueda)
        )
    
    if ubicacion_id:
        lotes = lotes.filter(id_ubicacion_id=ubicacion_id)
    
    if fecha_vencimiento_desde:
        try:
            fecha_desde = datetime.strptime(fecha_vencimiento_desde, '%Y-%m-%d').date()
            lotes = lotes.filter(fecha_vencimiento__gte=fecha_desde)
        except ValueError:
            pass
    
    if fecha_vencimiento_hasta:
        try:
            fecha_hasta = datetime.strptime(fecha_vencimiento_hasta, '%Y-%m-%d').date()
            lotes = lotes.filter(fecha_vencimiento__lte=fecha_hasta)
        except ValueError:
            pass
    
    if fecha_ingreso_desde:
        try:
            fecha_ingreso_desde_obj = datetime.strptime(fecha_ingreso_desde, '%Y-%m-%d').date()
            lotes = lotes.filter(fecha_ingreso__gte=fecha_ingreso_desde_obj)
        except ValueError:
            pass
    
    if fecha_ingreso_hasta:
        try:
            fecha_ingreso_hasta_obj = datetime.strptime(fecha_ingreso_hasta, '%Y-%m-%d').date()
            lotes = lotes.filter(fecha_ingreso__lte=fecha_ingreso_hasta_obj)
        except ValueError:
            pass
    
    if numero_lote:
        lotes = lotes.filter(numero_lote__icontains=numero_lote)
    
    # Filtro por estado de vencimiento
    hoy = timezone.now().date()
    if estado_vencimiento == 'vencidos':
        lotes = lotes.filter(fecha_vencimiento__lt=hoy)
    elif estado_vencimiento == 'por_vencer_7':
        lotes = lotes.filter(fecha_vencimiento__gte=hoy, fecha_vencimiento__lte=hoy + timedelta(days=7))
    elif estado_vencimiento == 'por_vencer_30':
        lotes = lotes.filter(fecha_vencimiento__gte=hoy, fecha_vencimiento__lte=hoy + timedelta(days=30))
    elif estado_vencimiento == 'vigentes':
        lotes = lotes.filter(fecha_vencimiento__gt=hoy + timedelta(days=30))
    
    # Ordenamiento
    if orden == 'fecha_vencimiento':
        lotes = lotes.order_by('fecha_vencimiento', 'fecha_ingreso')
    elif orden == 'fecha_ingreso':
        lotes = lotes.order_by('-fecha_ingreso', 'fecha_vencimiento')
    elif orden == 'cantidad':
        lotes = lotes.order_by('-cantidad_actual', 'fecha_vencimiento')
    elif orden == 'numero_lote':
        lotes = lotes.order_by('numero_lote')
    elif orden == 'insumo':
        lotes = lotes.order_by('id_insumo__nombre_insumo', 'fecha_vencimiento')
    
    # Paginación
    paginator = Paginator(lotes, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Calcular estados de vencimiento para cada lote
    lotes_con_estado = []
    for lote in page_obj:
        dias_restantes = (lote.fecha_vencimiento - hoy).days
        if dias_restantes < 0:
            estado = 'vencido'
            dias_mostrar = abs(dias_restantes)  # Para vencidos, mostrar días desde que venció
        elif dias_restantes <= 7:
            estado = 'por_vencer_7'
            dias_mostrar = dias_restantes
        elif dias_restantes <= 30:
            estado = 'por_vencer_30'
            dias_mostrar = dias_restantes
        else:
            estado = 'vigente'
            dias_mostrar = dias_restantes
        lotes_con_estado.append({
            'lote': lote,
            'estado': estado,
            'dias_restantes': dias_restantes,
            'dias_mostrar': dias_mostrar
        })
    
    # Obtener ubicaciones para el filtro
    ubicaciones = Ubicacion.objects.all().order_by('nombre_ubicacion')
    
    context = {
        'title': 'Lotes Disponibles',
        'page_obj': page_obj,
        'lotes_con_estado': lotes_con_estado,
        'busqueda': busqueda,
        'ubicacion_id': ubicacion_id,
        'fecha_vencimiento_desde': fecha_vencimiento_desde,
        'fecha_vencimiento_hasta': fecha_vencimiento_hasta,
        'fecha_ingreso_desde': fecha_ingreso_desde,
        'fecha_ingreso_hasta': fecha_ingreso_hasta,
        'numero_lote': numero_lote,
        'estado_vencimiento': estado_vencimiento,
        'orden': orden,
        'ubicaciones': ubicaciones,
        'hoy': hoy,
    }
    return render(request, 'inventario/lotes/lista.html', context)

# ===== GESTIÓN DE MOVIMIENTOS DE STOCK =====

def obtener_usuario_desde_django_user(user):
    """Helper para obtener o crear el Usuario desde Django User"""
    from inventario.models import Rol
    from django.contrib.auth.hashers import make_password
    
    try:
        # Primero intentar buscar por email
        usuario = Usuario.objects.get(email=user.email)
        return usuario
    except Usuario.DoesNotExist:
        # Si no existe, crear uno automáticamente
        try:
            # Obtener el rol de administrador (o el primero disponible)
            rol_admin = Rol.objects.filter(nombre_rol__icontains='admin').first()
            if not rol_admin:
                # Si no existe rol admin, obtener el primero disponible
                rol_admin = Rol.objects.first()
            
            if not rol_admin:
                # Si no hay roles, crear uno básico
                rol_admin = Rol.objects.create(nombre_rol='administrador')
            
            # Crear el usuario
            nombre_completo = f"{user.first_name} {user.last_name}".strip() or user.username
            usuario = Usuario.objects.create(
                id_rol=rol_admin,
                nombre=nombre_completo,
                email=user.email,
                password_hash=make_password('')  # Password hash vacío ya que se usa Django auth
            )
            return usuario
        except Exception as e:
            # Si hay algún error al crear, intentar obtener cualquier usuario admin como fallback
            try:
                return Usuario.objects.filter(id_rol__nombre_rol__icontains='admin').first()
            except:
                return None
    except Exception as e:
        # Cualquier otro error, intentar obtener cualquier usuario como fallback
        try:
            return Usuario.objects.first()
        except:
            return None

def generar_numero_lote(insumo):
    """
    Genera un número de lote automático basado en el código del insumo
    y un correlativo. Formato: CODIGO-01, CODIGO-02, etc.
    """
    if not insumo.codigo:
        # Si no tiene código, usar las primeras 3 letras del nombre
        codigo_insumo = insumo.nombre_insumo[:3].upper()
    else:
        codigo_insumo = insumo.codigo.upper()
    
    # Buscar todos los lotes para este insumo que empiecen con el código
    lotes_existentes = Lote.objects.filter(
        id_insumo=insumo,
        numero_lote__startswith=codigo_insumo + '-'
    )
    
    # Extraer los números de los lotes existentes y encontrar el mayor
    numeros_existentes = []
    for lote in lotes_existentes:
        try:
            # Extraer el número del formato "CODIGO-XX"
            partes = lote.numero_lote.split('-')
            if len(partes) == 2:
                numero = int(partes[1])
                numeros_existentes.append(numero)
        except (ValueError, IndexError):
            # Si no se puede parsear, ignorar este lote
            continue
    
    # Determinar el siguiente número correlativo
    if numeros_existentes:
        siguiente_numero = max(numeros_existentes) + 1
    else:
        # Si no hay lotes previos, empezar desde 1
        siguiente_numero = 1
    
    # Formatear con 2 dígitos (01, 02, 03, etc.)
    numero_lote = f"{codigo_insumo}-{siguiente_numero:02d}"
    
    return numero_lote

def _obtener_contexto_movimiento(form=None):
    """Helper para obtener el contexto con lotes y ubicaciones para crear movimiento"""
    from datetime import date
    if form is None:
        form = MovimientoStockForm()
    
    lotes_disponibles = Lote.objects.filter(
        cantidad_actual__gt=0,
        fecha_vencimiento__gte=date.today()
    ).select_related('id_insumo', 'id_ubicacion').order_by('fecha_vencimiento', 'fecha_ingreso')
    
    ubicaciones = Ubicacion.objects.all().order_by('nombre_ubicacion')
    
    return {
        'title': 'Crear Movimiento de Stock',
        'form': form,
        'lotes_disponibles': lotes_disponibles,
        'ubicaciones': ubicaciones,
    }

@login_required
@menu_required('inventario', 'movimientos')
def crear_movimiento_stock(request):
    """Crear uno o múltiples movimientos de stock (transferencia, salida o ajuste)"""
    if request.method == 'POST':
        # Obtener el usuario del sistema
        usuario_sistema = obtener_usuario_desde_django_user(request.user)
        if not usuario_sistema:
            messages.error(request, 'Error: No se encontró el usuario en el sistema. Contacte al administrador.')
            return render(request, 'inventario/movimientos/crear.html', _obtener_contexto_movimiento())
        
        # Obtener datos comunes del formulario
        tipo_movimiento = request.POST.get('tipo_movimiento')
        fecha_movimiento_str = request.POST.get('fecha_movimiento')
        ubicacion_destino_id = request.POST.get('id_ubicacion_destino')
        
        # Validar campos comunes
        if not tipo_movimiento:
            messages.error(request, 'Debe seleccionar un tipo de movimiento.')
            return render(request, 'inventario/movimientos/crear.html', _obtener_contexto_movimiento())
        
        if not fecha_movimiento_str:
            messages.error(request, 'Debe seleccionar una fecha de movimiento.')
            return render(request, 'inventario/movimientos/crear.html', _obtener_contexto_movimiento())
        
        try:
            from datetime import datetime
            fecha_movimiento = datetime.strptime(fecha_movimiento_str, '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, 'Fecha de movimiento inválida.')
            return render(request, 'inventario/movimientos/crear.html', _obtener_contexto_movimiento())
        
        if tipo_movimiento == 'transferencia' and not ubicacion_destino_id:
            messages.error(request, 'Debe seleccionar una ubicación destino para transferencias.')
            return render(request, 'inventario/movimientos/crear.html', _obtener_contexto_movimiento())
        
        # Obtener ubicación destino si es transferencia
        ubicacion_destino = None
        if tipo_movimiento == 'transferencia':
            try:
                ubicacion_destino = Ubicacion.objects.get(id_ubicacion=ubicacion_destino_id)
            except Ubicacion.DoesNotExist:
                messages.error(request, 'Ubicación destino no válida.')
                return render(request, 'inventario/movimientos/crear.html', _obtener_contexto_movimiento())
        
        # Procesar múltiples lotes
        # Buscar todos los campos que empiezan con 'lote_' y 'cantidad_'
        lotes_data = []
        i = 0
        while True:
            lote_id_key = f'lote_{i}'
            cantidad_key = f'cantidad_{i}'
            
            if lote_id_key not in request.POST:
                break
            
            lote_id = request.POST.get(lote_id_key)
            cantidad_str = request.POST.get(cantidad_key)
            
            if lote_id and cantidad_str:
                try:
                    from decimal import Decimal
                    cantidad = Decimal(str(cantidad_str))
                    if cantidad > 0:
                        lotes_data.append({
                            'lote_id': int(lote_id),
                            'cantidad': cantidad
                        })
                except (ValueError, TypeError):
                    pass
            
            i += 1
        
        # Si no hay lotes en formato múltiple, intentar formato simple (compatibilidad)
        if not lotes_data:
            lote_id = request.POST.get('id_lote_origen')
            cantidad_str = request.POST.get('cantidad')
            if lote_id and cantidad_str:
                try:
                    from decimal import Decimal
                    cantidad = Decimal(str(cantidad_str))
                    if cantidad > 0:
                        lotes_data.append({
                            'lote_id': int(lote_id),
                            'cantidad': cantidad
                        })
                except (ValueError, TypeError):
                    pass
        
        if not lotes_data:
            messages.error(request, 'Debe agregar al menos un lote con cantidad válida.')
            return render(request, 'inventario/movimientos/crear.html', _obtener_contexto_movimiento())
        
        # Procesar todos los movimientos
        try:
            movimientos_exitosos = 0
            insumos_actualizados = set()
            
            with transaction.atomic():
                for lote_data in lotes_data:
                    try:
                        lote_origen = Lote.objects.select_for_update().get(id_lote=lote_data['lote_id'])
                        cantidad = lote_data['cantidad']
                        
                        # Validar que hay suficiente cantidad
                        if lote_origen.cantidad_actual < cantidad:
                            messages.warning(request, 
                                f'Lote {lote_origen.numero_lote}: cantidad insuficiente. '
                                f'Disponible: {lote_origen.cantidad_actual}, Solicitado: {cantidad}'
                            )
                            continue
                        
                        # Reducir la cantidad del lote origen
                        lote_origen.cantidad_actual -= cantidad
                        lote_origen.save()
                        
                        # Si es transferencia, crear un nuevo lote en la ubicación destino
                        if tipo_movimiento == 'transferencia':
                            # Crear nuevo lote en destino con los mismos datos del origen
                            nuevo_lote = Lote.objects.create(
                                id_detalle_compra=lote_origen.id_detalle_compra,
                                id_insumo=lote_origen.id_insumo,
                                id_ubicacion=ubicacion_destino,
                                costo_unitario=lote_origen.costo_unitario,
                                fecha_vencimiento=lote_origen.fecha_vencimiento,
                                fecha_ingreso=fecha_movimiento,
                                cantidad_actual=cantidad,
                                numero_lote=lote_origen.numero_lote
                            )
                            
                            # Registrar movimiento de entrada en destino
                            MovimientoStock.objects.create(
                                id_lote=nuevo_lote,
                                id_usuario=usuario_sistema,
                                fecha_movimiento=fecha_movimiento,
                                tipo_movimiento='entrada',
                                origen_movimiento='manual',
                                cantidad=cantidad
                            )
                        
                        # Registrar movimiento de salida en origen
                        MovimientoStock.objects.create(
                            id_lote=lote_origen,
                            id_usuario=usuario_sistema,
                            fecha_movimiento=fecha_movimiento,
                            tipo_movimiento=tipo_movimiento,
                            origen_movimiento='manual',
                            cantidad=cantidad
                        )
                        
                        # Marcar insumo para actualizar costo promedio
                        insumos_actualizados.add(lote_origen.id_insumo)
                        movimientos_exitosos += 1
                        
                    except Lote.DoesNotExist:
                        messages.warning(request, f'Lote con ID {lote_data["lote_id"]} no encontrado.')
                    except Exception as e:
                        messages.warning(request, f'Error al procesar lote: {str(e)}')
                
                # Actualizar costo promedio de los insumos afectados
                for insumo in insumos_actualizados:
                    lotes_insumo = Lote.objects.filter(id_insumo=insumo, cantidad_actual__gt=0)
                    if lotes_insumo.exists():
                        costo_total = sum(lote.costo_unitario * lote.cantidad_actual for lote in lotes_insumo)
                        cantidad_total = sum(lote.cantidad_actual for lote in lotes_insumo)
                        insumo.costo_promedio = costo_total / cantidad_total if cantidad_total > 0 else 0
                        insumo.save()
            
            tipo_nombres = {
                'transferencia': 'Transferencia',
                'salida': 'Salida',
                'ajuste': 'Ajuste'
            }
            tipo_nombre = tipo_nombres.get(tipo_movimiento, 'Movimiento')
            
            if movimientos_exitosos > 0:
                if movimientos_exitosos == 1:
                    messages.success(request, f'Movimiento de {tipo_nombre.lower()} registrado exitosamente.')
                else:
                    messages.success(request, f'{movimientos_exitosos} movimientos de {tipo_nombre.lower()} registrados exitosamente.')
                return redirect('inventario:historial_movimientos')
            else:
                messages.error(request, 'No se pudo procesar ningún movimiento. Verifique los datos ingresados.')
                
        except Exception as e:
            messages.error(request, f'Error al crear los movimientos: {str(e)}')
    
    return render(request, 'inventario/movimientos/crear.html', _obtener_contexto_movimiento())

@login_required
@menu_required('inventario', 'movimientos')
def historial_movimientos(request):
    """Lista el historial de movimientos de stock"""
    movimientos = MovimientoStock.objects.select_related(
        'id_lote__id_insumo', 'id_lote__id_ubicacion', 'id_usuario'
    ).all()
    
    # Filtros
    busqueda = request.GET.get('busqueda', '')
    tipo_movimiento = request.GET.get('tipo_movimiento', '')
    origen_movimiento = request.GET.get('origen_movimiento', '')
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    ubicacion_id = request.GET.get('ubicacion', '')
    
    # Aplicar filtros
    if busqueda:
        movimientos = movimientos.filter(
            Q(id_lote__id_insumo__nombre_insumo__icontains=busqueda) |
            Q(id_lote__id_insumo__codigo__icontains=busqueda) |
            Q(id_lote__numero_lote__icontains=busqueda)
        )
    
    if tipo_movimiento:
        movimientos = movimientos.filter(tipo_movimiento=tipo_movimiento)
    
    if origen_movimiento:
        movimientos = movimientos.filter(origen_movimiento=origen_movimiento)
    
    if fecha_desde:
        try:
            fecha_desde_obj = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
            movimientos = movimientos.filter(fecha_movimiento__gte=fecha_desde_obj)
        except ValueError:
            pass
    
    if fecha_hasta:
        try:
            fecha_hasta_obj = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
            movimientos = movimientos.filter(fecha_movimiento__lte=fecha_hasta_obj)
        except ValueError:
            pass
    
    if ubicacion_id:
        movimientos = movimientos.filter(id_lote__id_ubicacion_id=ubicacion_id)
    
    # Paginación
    paginator = Paginator(movimientos, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Obtener ubicaciones para el filtro
    ubicaciones = Ubicacion.objects.all().order_by('nombre_ubicacion')
    
    context = {
        'title': 'Historial de Movimientos',
        'page_obj': page_obj,
        'busqueda': busqueda,
        'tipo_movimiento': tipo_movimiento,
        'origen_movimiento': origen_movimiento,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'ubicacion_id': ubicacion_id,
        'ubicaciones': ubicaciones,
    }
    return render(request, 'inventario/movimientos/historial.html', context)

# ===== GESTIÓN DE CAUSAS DE MERMA =====

@login_required
@menu_required('inventario', 'causas_merma')
def lista_causas_merma(request):
    """Lista todas las causas de merma con filtros y paginación"""
    causas = CausaMerma.objects.all()
    
    # Filtros
    busqueda = request.GET.get('busqueda', '')
    
    if busqueda:
        causas = causas.filter(nombre_causa__icontains=busqueda)
    
    # Ordenamiento
    causas = causas.order_by('nombre_causa')
    
    # Paginación
    paginator = Paginator(causas, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'title': 'Gestión de Causas de Merma',
        'page_obj': page_obj,
        'busqueda': busqueda,
    }
    return render(request, 'inventario/causas_merma/lista.html', context)

@login_required
@menu_required('inventario', 'causas_merma')
def crear_causa_merma(request):
    """Crear una nueva causa de merma"""
    if request.method == 'POST':
        form = CausaMermaForm(request.POST)
        if form.is_valid():
            causa = form.save()
            messages.success(request, f'Causa de merma "{causa.nombre_causa}" creada exitosamente.')
            return redirect('inventario:lista_causas_merma')
    else:
        form = CausaMermaForm()
    
    context = {
        'title': 'Crear Causa de Merma',
        'form': form,
    }
    return render(request, 'inventario/causas_merma/crear.html', context)

@login_required
@menu_required('inventario', 'causas_merma')
def editar_causa_merma(request, causa_id):
    """Editar una causa de merma existente"""
    causa = get_object_or_404(CausaMerma, id_causa=causa_id)
    
    if request.method == 'POST':
        form = CausaMermaForm(request.POST, instance=causa)
        if form.is_valid():
            form.save()
            messages.success(request, f'Causa de merma "{causa.nombre_causa}" actualizada exitosamente.')
            return redirect('inventario:lista_causas_merma')
    else:
        form = CausaMermaForm(instance=causa)
    
    context = {
        'title': f'Editar Causa de Merma - {causa.nombre_causa}',
        'form': form,
        'causa': causa,
    }
    return render(request, 'inventario/causas_merma/editar.html', context)

@login_required
@menu_required('inventario', 'causas_merma')
def eliminar_causa_merma(request, causa_id):
    """Eliminar una causa de merma"""
    causa = get_object_or_404(CausaMerma, id_causa=causa_id)
    
    # Verificar si la causa tiene mermas asociadas
    tiene_mermas = causa.merma_set.exists()
    
    if request.method == 'POST':
        causa.delete()
        messages.success(request, f'Causa de merma "{causa.nombre_causa}" eliminada exitosamente.')
        return redirect('inventario:lista_causas_merma')
    
    context = {
        'title': 'Eliminar Causa de Merma',
        'causa': causa,
        'tiene_mermas': tiene_mermas,
    }
    return render(request, 'inventario/causas_merma/eliminar.html', context)

# ===== GESTIÓN DE MERMAS =====

@login_required
@menu_required('inventario', 'mermas')
def lista_mermas(request):
    """Lista todas las mermas con filtros y paginación"""
    mermas = Merma.objects.all().select_related('id_lote', 'id_plato_producido', 'id_causa', 'id_usuario')
    
    # Filtros
    busqueda = request.GET.get('busqueda', '')
    tipo_merma = request.GET.get('tipo_merma', '')
    causa_id = request.GET.get('causa', '')
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    
    if busqueda:
        mermas = mermas.filter(
            Q(id_lote__id_insumo__nombre_insumo__icontains=busqueda) |
            Q(id_plato_producido__id_plato__nombre_plato__icontains=busqueda) |
            Q(id_causa__nombre_causa__icontains=busqueda)
        )
    
    if tipo_merma:
        mermas = mermas.filter(tipo_merma=tipo_merma)
    
    if causa_id:
        mermas = mermas.filter(id_causa_id=causa_id)
    
    if fecha_desde:
        try:
            fecha_desde_obj = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
            mermas = mermas.filter(fecha_registro__gte=fecha_desde_obj)
        except ValueError:
            pass
    
    if fecha_hasta:
        try:
            fecha_hasta_obj = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
            mermas = mermas.filter(fecha_registro__lte=fecha_hasta_obj)
        except ValueError:
            pass
    
    # Ordenamiento
    mermas = mermas.order_by('-fecha_registro', '-id_merma')
    
    # Paginación
    paginator = Paginator(mermas, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Obtener causas para el filtro
    causas = CausaMerma.objects.all().order_by('nombre_causa')
    
    context = {
        'title': 'Gestión de Mermas',
        'page_obj': page_obj,
        'busqueda': busqueda,
        'tipo_merma': tipo_merma,
        'causa_id': causa_id,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'causas': causas,
    }
    return render(request, 'inventario/mermas/lista.html', context)

@login_required
@menu_required('inventario', 'mermas')
def crear_merma_lote(request):
    """Crear una merma de lote"""
    # Si viene un lote_id en la URL, preseleccionarlo
    lote_id = request.GET.get('lote_id')
    lote_preseleccionado = None
    if lote_id:
        try:
            lote_preseleccionado = Lote.objects.get(id_lote=lote_id, cantidad_actual__gt=0)
        except Lote.DoesNotExist:
            messages.warning(request, 'El lote seleccionado no existe o no tiene stock disponible.')
            lote_id = None
    
    if request.method == 'POST':
        # Si hay un lote preseleccionado, agregarlo al POST (los campos disabled no se envían)
        post_data = request.POST.copy()
        if lote_preseleccionado and 'id_lote' not in post_data:
            post_data['id_lote'] = str(lote_preseleccionado.id_lote)
        
        form = MermaLoteForm(post_data, lote_preseleccionado=lote_preseleccionado)
        if form.is_valid():
            try:
                # Si hay lote preseleccionado, usar ese directamente
                lote = lote_preseleccionado if lote_preseleccionado else form.cleaned_data['id_lote']
                cantidad = form.cleaned_data['cantidad_desperdiciada']
                causa = form.cleaned_data['id_causa']
                fecha_registro = form.cleaned_data['fecha_registro']
                
                # Validar que la cantidad no exceda la disponible
                if cantidad > lote.cantidad_actual:
                    messages.error(request, f'La cantidad no puede ser mayor a la disponible en el lote ({lote.cantidad_actual} {lote.id_insumo.unidad_medida}).')
                    context = {
                        'title': 'Registrar Merma de Lote',
                        'form': form,
                    }
                    return render(request, 'inventario/mermas/crear_lote.html', context)
                
                # Obtener usuario (fuera del bloque atómico)
                usuario = obtener_usuario_desde_django_user(request.user)
                if not usuario:
                    messages.error(request, 'Error al obtener el usuario del sistema.')
                    context = {
                        'title': 'Registrar Merma de Lote',
                        'form': form,
                    }
                    return render(request, 'inventario/mermas/crear_lote.html', context)
                
                # Bloque atómico solo para las operaciones de base de datos
                with transaction.atomic():
                    # Crear la merma
                    merma = Merma.objects.create(
                        tipo_merma='lote',
                        id_lote=lote,
                        id_causa=causa,
                        id_usuario=usuario,
                        fecha_registro=fecha_registro,
                        cantidad_desperdiciada=cantidad
                    )
                    
                    # Descontar del lote
                    lote.cantidad_actual -= cantidad
                    lote.save()
                    
                    # Crear movimiento de stock
                    MovimientoStock.objects.create(
                        id_lote=lote,
                        id_usuario=usuario,
                        fecha_movimiento=fecha_registro,
                        tipo_movimiento='salida',
                        origen_movimiento='merma',
                        cantidad=cantidad
                    )
                
                messages.success(request, f'Merma de lote registrada exitosamente. Se descontaron {cantidad} {lote.id_insumo.unidad_medida} del lote {lote.numero_lote}.')
                return redirect('inventario:lista_mermas')
            except Exception as e:
                messages.error(request, f'Error al registrar la merma: {str(e)}')
                # Re-renderizar el formulario con los datos iniciales
                form = MermaLoteForm(initial={
                    'id_lote': form.cleaned_data.get('id_lote'),
                    'id_causa': form.cleaned_data.get('id_causa'),
                    'cantidad_desperdiciada': form.cleaned_data.get('cantidad_desperdiciada'),
                    'fecha_registro': form.cleaned_data.get('fecha_registro'),
                })
    else:
        # Si hay un lote preseleccionado, inicializar el formulario con ese lote
        initial_data = {}
        if lote_preseleccionado:
            initial_data['id_lote'] = lote_preseleccionado
        form = MermaLoteForm(initial=initial_data, lote_preseleccionado=lote_preseleccionado)
    
    # Preparar información de lotes para JavaScript
    lotes_info_json = '{}'
    if hasattr(form, 'lotes_info') and form.lotes_info:
        lotes_info_json = json.dumps(form.lotes_info)
    
    context = {
        'title': 'Registrar Merma de Lote',
        'form': form,
        'lotes_info_json': lotes_info_json,
        'lote_preseleccionado': lote_preseleccionado,  # Para deshabilitar el campo en el template
    }
    return render(request, 'inventario/mermas/crear_lote.html', context)

@login_required
@menu_required('inventario', 'mermas')
def crear_merma_plato(request):
    """Crear una merma de plato producido"""
    if request.method == 'POST':
        form = MermaPlatoForm(request.POST)
        if form.is_valid():
            try:
                plato_producido = form.cleaned_data['id_plato_producido']
                cantidad = form.cleaned_data['cantidad_desperdiciada']
                causa = form.cleaned_data['id_causa']
                fecha_registro = form.cleaned_data['fecha_registro']
                
                # Obtener usuario (fuera del bloque atómico)
                usuario = obtener_usuario_desde_django_user(request.user)
                if not usuario:
                    messages.error(request, 'Error al obtener el usuario del sistema.')
                    context = {
                        'title': 'Registrar Merma de Plato',
                        'form': form,
                    }
                    return render(request, 'inventario/mermas/crear_plato.html', context)
                
                # Bloque atómico solo para las operaciones de base de datos
                with transaction.atomic():
                    # Crear la merma
                    merma = Merma.objects.create(
                        tipo_merma='plato',
                        id_plato_producido=plato_producido,
                        id_causa=causa,
                        id_usuario=usuario,
                        fecha_registro=fecha_registro,
                        cantidad_desperdiciada=cantidad
                    )
                    
                    # Marcar el plato como entregado para que no aparezca más en listas disponibles
                    # (ya que fue mermado, no puede ser entregado a un cliente)
                    plato_producido.estado = 'entregado'
                    plato_producido.fecha_entrega = timezone.now()
                    plato_producido.save()
                
                messages.success(request, f'Merma de plato registrada exitosamente. Se registraron {cantidad} unidades del plato {plato_producido.id_plato.nombre_plato}. El plato ha sido marcado como entregado (mermado).')
                return redirect('inventario:lista_mermas')
            except Exception as e:
                messages.error(request, f'Error al registrar la merma: {str(e)}')
                # Re-renderizar el formulario con los datos iniciales
                form = MermaPlatoForm(initial={
                    'id_plato_producido': form.cleaned_data.get('id_plato_producido'),
                    'id_causa': form.cleaned_data.get('id_causa'),
                    'cantidad_desperdiciada': form.cleaned_data.get('cantidad_desperdiciada'),
                    'fecha_registro': form.cleaned_data.get('fecha_registro'),
                })
    else:
        # Si viene un plato_producido_id en la URL, pre-seleccionarlo
        plato_producido_id = request.GET.get('plato_producido_id')
        initial_data = {}
        if plato_producido_id:
            try:
                plato_producido = PlatoProducido.objects.get(id_plato_producido=plato_producido_id)
                initial_data['id_plato_producido'] = plato_producido
            except PlatoProducido.DoesNotExist:
                pass
        form = MermaPlatoForm(initial=initial_data)
    
    context = {
        'title': 'Registrar Merma de Plato',
        'form': form,
    }
    return render(request, 'inventario/mermas/crear_plato.html', context)
