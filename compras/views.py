from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Sum, F
from django.db import transaction
from functools import wraps
from datetime import date
from inventario.models import OrdenCompra, DetalleCompra, Proveedor, Insumo, Lote, MovimientoStock, Usuario, Ubicacion
from .forms import OrdenCompraForm, DetalleCompraFormSet, RecepcionDetalleForm
from django.forms import formset_factory
from usuarios.permissions import menu_required

# Create your views here.

def admin_required(view_func):
    """Decorador para verificar que el usuario sea administrador"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_staff:
            messages.error(request, 'No tienes permisos para acceder a esta sección.')
            return redirect('compras:index')
        return view_func(request, *args, **kwargs)
    return _wrapped_view

@login_required
def index(request):
    """Página principal de compras"""
    ordenes = OrdenCompra.objects.all()[:5]  # Últimas 5 órdenes
    context = {
        'title': 'Compras - CocinAI',
        'ordenes_recientes': ordenes,
    }
    return render(request, 'compras/index.html', context)

@login_required
@menu_required('compras', 'ordenes')
def lista_ordenes(request):
    """Lista todas las órdenes de compra con filtros y paginación"""
    ordenes = OrdenCompra.objects.select_related('id_proveedor').annotate(
        total_estimado=Sum(F('detallecompra__cantidad_pedida') * F('detallecompra__costo_unitario_acordado'))
    ).all()
    
    # Filtros
    estado_filtro = request.GET.get('estado', '')
    busqueda = request.GET.get('busqueda', '')
    
    if estado_filtro:
        ordenes = ordenes.filter(estado=estado_filtro)
    
    if busqueda:
        ordenes = ordenes.filter(
            Q(id_orden_compra__icontains=busqueda) |
            Q(id_proveedor__nombre_proveedor__icontains=busqueda)
        )
    
    # Ordenar por fecha más reciente
    ordenes = ordenes.order_by('-fecha_pedido')
    
    # Paginación
    paginator = Paginator(ordenes, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'title': 'Órdenes de Compra',
        'page_obj': page_obj,
        'estado_filtro': estado_filtro,
        'busqueda': busqueda,
        'estados': ['pendiente', 'en_proceso', 'recibida', 'cancelada'],
    }
    return render(request, 'compras/ordenes/lista.html', context)

@login_required
@menu_required('compras', 'ordenes')
def crear_orden(request):
    """Crear una nueva orden de compra con sus detalles"""
    if request.method == 'POST':
        form = OrdenCompraForm(request.POST)
        formset = DetalleCompraFormSet(request.POST)
        
        if form.is_valid() and formset.is_valid():
            orden = form.save()
            formset.instance = orden
            formset.save()
            
            messages.success(request, f'Orden de compra #{orden.id_orden_compra} creada exitosamente.')
            return redirect('compras:detalle_orden', orden_id=orden.id_orden_compra)
        else:
            # Mostrar errores del formulario
            if not form.is_valid():
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f'Error en {form.fields[field].label}: {error}')
            # Mostrar errores del formset
            if not formset.is_valid():
                for form_item in formset:
                    if form_item.errors:
                        for field, errors in form_item.errors.items():
                            for error in errors:
                                messages.error(request, f'Error en detalle: {error}')
    else:
        form = OrdenCompraForm()
        formset = DetalleCompraFormSet()
    
    context = {
        'title': 'Crear Orden de Compra',
        'form': form,
        'formset': formset,
    }
    return render(request, 'compras/ordenes/crear.html', context)

@login_required
@menu_required('compras', 'ordenes')
def detalle_orden(request, orden_id):
    """Ver los detalles de una orden de compra"""
    orden = get_object_or_404(OrdenCompra.objects.select_related('id_proveedor'), id_orden_compra=orden_id)
    detalles = DetalleCompra.objects.select_related('id_insumo').filter(id_orden_compra=orden)
    
    # Calcular totales y subtotales
    detalles_con_subtotal = []
    total_estimado = 0
    for detalle in detalles:
        subtotal = float(detalle.cantidad_pedida) * float(detalle.costo_unitario_acordado)
        total_estimado += subtotal
        detalles_con_subtotal.append({
            'detalle': detalle,
            'subtotal': subtotal
        })
    
    context = {
        'title': f'Orden de Compra #{orden.id_orden_compra}',
        'orden': orden,
        'detalles_con_subtotal': detalles_con_subtotal,
        'total_estimado': total_estimado,
    }
    return render(request, 'compras/ordenes/detalle.html', context)

@login_required
@menu_required('compras', 'ordenes')
def editar_orden(request, orden_id):
    """Editar una orden de compra existente"""
    orden = get_object_or_404(OrdenCompra, id_orden_compra=orden_id)
    
    if request.method == 'POST':
        form = OrdenCompraForm(request.POST, instance=orden)
        formset = DetalleCompraFormSet(request.POST, instance=orden)
        
        if form.is_valid():
            orden = form.save()
            if formset.is_valid():
                formset.save()
                messages.success(request, f'Orden de compra #{orden.id_orden_compra} actualizada exitosamente.')
                return redirect('compras:detalle_orden', orden_id=orden.id_orden_compra)
            else:
                # Mostrar errores del formset
                for form_item in formset.forms:
                    if form_item.errors:
                        for field, errors in form_item.errors.items():
                            for error in errors:
                                messages.error(request, f'Error en detalle ({field}): {error}')
                if formset.non_form_errors():
                    for error in formset.non_form_errors():
                        messages.error(request, f'Error en el formset: {error}')
        else:
            # Mostrar errores del formulario principal
            for field, errors in form.errors.items():
                for error in errors:
                    field_label = form.fields[field].label if field in form.fields else field
                    messages.error(request, f'Error en {field_label}: {error}')
    else:
        form = OrdenCompraForm(instance=orden)
        formset = DetalleCompraFormSet(instance=orden)
    
    context = {
        'title': f'Editar Orden de Compra #{orden.id_orden_compra}',
        'form': form,
        'formset': formset,
        'orden': orden,
    }
    return render(request, 'compras/ordenes/editar.html', context)

@login_required
@menu_required('compras', 'ordenes')
def eliminar_orden(request, orden_id):
    """Eliminar una orden de compra"""
    orden = get_object_or_404(OrdenCompra, id_orden_compra=orden_id)
    
    if request.method == 'POST':
        numero_orden = orden.id_orden_compra
        orden.delete()
        messages.success(request, f'Orden de compra #{numero_orden} eliminada exitosamente.')
        return redirect('compras:lista_ordenes')
    
    # Verificar si tiene detalles
    detalles = orden.detallecompra_set.exists()
    
    context = {
        'title': 'Eliminar Orden de Compra',
        'orden': orden,
        'tiene_detalles': detalles,
    }
    return render(request, 'compras/ordenes/eliminar.html', context)


def generar_numero_lote(insumo):
    """
    Genera un número de lote automático basado en el código del insumo
    y un correlativo. Formato: CODIGO-01, CODIGO-02, etc.
    
    Ejemplo: Si el insumo tiene código "TOM", genera "TOM-01", "TOM-02", etc.
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


