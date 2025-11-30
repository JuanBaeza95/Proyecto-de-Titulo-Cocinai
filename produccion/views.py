from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.db import transaction, connection
from django.utils import timezone
from datetime import date
from inventario.models import Receta, Plato, Insumo, PlatoProducido, DetalleProduccionInsumo, Lote, Ubicacion, MovimientoStock, Usuario, PrediccionDemanda
from .forms import RecetaForm, RecetaInlineFormSet, PlatoForm, PlatoProducidoForm, IngredienteProduccionFormSet
from ventas.models import Comanda, DetalleComanda
from usuarios.permissions import menu_required


# ========== HELPER FUNCTIONS ==========

def obtener_ubicacion_cocina():
    """Obtiene la ubicación de tipo 'cocina'"""
    ubicacion_cocina = Ubicacion.objects.filter(
        tipo_ubicacion__iexact='cocina'
    ).first()
    
    if not ubicacion_cocina:
        ubicacion_cocina = Ubicacion.objects.filter(
            tipo_ubicacion__icontains='cocina'
        ).first()
    
    if not ubicacion_cocina:
        ubicacion_cocina = Ubicacion.objects.filter(
            nombre_ubicacion__icontains='cocina'
        ).first()
    
    if not ubicacion_cocina:
        raise ValueError(
            'No se encontró una ubicación de tipo "cocina". '
            'Por favor, crea una ubicación de cocina primero.'
        )
    
    return ubicacion_cocina


def obtener_ubicacion_mesa():
    """Obtiene la ubicación de tipo 'mesa'"""
    ubicacion_mesa = Ubicacion.objects.filter(
        tipo_ubicacion__iexact='mesa'
    ).first()
    
    if not ubicacion_mesa:
        ubicacion_mesa = Ubicacion.objects.filter(
            tipo_ubicacion__icontains='mesa'
        ).first()
    
    if not ubicacion_mesa:
        ubicacion_mesa = Ubicacion.objects.filter(
            nombre_ubicacion__icontains='mesa'
        ).first()
    
    if not ubicacion_mesa:
        ubicacion_mesa = Ubicacion.objects.filter(
            Q(nombre_ubicacion__icontains='interior') | Q(nombre_ubicacion__icontains='sala')
        ).first()
    
    if not ubicacion_mesa:
        raise ValueError(
            'No se encontró una ubicación de tipo "mesa". '
            'Por favor, crea una ubicación de mesa primero.'
        )
    
    return ubicacion_mesa


def descontar_lotes_para_produccion(plato, usuario_django, ingredientes_personalizados=None):
    """
    Descuenta los lotes según la receta del plato o ingredientes personalizados, usando FEFO (First Expired, First Out)
    Solo descuenta de lotes en ubicación "cocina" y que no estén vencidos
    
    Args:
        plato: Plato a producir
        usuario_django: Usuario de Django
        ingredientes_personalizados: Lista de dicts con {'id_insumo': Insumo, 'cantidad_necesaria': Decimal} o None para usar receta
    
    Retorna: (detalles_produccion, movimientos_stock)
    """
    # Si se proporcionan ingredientes personalizados, usarlos; si no, usar la receta
    if ingredientes_personalizados:
        recetas_data = ingredientes_personalizados
    else:
        # Obtener la receta del plato
        recetas = Receta.objects.filter(id_plato=plato).select_related('id_insumo')
        if not recetas.exists():
            raise ValueError(f'El plato "{plato.nombre_plato}" no tiene receta definida.')
        recetas_data = [{'id_insumo': r.id_insumo, 'cantidad_necesaria': r.cantidad_necesaria} for r in recetas]
    
    # Obtener ubicación cocina
    ubicacion_cocina = obtener_ubicacion_cocina()
    
    # Obtener usuario del modelo Usuario (usando helper de ventas si existe)
    try:
        from ventas.views import obtener_usuario_desde_django_user
        usuario = obtener_usuario_desde_django_user(usuario_django)
        if not usuario:
            raise ValueError(f'No se pudo obtener o crear el usuario para "{usuario_django.username}".')
    except ImportError:
        # Si no existe el helper, intentar obtener directamente
        try:
            usuario = Usuario.objects.get(email=usuario_django.email)
        except Usuario.DoesNotExist:
            raise ValueError(f'Usuario Django "{usuario_django.username}" no tiene un registro correspondiente en la tabla USUARIO.')
    
    detalles_produccion = []
    movimientos_stock = []
    
    # Para cada ingrediente en la receta o ingredientes personalizados
    for receta_data in recetas_data:
        insumo = receta_data['id_insumo']
        cantidad_necesaria = receta_data['cantidad_necesaria']
        cantidad_restante = cantidad_necesaria
        
        # Obtener lotes del insumo en cocina, ordenados por FEFO (fecha vencimiento más próxima primero)
        # Excluir lotes vencidos
        lotes_disponibles = Lote.objects.filter(
            id_insumo=insumo,
            id_ubicacion=ubicacion_cocina,
            cantidad_actual__gt=0,
            fecha_vencimiento__gte=date.today()  # Solo lotes no vencidos
        ).order_by('fecha_vencimiento', 'fecha_ingreso')
        
        if not lotes_disponibles.exists():
            raise ValueError(
                f'No hay stock disponible del insumo "{insumo.nombre_insumo}" en cocina. '
                f'Cantidad necesaria: {cantidad_necesaria} {insumo.unidad_medida}'
            )
        
        # Calcular stock total disponible
        stock_total = sum(lote.cantidad_actual for lote in lotes_disponibles)
        if stock_total < cantidad_necesaria:
            raise ValueError(
                f'Stock insuficiente del insumo "{insumo.nombre_insumo}" en cocina. '
                f'Disponible: {stock_total} {insumo.unidad_medida}, '
                f'Necesario: {cantidad_necesaria} {insumo.unidad_medida}'
            )
        
        # Descontar de los lotes usando FEFO
        for lote in lotes_disponibles:
            if cantidad_restante <= 0:
                break
            
            cantidad_a_descontar = min(cantidad_restante, lote.cantidad_actual)
            
            # Actualizar cantidad del lote
            lote.cantidad_actual -= cantidad_a_descontar
            lote.save()
            
            # Guardar detalle para crear después
            detalles_produccion.append({
                'lote': lote,
                'insumo': insumo,
                'cantidad': cantidad_a_descontar
            })
            
            # Crear movimiento de stock
            movimiento = MovimientoStock.objects.create(
                id_lote=lote,
                id_usuario=usuario,
                fecha_movimiento=timezone.now().date(),
                tipo_movimiento='salida',
                origen_movimiento='produccion',
                cantidad=cantidad_a_descontar
            )
            movimientos_stock.append(movimiento)
            
            cantidad_restante -= cantidad_a_descontar
    
    return detalles_produccion, movimientos_stock


