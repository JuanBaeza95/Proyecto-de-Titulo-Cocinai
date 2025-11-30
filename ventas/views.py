from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.db import transaction
from inventario.models import (
    Plato, Usuario, Ubicacion, PlatoProducido
)
from .forms import MoverPlatoMesaForm, ComandaForm, DetalleComandaInlineFormSet
from .models import MovimientoMesa, Comanda, DetalleComanda, Mesa
from usuarios.permissions import menu_required


def obtener_usuario_desde_django_user(user):
    """Helper para obtener o crear el Usuario desde Django User"""
    from inventario.models import Rol
    from django.contrib.auth.hashers import make_password
    
    try:
        usuario = Usuario.objects.get(email=user.email)
        return usuario
    except Usuario.DoesNotExist:
        try:
            rol_admin = Rol.objects.filter(nombre_rol__icontains='admin').first()
            if not rol_admin:
                rol_admin = Rol.objects.first()
            
            if not rol_admin:
                rol_admin = Rol.objects.create(nombre_rol='administrador')
            
            nombre_completo = f"{user.first_name} {user.last_name}".strip() or user.username
            usuario = Usuario.objects.create(
                id_rol=rol_admin,
                nombre=nombre_completo,
                email=user.email,
                password_hash=make_password('')
            )
            return usuario
        except Exception as e:
            try:
                return Usuario.objects.filter(id_rol__nombre_rol__icontains='admin').first()
            except:
                return None
    except Exception as e:
        try:
            return Usuario.objects.first()
        except:
            return None


@login_required
def index(request):
    """Página principal de ventas"""
    context = {
        'title': 'Ventas - CocinAI',
    }
    return render(request, 'ventas/index.html', context)


# ========== MOVER PLATOS A MESA ==========

@login_required
@menu_required('ventas', 'mover_mesa')
def mover_plato_a_mesa(request, plato_producido_id):
    """Mover un plato producido de cocina a una mesa específica"""
    plato_producido = get_object_or_404(
        PlatoProducido.objects.select_related('id_plato', 'id_ubicacion'),
        id_plato_producido=plato_producido_id
    )
    
    if plato_producido.estado != 'en_cocina':
        messages.warning(
            request,
            f'El plato solo se puede mover a mesa si está en cocina. Estado actual: {plato_producido.get_estado_display()}'
        )
        return redirect('produccion:lista_platos_producidos')
    
    if request.method == 'POST':
        form = MoverPlatoMesaForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    ubicacion_mesa = form.cleaned_data['id_ubicacion']
                    numero_mesa = form.cleaned_data.get('numero_mesa', '').strip()
                    observaciones = form.cleaned_data.get('observaciones', '')
                    
                    # Obtener usuario del sistema
                    usuario_sistema = obtener_usuario_desde_django_user(request.user)
                    if not usuario_sistema:
                        raise ValueError('Error: No se encontró el usuario en el sistema. Contacte al administrador.')
                    
                    # Actualizar plato producido
                    plato_producido.id_ubicacion = ubicacion_mesa
                    plato_producido.estado = 'en_mesa'
                    plato_producido.save()
                    
                    # Crear registro de movimiento a mesa
                    MovimientoMesa.objects.create(
                        id_plato_producido=plato_producido,
                        id_ubicacion=ubicacion_mesa,
                        numero_mesa=numero_mesa if numero_mesa else None,
                        id_usuario=usuario_sistema,
                        observaciones=observaciones
                    )
                
                mensaje = f'Plato "{plato_producido.id_plato.nombre_plato}" movido a {ubicacion_mesa.nombre_ubicacion}'
                if numero_mesa:
                    mensaje += f' (Mesa {numero_mesa})'
                mensaje += ' exitosamente.'
                messages.success(request, mensaje)
                return redirect('ventas:historial_movimientos_mesa')
            except ValueError as e:
                messages.error(request, str(e))
            except Exception as e:
                messages.error(request, f'Error al mover el plato: {str(e)}')
    else:
        form = MoverPlatoMesaForm()
    
    context = {
        'title': 'Mover Plato a Mesa',
        'plato_producido': plato_producido,
        'form': form,
    }
    return render(request, 'ventas/movimientos/mover_mesa.html', context)