@login_required
@menu_required('compras', 'ordenes')
def recepcionar_orden(request, orden_id):
    """Recepcionar una orden de compra creando los lotes correspondientes"""
    orden = get_object_or_404(
        OrdenCompra.objects.select_related('id_proveedor'),
        id_orden_compra=orden_id
    )
    
    # Verificar que la orden no esté cancelada
    if orden.estado == 'cancelada':
        messages.error(request, 'No se puede recepcionar una orden cancelada.')
        return redirect('compras:detalle_orden', orden_id=orden_id)
    
    # Obtener todos los detalles de la orden
    detalles = DetalleCompra.objects.select_related('id_insumo').filter(id_orden_compra=orden)
    
    if not detalles.exists():
        messages.error(request, 'La orden no tiene detalles para recepcionar.')
        return redirect('compras:detalle_orden', orden_id=orden_id)
    
    # Obtener el usuario del sistema
    usuario_sistema = obtener_usuario_desde_django_user(request.user)
    if not usuario_sistema:
        messages.error(request, 'Error: No se encontró el usuario en el sistema. Contacte al administrador.')
        return redirect('compras:detalle_orden', orden_id=orden_id)
    
    # Crear formset con los detalles existentes
    # Necesitamos crear un formset con exactamente el número de detalles
    num_detalles = len(detalles)
    RecepcionFormSet = formset_factory(
        RecepcionDetalleForm,
        extra=0,
        can_delete=False,
        min_num=num_detalles,
        max_num=num_detalles
    )
    
    formset_data = []
    for detalle in detalles:
        formset_data.append({
            'detalle_id': detalle.id_detalle_compra,
            'cantidad_recibida': detalle.cantidad_pendiente(),  # Cantidad pendiente por defecto
            'costo_unitario_real': detalle.costo_unitario_acordado,
            'fecha_ingreso': date.today(),
        })
    
    if request.method == 'POST':
        formset = RecepcionFormSet(request.POST, initial=formset_data)
        
        if formset.is_valid():
            lotes_creados = 0
            
            try:
                with transaction.atomic():
                    for form in formset:
                        if form.cleaned_data.get('recibir'):
                            detalle_id = form.cleaned_data['detalle_id']
                            detalle = DetalleCompra.objects.get(id_detalle_compra=detalle_id)
                            
                            cantidad_recibida = form.cleaned_data['cantidad_recibida']
                            fecha_vencimiento = form.cleaned_data['fecha_vencimiento']
                            fecha_ingreso = form.cleaned_data['fecha_ingreso']
                            ubicacion = form.cleaned_data['id_ubicacion']
                            costo_unitario_real = form.cleaned_data['costo_unitario_real']
                            
                            # Verificar que no exceda la cantidad pendiente (a menos que se permita recibir más)
                            cantidad_pendiente = detalle.cantidad_pendiente()
                            
                            # Generar número de lote automático
                            numero_lote = generar_numero_lote(detalle.id_insumo)
                            
                            # Crear el lote
                            lote = Lote.objects.create(
                                id_detalle_compra=detalle,
                                id_insumo=detalle.id_insumo,
                                id_ubicacion=ubicacion,
                                costo_unitario=costo_unitario_real,
                                fecha_vencimiento=fecha_vencimiento,
                                fecha_ingreso=fecha_ingreso,
                                cantidad_actual=cantidad_recibida,
                                numero_lote=numero_lote
                            )
                            
                            # Crear movimiento de stock
                            MovimientoStock.objects.create(
                                id_lote=lote,
                                id_usuario=usuario_sistema,
                                fecha_movimiento=fecha_ingreso,
                                tipo_movimiento='entrada',
                                origen_movimiento='compra',
                                cantidad=cantidad_recibida
                            )
                            
                            # Actualizar costo promedio del insumo
                            # Calcular promedio ponderado con todos los lotes del insumo
                            insumo = detalle.id_insumo
                            lotes_insumo = Lote.objects.filter(id_insumo=insumo)
                            
                            total_cantidad = sum(float(l.cantidad_actual) for l in lotes_insumo)
                            if total_cantidad > 0:
                                costo_total = sum(float(l.cantidad_actual) * float(l.costo_unitario) for l in lotes_insumo)
                                costo_promedio = costo_total / total_cantidad
                                insumo.costo_promedio = round(costo_promedio, 2)
                                insumo.save()
                            
                            lotes_creados += 1
                    
                    # Actualizar estado de la orden
                    # Verificar si todos los detalles están completamente recibidos
                    todos_recibidos = all(detalle.esta_completamente_recibido() for detalle in detalles)
                    if todos_recibidos:
                        orden.estado = 'recibida'
                    elif orden.estado == 'pendiente':
                        orden.estado = 'en_proceso'
                    orden.save()
                    
                    if lotes_creados > 0:
                        messages.success(
                            request,
                            f'Se recepcionaron {lotes_creados} lote(s) exitosamente. '
                            f'Orden actualizada a estado: {orden.get_estado_display() if hasattr(orden, "get_estado_display") else orden.estado}'
                        )
                        return redirect('compras:detalle_orden', orden_id=orden_id)
                    else:
                        messages.warning(request, 'No se seleccionó ningún detalle para recepcionar.')
            except Exception as e:
                messages.error(request, f'Error al recepcionar la orden: {str(e)}')
        else:
            # Mostrar errores del formset
            for form in formset:
                if form.errors:
                    for field, errors in form.errors.items():
                        for error in errors:
                            messages.error(request, f'Error en {field}: {error}')
    else:
        # Preparar formset inicial con la cantidad correcta de forms
        formset = RecepcionFormSet(initial=formset_data)
        
        # Inicializar cada formulario con su detalle
        for i, (form, detalle) in enumerate(zip(formset.forms, detalles)):
            form.fields['detalle_id'].initial = detalle.id_detalle_compra
            form.fields['cantidad_recibida'].initial = detalle.cantidad_pendiente()
            form.fields['costo_unitario_real'].initial = detalle.costo_unitario_acordado
            form.fields['fecha_ingreso'].initial = date.today()
            form.fields['id_ubicacion'].queryset = Ubicacion.objects.all().order_by('nombre_ubicacion')
    
    # Preparar información de detalles para mostrar (combinar con forms)
    detalles_con_forms = []
    for i, detalle in enumerate(detalles):
        form = formset.forms[i] if i < len(formset.forms) else None
        detalles_con_forms.append({
            'detalle': detalle,
            'form': form,
            'cantidad_recibida': detalle.cantidad_recibida(),
            'cantidad_pendiente': detalle.cantidad_pendiente(),
            'completamente_recibido': detalle.esta_completamente_recibido(),
        })
    
    context = {
        'title': f'Recepcionar Orden de Compra #{orden.id_orden_compra}',
        'orden': orden,
        'formset': formset,
        'detalles_con_forms': detalles_con_forms,
    }
    return render(request, 'compras/ordenes/recepcionar.html', context)