# ========== INDEX ==========

@login_required
@menu_required('produccion', 'recetas')
def index(request):
    """Página principal del módulo de producción"""
    # Obtener platos con recetas y contar ingredientes
    platos = Plato.objects.annotate(
        num_ingredientes=Count('receta')
    ).order_by('nombre_plato')
    
    platos_con_recetas = platos.filter(num_ingredientes__gt=0)
    
    context = {
        'title': 'Producción - CocinAI',
        'platos_con_recetas': platos_con_recetas,
    }
    return render(request, 'produccion/index.html', context)


# ========== GESTIÓN DE RECETAS ==========

@login_required
@menu_required('produccion', 'recetas')
def lista_recetas(request):
    """Lista todas las recetas"""
    platos = Plato.objects.annotate(
        num_ingredientes=Count('receta')
    ).order_by('nombre_plato')
    
    # Filtros
    busqueda = request.GET.get('busqueda', '')
    if busqueda:
        platos = platos.filter(nombre_plato__icontains=busqueda)
    
    # Paginación
    paginator = Paginator(platos, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'title': 'Recetario',
        'page_obj': page_obj,
        'busqueda': busqueda,
    }
    return render(request, 'produccion/recetas/lista.html', context)


@login_required
@menu_required('produccion', 'recetas')
def crear_receta(request):
    """Crear una nueva receta"""
    plato_id = request.GET.get('plato_id')
    plato = None
    
    if plato_id:
        try:
            plato = Plato.objects.get(id_plato=plato_id)
        except Plato.DoesNotExist:
            pass
    
    if request.method == 'POST':
        # Si hay un plato, usar el formset con instancia
        if plato:
            formset = RecetaInlineFormSet(request.POST, instance=plato)
        else:
            # Si no hay plato, necesitamos crear uno primero
            # Esto no debería pasar normalmente, pero manejamos el caso
            formset = RecetaInlineFormSet(request.POST)
        
        if formset.is_valid():
            try:
                with transaction.atomic():
                    # Si no hay plato, necesitamos obtenerlo del POST o crear uno
                    if not plato:
                        # Intentar obtener plato_id del POST
                        plato_id_post = request.POST.get('plato_id')
                        if plato_id_post:
                            try:
                                plato = Plato.objects.get(id_plato=plato_id_post)
                                formset.instance = plato
                            except Plato.DoesNotExist:
                                messages.error(request, 'Plato no encontrado.')
                                formset = RecetaInlineFormSet()
                                context = {
                                    'title': 'Crear Receta',
                                    'formset': formset,
                                    'plato': None,
                                }
                                return render(request, 'produccion/recetas/crear.html', context)
                        else:
                            messages.error(request, 'Debe especificar un plato para crear la receta.')
                            formset = RecetaInlineFormSet()
                            context = {
                                'title': 'Crear Receta',
                                'formset': formset,
                                'plato': None,
                            }
                            return render(request, 'produccion/recetas/crear.html', context)
                    
                    # Guardar el formset
                    formset.save()
                
                messages.success(request, f'Receta para "{plato.nombre_plato}" creada exitosamente.')
                return redirect('produccion:detalle_receta', plato_id=plato.id_plato)
            except Exception as e:
                messages.error(request, f'Error al crear la receta: {str(e)}')
    else:
        # GET request: crear formset con instancia del plato si existe
        if plato:
            formset = RecetaInlineFormSet(instance=plato)
        else:
            formset = RecetaInlineFormSet()
    
    # Obtener lista de platos para el selector (si no hay plato seleccionado)
    platos = None
    if not plato:
        platos = Plato.objects.all().order_by('nombre_plato')
    
    context = {
        'title': 'Crear Receta',
        'formset': formset,
        'plato': plato,
        'platos': platos,
    }
    return render(request, 'produccion/recetas/crear.html', context)