# ========== GESTIÓN DE MESAS Y CIERRE DE VENTAS ==========

@login_required
@menu_required('ventas', 'mesas')
def lista_mesas_activas(request):
    """Lista las mesas con platos en estado 'en_mesa', agrupadas por ubicación y número de mesa"""
    # Obtener todos los platos en estado 'en_mesa'
    platos_en_mesa = PlatoProducido.objects.filter(
        estado='en_mesa'
    ).select_related('id_plato', 'id_ubicacion', 'id_usuario').order_by('id_ubicacion', 'fecha_produccion')
    
    # Obtener todos los movimientos a mesa para estos platos
    platos_ids = list(platos_en_mesa.values_list('id_plato_producido', flat=True))
    movimientos = MovimientoMesa.objects.filter(
        id_plato_producido__in=platos_ids
    ).select_related('id_ubicacion').order_by('id_plato_producido', '-fecha_movimiento')
    
    # Crear un diccionario de plato_id -> último movimiento (más reciente)
    movimientos_por_plato = {}
    for movimiento in movimientos:
        plato_id = movimiento.id_plato_producido_id
        # Solo guardar el primero (más reciente) para cada plato
        if plato_id not in movimientos_por_plato:
            movimientos_por_plato[plato_id] = movimiento
    
    # Agrupar por ubicación y número de mesa
    mesas_dict = {}
    for plato in platos_en_mesa:
        # Obtener el movimiento para este plato
        movimiento = movimientos_por_plato.get(plato.id_plato_producido)
        
        if movimiento:
            ubicacion = movimiento.id_ubicacion
            # Normalizar número de mesa: si está vacío, None o solo espacios, usar 'Sin número'
            numero_mesa_raw = movimiento.numero_mesa
            if numero_mesa_raw and numero_mesa_raw.strip():
                numero_mesa = numero_mesa_raw.strip()
            else:
                numero_mesa = 'Sin número'
            clave = f"{ubicacion.id_ubicacion}_{numero_mesa}"
        else:
            # Si no hay movimiento, usar la ubicación del plato
            ubicacion = plato.id_ubicacion
            numero_mesa = 'Sin número'
            clave = f"{ubicacion.id_ubicacion}_{numero_mesa}"
        
        if clave not in mesas_dict:
            mesas_dict[clave] = {
                'ubicacion': ubicacion,
                'numero_mesa': numero_mesa,
                'platos': []
            }
        
        mesas_dict[clave]['platos'].append(plato)
    
    # Convertir a lista ordenada
    mesas = sorted(mesas_dict.values(), key=lambda x: (x['ubicacion'].nombre_ubicacion, x['numero_mesa']))
    
    # Filtros
    ubicacion_id = request.GET.get('ubicacion', '')
    numero_mesa_filtro = request.GET.get('numero_mesa', '')
    
    if ubicacion_id:
        mesas = [m for m in mesas if m['ubicacion'].id_ubicacion == int(ubicacion_id)]
    
    if numero_mesa_filtro:
        mesas = [m for m in mesas if numero_mesa_filtro.lower() in m['numero_mesa'].lower()]
    
    # Obtener ubicaciones de tipo mesa para el filtro
    ubicaciones_mesa = Ubicacion.objects.filter(
        tipo_ubicacion__iexact='mesa'
    ).order_by('nombre_ubicacion')
    
    if not ubicaciones_mesa.exists():
        ubicaciones_mesa = Ubicacion.objects.filter(
            tipo_ubicacion__icontains='mesa'
        ).order_by('nombre_ubicacion')
    
    context = {
        'title': 'Mesas Activas',
        'mesas': mesas,
        'ubicacion_id': ubicacion_id,
        'numero_mesa_filtro': numero_mesa_filtro,
        'ubicaciones_mesa': ubicaciones_mesa,
    }
    return render(request, 'ventas/mesas/lista_activas.html', context)