@login_required
@menu_required('produccion', 'recetas')
def editar_receta(request, plato_id):
    """Editar una receta existente"""
    plato = get_object_or_404(Plato, id_plato=plato_id)
    
    if request.method == 'POST':
        formset = RecetaInlineFormSet(request.POST, instance=plato)
        
        if formset.is_valid():
            try:
                formset.save()
                messages.success(request, f'Receta de "{plato.nombre_plato}" actualizada exitosamente.')
                return redirect('produccion:detalle_receta', plato_id=plato_id)
            except Exception as e:
                messages.error(request, f'Error al actualizar la receta: {str(e)}')
    else:
        formset = RecetaInlineFormSet(instance=plato)
    
    context = {
        'title': f'Editar Receta: {plato.nombre_plato}',
        'plato': plato,
        'formset': formset,
    }
    return render(request, 'produccion/recetas/editar.html', context)


@login_required
@menu_required('produccion', 'recetas')
def detalle_receta(request, plato_id):
    """Ver detalle de una receta"""
    plato = get_object_or_404(Plato, id_plato=plato_id)
    recetas = Receta.objects.filter(id_plato=plato).select_related('id_insumo').order_by('id_insumo__nombre_insumo')
    
    context = {
        'title': f'Receta: {plato.nombre_plato}',
        'plato': plato,
        'recetas': recetas,
    }
    return render(request, 'produccion/recetas/detalle.html', context)


@login_required
@menu_required('produccion', 'recetas')
def eliminar_receta(request, plato_id):
    """Eliminar una receta"""
    plato = get_object_or_404(Plato, id_plato=plato_id)
    
    if request.method == 'POST':
        try:
            nombre_plato = plato.nombre_plato
            Receta.objects.filter(id_plato=plato).delete()
            messages.success(request, f'Receta de "{nombre_plato}" eliminada exitosamente.')
            return redirect('produccion:lista_recetas')
        except Exception as e:
            messages.error(request, f'Error al eliminar la receta: {str(e)}')
    
    recetas = Receta.objects.filter(id_plato=plato).select_related('id_insumo')
    
    context = {
        'title': f'Eliminar Receta: {plato.nombre_plato}',
        'plato': plato,
        'recetas': recetas,
    }
    return render(request, 'produccion/recetas/eliminar.html', context)


# ========== GESTIÓN DE PLATOS ==========

@login_required
@menu_required('produccion', 'recetas')
def lista_platos(request):
    """Lista todos los platos"""
    platos = Plato.objects.annotate(
        num_ingredientes=Count('receta')
    ).order_by('nombre_plato')
    
    # Filtros
    busqueda = request.GET.get('busqueda', '')
    if busqueda:
        platos = platos.filter(nombre_plato__icontains=busqueda)
    
    # Paginación
    paginator = Paginator(platos, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'title': 'Platos',
        'page_obj': page_obj,
        'busqueda': busqueda,
    }
    return render(request, 'produccion/platos/lista.html', context)


@login_required
@menu_required('produccion', 'recetas')
def crear_plato(request):
    """Crear un nuevo plato"""
    if request.method == 'POST':
        form = PlatoForm(request.POST)
        if form.is_valid():
            try:
                plato = form.save()
                messages.success(request, f'Plato "{plato.nombre_plato}" creado exitosamente.')
                return redirect('produccion:lista_platos')
            except Exception as e:
                messages.error(request, f'Error al crear el plato: {str(e)}')
    else:
        form = PlatoForm()
    
    context = {
        'title': 'Crear Plato',
        'form': form,
    }
    return render(request, 'produccion/platos/crear.html', context)