@login_required
@menu_required('ventas', 'cerrar_venta')
def cerrar_venta_mesa(request):
    """Cerrar la venta de una mesa, cambiando el estado de los platos de 'en_mesa' a 'venta'"""
    if request.method == 'POST':
        ubicacion_id = request.POST.get('ubicacion_id')
        numero_mesa = request.POST.get('numero_mesa', '').strip()
        platos_ids = request.POST.getlist('platos_ids')
        
        if not platos_ids:
            messages.error(request, 'Debe seleccionar al menos un plato para cerrar la venta.')
            return redirect('ventas:lista_mesas_activas')
        
        try:
            with transaction.atomic():
                # Obtener usuario del sistema
                usuario_sistema = obtener_usuario_desde_django_user(request.user)
                if not usuario_sistema:
                    raise ValueError('Error: No se encontró el usuario en el sistema. Contacte al administrador.')
                
                # Obtener los platos
                platos = PlatoProducido.objects.filter(
                    id_plato_producido__in=platos_ids,
                    estado='en_mesa'
                )
                
                if not platos.exists():
                    messages.error(request, 'No se encontraron platos válidos para cerrar la venta.')
                    return redirect('ventas:lista_mesas_activas')
                
                # Cambiar estado a 'venta' y actualizar fecha_entrega
                from django.utils import timezone
                platos_actualizados = 0
                for plato in platos:
                    plato.estado = 'venta'
                    plato.fecha_entrega = timezone.now()
                    plato.save()
                    platos_actualizados += 1
                
                # Obtener información de la mesa
                ubicacion = None
                if ubicacion_id:
                    try:
                        ubicacion = Ubicacion.objects.get(id_ubicacion=ubicacion_id)
                    except:
                        pass
                
                mensaje = f'Venta cerrada exitosamente. {platos_actualizados} plato(s) marcado(s) como vendido(s).'
                if ubicacion and numero_mesa:
                    mensaje += f' Mesa: {ubicacion.nombre_ubicacion} - {numero_mesa}'
                elif ubicacion:
                    mensaje += f' Ubicación: {ubicacion.nombre_ubicacion}'
                
                messages.success(request, mensaje)
                return redirect('ventas:lista_mesas_activas')
                
        except ValueError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f'Error al cerrar la venta: {str(e)}')
    
    return redirect('ventas:lista_mesas_activas')


@login_required
@menu_required('ventas', 'historial_mesas')
def historial_movimientos_mesa(request):
    """Historial de movimientos de platos de cocina a mesa"""
    movimientos = MovimientoMesa.objects.select_related(
        'id_plato_producido__id_plato',
        'id_ubicacion',
        'id_usuario'
    ).all()
    
    # Filtros
    busqueda = request.GET.get('busqueda', '')
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    ubicacion_id = request.GET.get('ubicacion', '')
    plato_id = request.GET.get('plato', '')
    usuario_id = request.GET.get('usuario', '')
    
    if busqueda:
        movimientos = movimientos.filter(
            Q(id_plato_producido__id_plato__nombre_plato__icontains=busqueda) |
            Q(id_ubicacion__nombre_ubicacion__icontains=busqueda) |
            Q(numero_mesa__icontains=busqueda) |
            Q(observaciones__icontains=busqueda)
        )
    
    if ubicacion_id:
        movimientos = movimientos.filter(id_ubicacion_id=ubicacion_id)
    
    if plato_id:
        movimientos = movimientos.filter(id_plato_producido__id_plato_id=plato_id)
    
    if usuario_id:
        movimientos = movimientos.filter(id_usuario_id=usuario_id)
    
    if fecha_desde:
        try:
            from datetime import datetime
            fecha_desde_obj = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
            movimientos = movimientos.filter(fecha_movimiento__date__gte=fecha_desde_obj)
        except ValueError:
            pass
    
    if fecha_hasta:
        try:
            from datetime import datetime
            fecha_hasta_obj = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
            movimientos = movimientos.filter(fecha_movimiento__date__lte=fecha_hasta_obj)
        except ValueError:
            pass
    
    # Ordenar por fecha más reciente
    movimientos = movimientos.order_by('-fecha_movimiento')
    
    # Paginación
    paginator = Paginator(movimientos, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Datos para filtros
    ubicaciones_mesa = Ubicacion.objects.filter(
        tipo_ubicacion__iexact='mesa'
    ).order_by('nombre_ubicacion')
    
    if not ubicaciones_mesa.exists():
        ubicaciones_mesa = Ubicacion.objects.filter(
            tipo_ubicacion__icontains='mesa'
        ).order_by('nombre_ubicacion')
    
    platos = Plato.objects.filter(
        id_plato__in=PlatoProducido.objects.values_list('id_plato', flat=True).distinct()
    ).order_by('nombre_plato')
    usuarios = Usuario.objects.filter(
        id_usuario__in=MovimientoMesa.objects.values_list('id_usuario', flat=True).distinct()
    ).order_by('nombre')
    
    context = {
        'title': 'Historial de Movimientos a Mesa',
        'page_obj': page_obj,
        'busqueda': busqueda,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'ubicacion_id': ubicacion_id,
        'plato_id': plato_id,
        'usuario_id': usuario_id,
        'ubicaciones_mesa': ubicaciones_mesa,
        'platos': platos,
        'usuarios': usuarios,
    }
    return render(request, 'ventas/movimientos/historial.html', context)


@login_required
@menu_required('ventas', 'historial_ventas')
def historial_ventas_platos(request):
    """Historial de ventas de platos producidos (estado 'venta')"""
    platos_vendidos = PlatoProducido.objects.filter(
        estado='venta'
    ).select_related('id_plato', 'id_ubicacion', 'id_usuario').order_by('-fecha_entrega')
    
    # Filtros
    busqueda = request.GET.get('busqueda', '')
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    plato_id = request.GET.get('plato', '')
    ubicacion_id = request.GET.get('ubicacion', '')
    
    if busqueda:
        platos_vendidos = platos_vendidos.filter(
            Q(id_plato__nombre_plato__icontains=busqueda) |
            Q(id_ubicacion__nombre_ubicacion__icontains=busqueda)
        )
    
    if plato_id:
        platos_vendidos = platos_vendidos.filter(id_plato_id=plato_id)
    
    if ubicacion_id:
        platos_vendidos = platos_vendidos.filter(id_ubicacion_id=ubicacion_id)
    
    if fecha_desde:
        try:
            from datetime import datetime
            fecha_desde_obj = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
            platos_vendidos = platos_vendidos.filter(fecha_entrega__date__gte=fecha_desde_obj)
        except ValueError:
            pass
    
    if fecha_hasta:
        try:
            from datetime import datetime
            fecha_hasta_obj = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
            platos_vendidos = platos_vendidos.filter(fecha_entrega__date__lte=fecha_hasta_obj)
        except ValueError:
            pass
    
    # Paginación
    paginator = Paginator(platos_vendidos, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Datos para filtros
    platos = Plato.objects.filter(
        id_plato__in=PlatoProducido.objects.values_list('id_plato', flat=True).distinct()
    ).order_by('nombre_plato')
    
    ubicaciones_mesa = Ubicacion.objects.filter(
        tipo_ubicacion__iexact='mesa'
    ).order_by('nombre_ubicacion')
    
    if not ubicaciones_mesa.exists():
        ubicaciones_mesa = Ubicacion.objects.filter(
            tipo_ubicacion__icontains='mesa'
        ).order_by('nombre_ubicacion')
    
    context = {
        'title': 'Historial de Ventas de Platos',
        'page_obj': page_obj,
        'busqueda': busqueda,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'plato_id': plato_id,
        'ubicacion_id': ubicacion_id,
        'platos': platos,
        'ubicaciones_mesa': ubicaciones_mesa,
    }
    return render(request, 'ventas/ventas_platos/historial.html', context)


# ========== GESTIÓN DE COMANDAS ==========

@login_required
@menu_required('ventas', 'comandas')
def crear_comanda(request):
    """Crear una nueva comanda"""
    if request.method == 'POST':
        form = ComandaForm(request.POST)
        
        # Para inlineformset, NO podemos crear una instancia temporal sin id_mesa
        # porque Comanda requiere id_mesa (ForeignKey no nullable)
        # Validaremos el formset después de crear la comanda
        # Por ahora, solo validamos el formulario principal
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Obtener usuario del sistema
                    usuario_sistema = obtener_usuario_desde_django_user(request.user)
                    if not usuario_sistema:
                        raise ValueError('Error: No se encontró el usuario en el sistema. Contacte al administrador.')
                    
                    # Obtener la ubicación seleccionada
                    id_ubicacion = form.cleaned_data.get('id_ubicacion')
                    numero_mesa = form.cleaned_data.get('numero_mesa', '').strip()
                    
                    # Validar que ambos campos estén presentes
                    if not id_ubicacion:
                        raise ValueError('Debe seleccionar una ubicación (mesa).')
                    if not numero_mesa:
                        raise ValueError('Debe ingresar un número de mesa.')
                    
                    # Obtener o crear la mesa
                    # Usar el nombre de la ubicación como parte del identificador único si es necesario
                    mesa = None
                    try:
                        mesa, created = Mesa.objects.get_or_create(
                            numero_mesa=numero_mesa,
                            defaults={
                                'estado': 'ocupada',
                                'activa': True,
                                'ubicacion': id_ubicacion.nombre_ubicacion
                            }
                        )
                        
                        # Si la mesa ya existía, actualizar la ubicación si es necesario
                        if not created:
                            if mesa.ubicacion != id_ubicacion.nombre_ubicacion:
                                mesa.ubicacion = id_ubicacion.nombre_ubicacion
                            # Si estaba disponible, marcarla como ocupada
                            if mesa.estado == 'disponible':
                                mesa.estado = 'ocupada'
                            mesa.save()
                        
                        # Refrescar la mesa desde la base de datos para asegurar que tiene el id
                        mesa.refresh_from_db()
                    except Exception as e:
                        import traceback
                        traceback.print_exc()
                        raise ValueError(f'Error al crear o obtener la mesa: {str(e)}')
                    
                    # Verificar que la mesa se creó correctamente
                    if not mesa:
                        raise ValueError('Error: No se pudo crear o obtener la mesa correctamente.')
                    
                    # Asegurarse de que la mesa tiene un id_mesa válido
                    if not hasattr(mesa, 'id_mesa') or mesa.id_mesa is None:
                        # Si la mesa no tiene id, guardarla explícitamente
                        mesa.save()
                        mesa.refresh_from_db()
                        if not mesa.id_mesa:
                            raise ValueError('Error: La mesa no tiene un ID válido después de guardarla.')
                    
                    # Debug: verificar la mesa antes de crear la comanda
                    print(f"[DEBUG] Mesa creada/obtenida: id={mesa.id_mesa}, numero={mesa.numero_mesa}, ubicacion={mesa.ubicacion}")
                    
                    # Crear comanda
                    try:
                        # Verificar que mesa tiene id_mesa antes de crear la comanda
                        if not mesa.id_mesa:
                            raise ValueError(f'Mesa no tiene id_mesa válido. Mesa: {mesa}')
                        
                        comanda = Comanda(
                            id_mesa=mesa,
                            id_usuario=usuario_sistema,
                            estado='pendiente',
                            observaciones=form.cleaned_data.get('observaciones', '')
                        )
                        # Guardar primero la comanda para que tenga un ID
                        comanda.save()
                        print(f"[DEBUG] Comanda creada: id={comanda.id_comanda}, id_mesa={comanda.id_mesa_id}, mesa_id={mesa.id_mesa}")
                    except Exception as e:
                        print(f"[DEBUG] Error al crear comanda: {str(e)}")
                        print(f"[DEBUG] Tipo de mesa: {type(mesa)}, id_mesa: {getattr(mesa, 'id_mesa', 'NO EXISTE')}")
                        import traceback
                        traceback.print_exc()
                        raise ValueError(f'Error al crear la comanda: {str(e)}')
                    
                    # Verificar que la comanda se creó correctamente
                    if not comanda or not comanda.id_comanda:
                        raise ValueError('Error: La comanda no se creó correctamente.')
                    
                    # Refrescar la comanda desde la base de datos
                    comanda.refresh_from_db()
                    print(f"[DEBUG] Comanda refrescada: id={comanda.id_comanda}, id_mesa={comanda.id_mesa_id}")
                    
                    # Debug: verificar qué datos están llegando en el POST
                    print(f"[DEBUG] POST data keys relacionados con formset:")
                    formset_keys = [k for k in request.POST.keys() if 'detallecomanda_set' in k]
                    for key in sorted(formset_keys):
                        print(f"  {key} = {request.POST.get(key)}")
                    
                    # Recrear el formset con la instancia real de la comanda
                    # Esto es necesario porque el formset necesita la instancia para validar y guardar
                    formset = DetalleComandaInlineFormSet(request.POST, instance=comanda)
                    
                    # Validar el formset ahora que tiene la instancia
                    if not formset.is_valid():
                        # Si hay errores en el formset, eliminamos la comanda creada
                        comanda.delete()
                        if formset.non_form_errors():
                            for error in formset.non_form_errors():
                                messages.error(request, f'Error en formulario: {error}')
                        for i, form_error in enumerate(formset.errors):
                            if form_error:
                                for field, errors in form_error.items():
                                    for error in errors:
                                        messages.error(request, f'Error en plato {i+1}, campo {field}: {error}')
                        raise ValueError('Error en los detalles de la comanda.')
                    
                    # Debug: verificar cuántos formularios hay en el formset
                    print(f"[DEBUG] Total forms en formset: {formset.total_form_count()}")
                    print(f"[DEBUG] Total forms (management): {formset.management_form.cleaned_data.get('TOTAL_FORMS', 'N/A')}")
                    print(f"[DEBUG] Forms count: {len(formset.forms)}")
                    
                    # Debug: verificar cada formulario
                    forms_con_datos = []
                    for i, form in enumerate(formset.forms):
                        if hasattr(form, 'cleaned_data'):
                            id_plato = form.cleaned_data.get('id_plato')
                            cantidad = form.cleaned_data.get('cantidad')
                            delete = form.cleaned_data.get('DELETE', False)
                            print(f"[DEBUG] Form {i}: plato={id_plato}, cantidad={cantidad}, DELETE={delete}, is_valid={form.is_valid()}")
                            if id_plato and cantidad and not delete:
                                forms_con_datos.append((i, form))
                        else:
                            print(f"[DEBUG] Form {i}: NO tiene cleaned_data, errors={form.errors if hasattr(form, 'errors') else 'N/A'}")
                    
                    print(f"[DEBUG] Forms con datos válidos: {len(forms_con_datos)}")
                    
                    # Guardar los detalles
                    detalles_guardados = formset.save()
                    
                    print(f"[DEBUG] Detalles guardados por formset.save(): {len(detalles_guardados)}")
                    
                    # Debug: verificar qué se guardó
                    print(f"[DEBUG] Detalles guardados: {len(detalles_guardados)}")
                    for detalle in detalles_guardados:
                        print(f"[DEBUG] - {detalle.id_plato.nombre_plato} x{detalle.cantidad}")
                    
                    # Verificar cuántos detalles se guardaron
                    if len(detalles_guardados) == 0:
                        messages.warning(request, 'No se guardaron detalles. Verifica que hayas completado al menos un plato.')
                    elif len(detalles_guardados) == 1:
                        messages.success(request, f'Comanda #{comanda.id_comanda} creada exitosamente para Mesa {mesa.numero_mesa} con {len(detalles_guardados)} plato.')
                    else:
                        messages.success(request, f'Comanda #{comanda.id_comanda} creada exitosamente para Mesa {mesa.numero_mesa} con {len(detalles_guardados)} platos.')
                return redirect('ventas:lista_comandas')
            except ValueError as e:
                messages.error(request, str(e))
            except Exception as e:
                messages.error(request, f'Error al crear la comanda: {str(e)}')
                import traceback
                traceback.print_exc()
        else:
            # Si hay errores, mostrarlos
            if not form.is_valid():
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f'Error en {field}: {error}')
            if not formset.is_valid():
                if formset.non_form_errors():
                    for error in formset.non_form_errors():
                        messages.error(request, f'Error en formulario: {error}')
                for i, form_error in enumerate(formset.errors):
                    if form_error:
                        for field, errors in form_error.items():
                            for error in errors:
                                messages.error(request, f'Error en plato {i+1}, campo {field}: {error}')
    else:
        form = ComandaForm()
        # Crear formset con instancia temporal (para formulario nuevo)
        comanda_temporal = Comanda()
        formset = DetalleComandaInlineFormSet(instance=comanda_temporal)
    
    context = {
        'title': 'Crear Comanda',
        'form': form,
        'formset': formset,
    }
    return render(request, 'ventas/comandas/crear.html', context)


@login_required
@menu_required('ventas', 'comandas')
def lista_comandas(request):
    """Lista todas las comandas"""
    comandas = Comanda.objects.select_related(
        'id_mesa', 'id_usuario'
    ).prefetch_related('detalles__id_plato').all().order_by('-fecha_creacion')
    
    # Filtros
    estado_filtro = request.GET.get('estado', '')
    mesa_id = request.GET.get('mesa', '')
    busqueda = request.GET.get('busqueda', '')
    
    if estado_filtro:
        comandas = comandas.filter(estado=estado_filtro)
    
    if mesa_id:
        comandas = comandas.filter(id_mesa_id=mesa_id)
    
    if busqueda:
        comandas = comandas.filter(
            Q(id_mesa__numero_mesa__icontains=busqueda) |
            Q(id_usuario__nombre__icontains=busqueda) |
            Q(observaciones__icontains=busqueda)
        )
    
    # Paginación
    paginator = Paginator(comandas, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Datos para filtros
    mesas = Mesa.objects.filter(activa=True).order_by('numero_mesa')
    
    context = {
        'title': 'Comandas',
        'page_obj': page_obj,
        'estado_filtro': estado_filtro,
        'mesa_id': mesa_id,
        'busqueda': busqueda,
        'estados': Comanda.ESTADO_CHOICES,
        'mesas': mesas,
    }
    return render(request, 'ventas/comandas/lista.html', context)


@login_required
@menu_required('ventas', 'comandas')
def detalle_comanda(request, comanda_id):
    """Ver detalle de una comanda"""
    comanda = get_object_or_404(
        Comanda.objects.select_related('id_mesa', 'id_usuario'),
        id_comanda=comanda_id
    )
    
    detalles = DetalleComanda.objects.filter(
        id_comanda=comanda
    ).select_related('id_plato', 'id_plato_producido').order_by('id_plato__nombre_plato')
    
    context = {
        'title': f'Comanda #{comanda.id_comanda}',
        'comanda': comanda,
        'detalles': detalles,
    }
    return render(request, 'ventas/comandas/detalle.html', context)


@login_required
@menu_required('ventas', 'comandas')
def entregar_platos_comanda(request, comanda_id):
    """Entregar platos listos de una comanda a la mesa"""
    comanda = get_object_or_404(Comanda, id_comanda=comanda_id)
    
    if request.method == 'POST':
        detalles_ids = request.POST.getlist('detalles_ids')
        
        if not detalles_ids:
            messages.error(request, 'Debe seleccionar al menos un plato para entregar.')
            return redirect('ventas:detalle_comanda', comanda_id=comanda_id)
        
        try:
            with transaction.atomic():
                # Obtener usuario del sistema
                usuario_sistema = obtener_usuario_desde_django_user(request.user)
                if not usuario_sistema:
                    raise ValueError('Error: No se encontró el usuario en el sistema.')
                
                # Obtener detalles que están listos
                detalles = DetalleComanda.objects.filter(
                    id_detalle_comanda__in=detalles_ids,
                    id_comanda=comanda,
                    estado='listo'
                ).select_related('id_plato_producido')
                
                platos_entregados = 0
                for detalle in detalles:
                    if detalle.id_plato_producido:
                        # Cambiar estado del detalle a entregado
                        detalle.estado = 'entregado'
                        detalle.save()
                        
                        # Cambiar estado del plato producido a en_mesa
                        plato_producido = detalle.id_plato_producido
                        plato_producido.estado = 'en_mesa'
                        plato_producido.save()
                        
                        platos_entregados += 1
                
                # Actualizar estado de la comanda
                comanda.actualizar_estado()
                
                messages.success(
                    request,
                    f'{platos_entregados} plato(s) entregado(s) exitosamente a la mesa.'
                )
                return redirect('ventas:detalle_comanda', comanda_id=comanda_id)
                
        except ValueError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f'Error al entregar los platos: {str(e)}')
    
    return redirect('ventas:detalle_comanda', comanda_id=comanda_id)