@login_required
@menu_required('produccion', 'recetas')
def editar_plato(request, plato_id):
    """Editar un plato existente"""
    plato = get_object_or_404(Plato, id_plato=plato_id)
    
    if request.method == 'POST':
        form = PlatoForm(request.POST, instance=plato)
        if form.is_valid():
            try:
                plato = form.save()
                messages.success(request, f'Plato "{plato.nombre_plato}" actualizado exitosamente.')
                return redirect('produccion:lista_platos')
            except Exception as e:
                messages.error(request, f'Error al actualizar el plato: {str(e)}')
    else:
        form = PlatoForm(instance=plato)
    
    context = {
        'title': f'Editar Plato: {plato.nombre_plato}',
        'form': form,
        'plato': plato,
    }
    return render(request, 'produccion/platos/editar.html', context)


@login_required
@menu_required('produccion', 'recetas')
def eliminar_plato(request, plato_id):
    """Eliminar un plato"""
    plato = get_object_or_404(Plato, id_plato=plato_id)
    
    if request.method == 'POST':
        try:
            nombre_plato = plato.nombre_plato
            
            # Verificar si la tabla PREDICCION_DEMANDA existe antes de intentar eliminar
            # Esto evita el error cuando la tabla no existe en la base de datos
            tabla_prediccion_existe = False
            try:
                with connection.cursor() as cursor:
                    cursor.execute("""
                        SELECT COUNT(*) 
                        FROM information_schema.tables 
                        WHERE table_schema = DATABASE() 
                        AND table_name = 'PREDICCION_DEMANDA'
                    """)
                    tabla_prediccion_existe = cursor.fetchone()[0] > 0
                    
                    # Si la tabla existe, eliminar las predicciones relacionadas
                    if tabla_prediccion_existe:
                        cursor.execute("""
                            DELETE FROM PREDICCION_DEMANDA 
                            WHERE id_plato = %s
                        """, [plato_id])
            except Exception:
                # Si hay error al verificar, asumimos que la tabla no existe
                tabla_prediccion_existe = False
            
            # Intentar eliminar el plato usando el ORM de Django
            try:
                plato.delete()
            except Exception as delete_error:
                # Si el error es porque la tabla PREDICCION_DEMANDA no existe,
                # eliminar el plato directamente con SQL
                error_str = str(delete_error).lower()
                if "prediccion_demanda" in error_str and ("doesn't exist" in error_str or "table" in error_str):
                    # Eliminar manualmente las relaciones que puedan existir (solo CASCADE)
                    try:
                        with connection.cursor() as cursor:
                            # Verificar si hay platos producidos (RESTRICT - no se pueden eliminar)
                            cursor.execute("SELECT COUNT(*) FROM PLATO_PRODUCIDO WHERE id_plato = %s", [plato_id])
                            if cursor.fetchone()[0] > 0:
                                raise Exception("No se puede eliminar el plato porque tiene platos producidos asociados. Elimine primero los platos producidos.")
                            
                            # Eliminar recetas relacionadas (CASCADE)
                            cursor.execute("DELETE FROM RECETA WHERE id_plato = %s", [plato_id])
                            # Eliminar registros de venta relacionados (CASCADE)
                            cursor.execute("DELETE FROM REGISTRO_VENTA_PLATO WHERE id_plato = %s", [plato_id])
                            # Eliminar el plato
                            cursor.execute("DELETE FROM PLATO WHERE id_plato = %s", [plato_id])
                    except Exception as sql_error:
                        # Si hay error al eliminar con SQL, relanzarlo
                        raise sql_error
                else:
                    # Si es otro tipo de error, relanzarlo
                    raise delete_error
            
            messages.success(request, f'Plato "{nombre_plato}" eliminado exitosamente.')
            return redirect('produccion:lista_platos')
        except Exception as e:
            messages.error(request, f'Error al eliminar el plato: {str(e)}')
    
    context = {
        'title': f'Eliminar Plato: {plato.nombre_plato}',
        'plato': plato,
    }
    return render(request, 'produccion/platos/eliminar.html', context)


# ========== GESTIÓN DE PLATOS PRODUCIDOS ==========

@login_required
@menu_required('produccion', 'recetas')
def lista_platos_producidos(request):
    """Lista todos los platos producidos con filtros"""
    platos_producidos = PlatoProducido.objects.select_related(
        'id_plato', 'id_ubicacion', 'id_usuario'
    ).all().order_by('-fecha_produccion')
    
    # Filtros
    estado_filtro = request.GET.get('estado', '')
    busqueda = request.GET.get('busqueda', '')
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    usuario_id = request.GET.get('usuario', '')
    ubicacion_id = request.GET.get('ubicacion', '')
    
    if estado_filtro:
        platos_producidos = platos_producidos.filter(estado=estado_filtro)
    
    if busqueda:
        platos_producidos = platos_producidos.filter(
            Q(id_plato__nombre_plato__icontains=busqueda)
        )
    
    if fecha_desde:
        try:
            from datetime import datetime
            fecha_desde_obj = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
            platos_producidos = platos_producidos.filter(fecha_produccion__date__gte=fecha_desde_obj)
        except ValueError:
            pass
    
    if fecha_hasta:
        try:
            from datetime import datetime
            fecha_hasta_obj = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
            platos_producidos = platos_producidos.filter(fecha_produccion__date__lte=fecha_hasta_obj)
        except ValueError:
            pass
    
    if usuario_id:
        platos_producidos = platos_producidos.filter(id_usuario_id=usuario_id)
    
    if ubicacion_id:
        platos_producidos = platos_producidos.filter(id_ubicacion_id=ubicacion_id)
    
    # Paginación
    paginator = Paginator(platos_producidos, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Datos para filtros
    from django.contrib.auth.models import User
    usuarios_ids = PlatoProducido.objects.values_list('id_usuario', flat=True).distinct()
    usuarios = User.objects.filter(id__in=usuarios_ids).order_by('username')
    
    ubicaciones = Ubicacion.objects.filter(
        id_ubicacion__in=PlatoProducido.objects.values_list('id_ubicacion', flat=True).distinct()
    ).order_by('nombre_ubicacion')
    
    context = {
        'title': 'Platos Producidos',
        'page_obj': page_obj,
        'estado_filtro': estado_filtro,
        'busqueda': busqueda,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'usuario_id': usuario_id,
        'ubicacion_id': ubicacion_id,
        'estados': PlatoProducido.ESTADO_CHOICES,
        'usuarios': usuarios,
        'ubicaciones': ubicaciones,
    }
    return render(request, 'produccion/platos_producidos/lista.html', context)


@login_required
@menu_required('produccion', 'recetas')
def crear_plato_producido(request):
    """Crear un nuevo plato producido y descontar lotes según receta (editable)"""
    import json
    
    # Función helper para obtener el contexto completo
    def obtener_contexto_completo(form, formset, plato_seleccionado=None):
        # Obtener recetas para JavaScript
        recetas_por_plato = {}
        platos_con_receta = Plato.objects.filter(receta__isnull=False).distinct()
        for plato in platos_con_receta:
            recetas = Receta.objects.filter(id_plato=plato).select_related('id_insumo')
            recetas_por_plato[plato.id_plato] = [
                {
                    'id_insumo': r.id_insumo.id_insumo,
                    'nombre_insumo': r.id_insumo.nombre_insumo,
                    'cantidad_necesaria': float(r.cantidad_necesaria),
                    'unidad_medida': r.id_insumo.unidad_medida
                }
                for r in recetas
            ]
        
        # Obtener todos los insumos para el formset
        insumos = Insumo.objects.all().order_by('nombre_insumo')
        insumos_json = [
            {
                'id_insumo': i.id_insumo,
                'nombre_insumo': i.nombre_insumo,
                'unidad_medida': i.unidad_medida
            }
            for i in insumos
        ]
        
        context = {
            'title': 'Producir Plato',
            'form': form,
            'formset': formset,
            'recetas_por_plato_json': json.dumps(recetas_por_plato),
            'insumos_json': json.dumps(insumos_json),
        }
        
        if plato_seleccionado:
            context['plato_seleccionado'] = plato_seleccionado
        
        return context
    
    if request.method == 'POST':
        form = PlatoProducidoForm(request.POST)
        formset = IngredienteProduccionFormSet(request.POST, prefix='ingredientes')
        
        if form.is_valid() and formset.is_valid():
            plato = form.cleaned_data['id_plato']
            
            try:
                # Validar ubicación cocina antes de entrar en transacción
                ubicacion_cocina = obtener_ubicacion_cocina()
                
                # Procesar ingredientes del formset
                ingredientes_personalizados = []
                for form_ingrediente in formset.forms:
                    # Verificar si el formulario debe eliminarse
                    if form_ingrediente.cleaned_data.get('DELETE', False):
                        continue
                    
                    id_insumo = form_ingrediente.cleaned_data.get('id_insumo')
                    cantidad = form_ingrediente.cleaned_data.get('cantidad_necesaria')
                    
                    if id_insumo and cantidad:
                        ingredientes_personalizados.append({
                            'id_insumo': id_insumo,
                            'cantidad_necesaria': cantidad
                        })
                
                if not ingredientes_personalizados:
                    messages.error(request, 'Debe agregar al menos un ingrediente válido.')
                    context = obtener_contexto_completo(form, formset, plato)
                    return render(request, 'produccion/platos_producidos/crear.html', context)
                
                # Ahora sí, entrar en transacción atómica
                with transaction.atomic():
                    # Descontar lotes según ingredientes personalizados (FIFO)
                    detalles_produccion, movimientos_stock = descontar_lotes_para_produccion(
                        plato, request.user, ingredientes_personalizados
                    )
                    
                    # Crear plato producido
                    plato_producido = PlatoProducido.objects.create(
                        id_plato=plato,
                        id_ubicacion=ubicacion_cocina,
                        estado='en_cocina',
                        id_usuario=request.user
                    )
                    
                    # Crear detalles de producción
                    for detalle in detalles_produccion:
                        DetalleProduccionInsumo.objects.create(
                            id_plato_producido=plato_producido,
                            id_lote=detalle['lote'],
                            id_insumo=detalle['insumo'],
                            cantidad_usada=detalle['cantidad']
                        )
                
                messages.success(
                    request, 
                    f'Plato "{plato.nombre_plato}" producido exitosamente. Estado: En Cocina'
                )
                return redirect('produccion:lista_platos_producidos')
                
            except ValueError as e:
                messages.error(request, str(e))
                context = obtener_contexto_completo(form, formset, plato)
                return render(request, 'produccion/platos_producidos/crear.html', context)
            except Exception as e:
                messages.error(request, f'Error al producir el plato: {str(e)}')
                context = obtener_contexto_completo(form, formset, plato if 'plato' in locals() else None)
                return render(request, 'produccion/platos_producidos/crear.html', context)
        else:
            # Si el formulario no es válido, mostrar errores
            plato_seleccionado = None
            if form.is_valid():
                plato_seleccionado = form.cleaned_data.get('id_plato')
            context = obtener_contexto_completo(form, formset, plato_seleccionado)
            return render(request, 'produccion/platos_producidos/crear.html', context)
    else:
        form = PlatoProducidoForm()
        formset = IngredienteProduccionFormSet(prefix='ingredientes')
        context = obtener_contexto_completo(form, formset)
        return render(request, 'produccion/platos_producidos/crear.html', context)


@login_required
@menu_required('produccion', 'recetas')
def detalle_plato_producido(request, plato_producido_id):
    """Ver detalles de un plato producido"""
    plato_producido = get_object_or_404(
        PlatoProducido.objects.select_related('id_plato', 'id_ubicacion', 'id_usuario'),
        id_plato_producido=plato_producido_id
    )
    
    detalles_insumos = DetalleProduccionInsumo.objects.filter(
        id_plato_producido=plato_producido
    ).select_related('id_lote', 'id_insumo').order_by('id_insumo__nombre_insumo')
    
    context = {
        'title': f'Detalle: {plato_producido.id_plato.nombre_plato}',
        'plato_producido': plato_producido,
        'detalles_insumos': detalles_insumos,
    }
    return render(request, 'produccion/platos_producidos/detalle.html', context)


@login_required
@menu_required('produccion', 'recetas')
def mover_plato_a_mesa(request, plato_producido_id):
    """Mover un plato de cocina a mesa"""
    plato_producido = get_object_or_404(PlatoProducido, id_plato_producido=plato_producido_id)
    
    if plato_producido.estado != 'en_cocina':
        messages.warning(request, f'El plato solo se puede mover a mesa si está en cocina. Estado actual: {plato_producido.get_estado_display()}')
        return redirect('produccion:detalle_plato_producido', plato_producido_id=plato_producido_id)
    
    if request.method == 'POST':
        try:
            ubicacion_mesa = obtener_ubicacion_mesa()
            plato_producido.id_ubicacion = ubicacion_mesa
            plato_producido.estado = 'en_mesa'
            plato_producido.save()
            
            messages.success(request, f'Plato "{plato_producido.id_plato.nombre_plato}" movido a mesa exitosamente.')
            return redirect('produccion:lista_platos_producidos')
        except ValueError as e:
            messages.error(request, str(e))
            return redirect('produccion:detalle_plato_producido', plato_producido_id=plato_producido_id)
    
    context = {
        'title': 'Mover a Mesa',
        'plato_producido': plato_producido,
    }
    return render(request, 'produccion/platos_producidos/mover_mesa.html', context)


@login_required
@menu_required('produccion', 'recetas')
def eliminar_plato_producido(request, plato_producido_id):
    """Eliminar un plato producido y revertir los descuentos de lotes"""
    plato_producido = get_object_or_404(
        PlatoProducido.objects.select_related('id_plato', 'id_ubicacion'),
        id_plato_producido=plato_producido_id
    )
    
    # Solo permitir eliminar si está en cocina o en mesa (no si ya fue vendido o mermado)
    if plato_producido.estado not in ['en_cocina', 'en_mesa']:
        messages.error(
            request, 
            f'No se puede eliminar un plato en estado "{plato_producido.get_estado_display()}". '
            f'Solo se pueden eliminar platos en estado "En Cocina" o "En Mesa".'
        )
        return redirect('produccion:detalle_plato_producido', plato_producido_id=plato_producido_id)
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Obtener usuario del sistema
                try:
                    from ventas.views import obtener_usuario_desde_django_user
                    usuario = obtener_usuario_desde_django_user(request.user)
                except ImportError:
                    try:
                        usuario = Usuario.objects.get(email=request.user.email)
                    except Usuario.DoesNotExist:
                        usuario = Usuario.objects.first()
                
                if not usuario:
                    raise ValueError('No se pudo obtener el usuario del sistema.')
                
                # Obtener todos los detalles de producción (insumos usados)
                detalles = DetalleProduccionInsumo.objects.filter(
                    id_plato_producido=plato_producido
                ).select_related('id_lote')
                
                # Revertir los descuentos: devolver las cantidades a los lotes
                for detalle in detalles:
                    lote = detalle.id_lote
                    cantidad_a_devolver = detalle.cantidad_usada
                    
                    # Devolver la cantidad al lote
                    lote.cantidad_actual += cantidad_a_devolver
                    lote.save()
                    
                    # Crear un movimiento de stock de entrada para registrar la devolución
                    MovimientoStock.objects.create(
                        id_lote=lote,
                        id_usuario=usuario,
                        fecha_movimiento=timezone.now().date(),
                        tipo_movimiento='entrada',
                        origen_movimiento='produccion',
                        cantidad=cantidad_a_devolver
                    )
                
                # Eliminar los detalles de producción
                detalles.delete()
                
                # Guardar información antes de eliminar
                nombre_plato = plato_producido.id_plato.nombre_plato
                
                # Eliminar el plato producido
                plato_producido.delete()
            
            messages.success(
                request, 
                f'Plato "{nombre_plato}" eliminado exitosamente. '
                f'El stock consumido ha sido devuelto a los lotes correspondientes.'
            )
            return redirect('produccion:lista_platos_producidos')
            
        except Exception as e:
            messages.error(request, f'Error al eliminar el plato: {str(e)}')
            return redirect('produccion:detalle_plato_producido', plato_producido_id=plato_producido_id)
    
    # Obtener detalles para mostrar en la confirmación
    detalles_insumos = DetalleProduccionInsumo.objects.filter(
        id_plato_producido=plato_producido
    ).select_related('id_lote', 'id_insumo').order_by('id_insumo__nombre_insumo')
    
    context = {
        'title': 'Eliminar Producción de Plato',
        'plato_producido': plato_producido,
        'detalles_insumos': detalles_insumos,
    }
    return render(request, 'produccion/platos_producidos/eliminar.html', context)


@login_required
@menu_required('produccion', 'recetas')
def redirigir_mermar_plato(request, plato_producido_id):
    """Redirigir al formulario de merma de plato con el plato pre-seleccionado"""
    plato_producido = get_object_or_404(PlatoProducido, id_plato_producido=plato_producido_id)
    
    # Redirigir al formulario de merma con el plato seleccionado
    return redirect(f"{reverse('inventario:crear_merma_plato')}?plato_producido_id={plato_producido_id}")


# ========== GESTIÓN DE COMANDAS EN PRODUCCIÓN ==========

@login_required
@menu_required('produccion', 'comandas')
def lista_comandas(request):
    """Lista todas las comandas para que el chef las vea y actualice"""
    comandas = Comanda.objects.select_related(
        'id_mesa', 'id_usuario'
    ).prefetch_related('detalles__id_plato').exclude(
        estado__in=['entregada', 'cancelada']
    ).order_by('-fecha_creacion')
    
    # Filtros
    estado_filtro = request.GET.get('estado', '')
    mesa_id = request.GET.get('mesa', '')
    
    if estado_filtro:
        comandas = comandas.filter(estado=estado_filtro)
    
    if mesa_id:
        comandas = comandas.filter(id_mesa_id=mesa_id)
    
    # Paginación
    paginator = Paginator(comandas, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Datos para filtros
    from ventas.models import Mesa
    mesas = Mesa.objects.filter(activa=True).order_by('numero_mesa')
    
    context = {
        'title': 'Comandas - Producción',
        'page_obj': page_obj,
        'estado_filtro': estado_filtro,
        'mesa_id': mesa_id,
        'estados': Comanda.ESTADO_CHOICES,
        'mesas': mesas,
    }
    return render(request, 'produccion/comandas/lista.html', context)


@login_required
@menu_required('produccion', 'comandas')
def detalle_comanda_produccion(request, comanda_id):
    """Ver detalle de una comanda en producción y actualizar estados"""
    comanda = get_object_or_404(
        Comanda.objects.select_related('id_mesa', 'id_usuario'),
        id_comanda=comanda_id
    )
    
    detalles = DetalleComanda.objects.filter(
        id_comanda=comanda
    ).select_related('id_plato', 'id_plato_producido').order_by('id_plato__nombre_plato')
    
    context = {
        'title': f'Comanda #{comanda.id_comanda} - Producción',
        'comanda': comanda,
        'detalles': detalles,
    }
    return render(request, 'produccion/comandas/detalle.html', context)


@login_required
@menu_required('produccion', 'comandas')
def actualizar_estado_detalles(request, comanda_id):
    """Actualizar el estado de los detalles de una comanda (chef marca platos como listos)"""
    comanda = get_object_or_404(Comanda, id_comanda=comanda_id)
    
    if request.method == 'POST':
        detalles_actualizados = []
        
        try:
            with transaction.atomic():
                # Obtener usuario del sistema
                try:
                    from ventas.views import obtener_usuario_desde_django_user
                    usuario_sistema = obtener_usuario_desde_django_user(request.user)
                except ImportError:
                    try:
                        usuario_sistema = Usuario.objects.get(email=request.user.email)
                    except Usuario.DoesNotExist:
                        usuario_sistema = Usuario.objects.first()
                
                if not usuario_sistema:
                    raise ValueError('No se pudo obtener el usuario del sistema.')
                
                # Obtener ubicación cocina
                ubicacion_cocina = obtener_ubicacion_cocina()
                
                # Procesar cada detalle
                for detalle in DetalleComanda.objects.filter(id_comanda=comanda):
                    nuevo_estado = request.POST.get(f'estado_{detalle.id_detalle_comanda}')
                    
                    if nuevo_estado and nuevo_estado != detalle.estado:
                        estado_anterior = detalle.estado
                        detalle.estado = nuevo_estado
                        
                        # Si se marca como "listo" y no tiene plato producido, crearlo y descontar lotes
                        if nuevo_estado == 'listo' and not detalle.id_plato_producido:
                            try:
                                # Descontar lotes según la receta del plato usando FIFO (lote más próximo a vencer primero)
                                detalles_produccion, movimientos_stock = descontar_lotes_para_produccion(
                                    detalle.id_plato, request.user, None
                                )
                                
                                # Crear plato producido para este detalle
                                plato_producido = PlatoProducido.objects.create(
                                    id_plato=detalle.id_plato,
                                    id_ubicacion=ubicacion_cocina,
                                    estado='en_cocina',
                                    id_usuario=request.user
                                )
                                
                                # Crear detalles de producción (insumos usados)
                                for detalle_prod in detalles_produccion:
                                    DetalleProduccionInsumo.objects.create(
                                        id_plato_producido=plato_producido,
                                        id_lote=detalle_prod['lote'],
                                        id_insumo=detalle_prod['insumo'],
                                        cantidad_usada=detalle_prod['cantidad']
                                    )
                                
                                # Asociar el plato producido al detalle
                                detalle.id_plato_producido = plato_producido
                            except ValueError as e:
                                # Si hay error (stock insuficiente, sin receta, etc.), no cambiar el estado
                                messages.error(request, f'Error al producir "{detalle.id_plato.nombre_plato}": {str(e)}')
                                detalle.estado = estado_anterior  # Revertir el cambio de estado
                                continue
                        
                        detalle.save()
                        detalles_actualizados.append({
                            'detalle': detalle,
                            'estado_anterior': estado_anterior,
                            'nuevo_estado': nuevo_estado
                        })
                
                # Actualizar estado de la comanda
                comanda.actualizar_estado()
                
                if detalles_actualizados:
                    mensaje = f'Se actualizaron {len(detalles_actualizados)} detalle(s) de la comanda.'
                    messages.success(request, mensaje)
                else:
                    messages.info(request, 'No se realizaron cambios.')
                
                return redirect('produccion:detalle_comanda_produccion', comanda_id=comanda_id)
                
        except ValueError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f'Error al actualizar los estados: {str(e)}')
    
    return redirect('produccion:detalle_comanda_produccion', comanda_id=comanda_id)
