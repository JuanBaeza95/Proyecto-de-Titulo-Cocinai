"""
Comando para generar datos históricos completos del año 2024
Incluye: Compras -> Lotes -> Producción -> Ventas
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from datetime import datetime, timedelta, date
from decimal import Decimal
from inventario.models import (
    Insumo, Plato, DetalleProduccionInsumo, 
    PlatoProducido, Receta, Ubicacion, Lote,
    OrdenCompra, DetalleCompra, Proveedor,
    MovimientoStock, Usuario, RegistroVentaPlato
)
from django.contrib.auth.models import User
import random


def generar_numero_lote(insumo, fecha_ingreso):
    """Genera un número de lote basado en el código del insumo y fecha"""
    if not insumo.codigo:
        codigo_insumo = insumo.nombre_insumo[:3].upper()
    else:
        codigo_insumo = insumo.codigo.upper()
    
    # Usar año y mes en el número de lote
    año_mes = fecha_ingreso.strftime('%Y%m')
    
    # Buscar lotes existentes con este patrón
    lotes_existentes = Lote.objects.filter(
        id_insumo=insumo,
        numero_lote__startswith=f'{codigo_insumo}-{año_mes}-'
    )
    
    numeros_existentes = []
    for lote in lotes_existentes:
        try:
            partes = lote.numero_lote.split('-')
            if len(partes) >= 3:
                numero = int(partes[2])
                numeros_existentes.append(numero)
        except (ValueError, IndexError):
            continue
    
    siguiente_numero = max(numeros_existentes) + 1 if numeros_existentes else 1
    return f"{codigo_insumo}-{año_mes}-{siguiente_numero:02d}"


class Command(BaseCommand):
    help = 'Genera datos históricos completos del año 2024 (compras, lotes, producción, ventas)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--ano',
            type=int,
            default=2024,
            help='Año a generar (default: 2024)'
        )
        parser.add_argument(
            '--mes-inicio',
            type=int,
            default=1,
            help='Mes de inicio (1-12)'
        )
        parser.add_argument(
            '--mes-fin',
            type=int,
            default=12,
            help='Mes de fin (1-12)'
        )
        parser.add_argument(
            '--compras-por-mes',
            type=int,
            default=4,
            help='Número de compras por mes'
        )
        parser.add_argument(
            '--producciones-por-dia',
            type=int,
            default=15,
            help='Número promedio de producciones por día (default: 15, equilibrado)'
        )

    def handle(self, *args, **options):
        año = options['ano']
        mes_inicio = options['mes_inicio']
        mes_fin = options['mes_fin']
        compras_por_mes = options['compras_por_mes']
        producciones_por_dia = options['producciones_por_dia']
        
        # Validar datos básicos
        insumos = Insumo.objects.all()
        platos = Plato.objects.all()
        proveedores = Proveedor.objects.all()
        
        if not insumos.exists():
            self.stdout.write(self.style.ERROR('No hay insumos en el sistema'))
            return
        
        if not platos.exists():
            self.stdout.write(self.style.ERROR('No hay platos en el sistema'))
            return
        
        if not proveedores.exists():
            self.stdout.write(self.style.ERROR('No hay proveedores en el sistema'))
            return
        
        # Obtener ubicaciones
        ubicacion_bodega = Ubicacion.objects.filter(tipo_ubicacion='bodega').first()
        ubicacion_cocina = Ubicacion.objects.filter(tipo_ubicacion='cocina').first()
        
        if not ubicacion_bodega:
            ubicacion_bodega = Ubicacion.objects.first()
        if not ubicacion_cocina:
            ubicacion_cocina = ubicacion_bodega
        
        # Obtener usuario
        usuario_django = User.objects.first()
        if not usuario_django:
            self.stdout.write(self.style.ERROR('No hay usuarios en el sistema'))
            return
        
        try:
            usuario = Usuario.objects.get(email=usuario_django.email)
        except Usuario.DoesNotExist:
            usuario = Usuario.objects.first()
            if not usuario:
                self.stdout.write(self.style.ERROR('No hay usuarios en la tabla USUARIO'))
                return
        
        self.stdout.write(f'Generando datos históricos para {año} (meses {mes_inicio}-{mes_fin})...')
        self.stdout.write(f'Producciones por día: {producciones_por_dia} (equilibrado)')
        
        ordenes_creadas = 0
        lotes_creados = 0
        platos_producidos = 0
        ventas_creadas = 0
        
        # Procesar mes por mes
        for mes in range(mes_inicio, mes_fin + 1):
            self.stdout.write(f'\n--- Procesando mes {mes}/{año} ---')
            
            # 1. CREAR COMPRAS (al inicio de cada mes)
            if mes == 12:
                fecha_base_mes = date(año, mes, 1)
                dias_en_mes = (date(año + 1, 1, 1) - timedelta(days=1)).day
            else:
                fecha_base_mes = date(año, mes, 1)
                dias_en_mes = (date(año, mes + 1, 1) - timedelta(days=1)).day
            
            # Crear compras distribuidas en el mes
            dias_entre_compras = max(1, dias_en_mes // compras_por_mes)
            
            for compra_num in range(compras_por_mes):
                dia_compra = min(1 + (compra_num * dias_entre_compras), dias_en_mes)
                fecha_compra = date(año, mes, dia_compra)
                
                # Seleccionar proveedor aleatorio
                proveedor = random.choice(proveedores)
                
                # Crear orden de compra
                orden = OrdenCompra.objects.create(
                    id_proveedor=proveedor,
                    fecha_pedido=fecha_compra,
                    estado='recibida'
                )
                ordenes_creadas += 1
                
                # Crear detalles de compra (3-8 insumos por orden)
                num_insumos = random.randint(3, min(8, insumos.count()))
                insumos_orden = random.sample(list(insumos), num_insumos)
                
                for insumo in insumos_orden:
                    # Cantidad y costo realistas según el insumo
                    if 'kg' in insumo.unidad_medida.lower():
                        cantidad = Decimal(random.uniform(50, 200)).quantize(Decimal('0.01'))  # Más cantidad para tener stock
                        costo = Decimal(random.uniform(500, 5000)).quantize(Decimal('0.01'))
                    elif 'und' in insumo.unidad_medida.lower() or 'unidad' in insumo.unidad_medida.lower():
                        cantidad = Decimal(random.uniform(50, 300)).quantize(Decimal('0.01'))  # Más cantidad
                        costo = Decimal(random.uniform(100, 2000)).quantize(Decimal('0.01'))
                    else:
                        cantidad = Decimal(random.uniform(20, 100)).quantize(Decimal('0.01'))  # Más cantidad
                        costo = Decimal(random.uniform(300, 3000)).quantize(Decimal('0.01'))
                    
                    # Crear detalle de compra
                    detalle_compra = DetalleCompra.objects.create(
                        id_orden_compra=orden,
                        id_insumo=insumo,
                        cantidad_pedida=cantidad,
                        costo_unitario_acordado=costo
                    )
                    
                    # 2. CREAR LOTE (recibir la compra 2-5 días después)
                    fecha_recepcion = fecha_compra + timedelta(days=random.randint(2, 5))
                    fecha_vencimiento = fecha_recepcion + timedelta(days=random.randint(60, 120))  # Más días de vencimiento
                    
                    numero_lote = generar_numero_lote(insumo, fecha_recepcion)
                    
                    lote = Lote.objects.create(
                        id_detalle_compra=detalle_compra,
                        id_insumo=insumo,
                        id_ubicacion=ubicacion_bodega,
                        costo_unitario=costo,
                        fecha_vencimiento=fecha_vencimiento,
                        fecha_ingreso=fecha_recepcion,
                        cantidad_actual=cantidad,
                        numero_lote=numero_lote
                    )
                    lotes_creados += 1
                    
                    # 3. CREAR MOVIMIENTO DE STOCK (entrada por compra)
                    MovimientoStock.objects.create(
                        id_lote=lote,
                        id_usuario=usuario,
                        fecha_movimiento=fecha_recepcion,
                        tipo_movimiento='entrada',
                        origen_movimiento='compra',
                        cantidad=cantidad
                    )
            
            # 4. CREAR PRODUCCIÓN Y VENTAS (distribuidas durante el mes)
            # Producir platos 5-6 días por semana
            platos_con_receta = [p for p in platos if Receta.objects.filter(id_plato=p).exists()]
            
            if not platos_con_receta:
                self.stdout.write(self.style.WARNING(f'No hay platos con recetas en el mes {mes}'))
                continue
            
            # Esperar al menos 5 días después de la primera compra para empezar a producir
            # Esto asegura que haya lotes disponibles
            dia_inicio_produccion = min(5, dias_en_mes)
            
            for dia in range(dia_inicio_produccion, dias_en_mes + 1):
                fecha_actual = date(año, mes, dia)
                
                # No producir domingos (día 6 = domingo en weekday())
                if fecha_actual.weekday() == 6:
                    continue
                
                # Variar producción según día de semana (más los fines de semana)
                # Usar el parámetro producciones_por_dia como base
                if fecha_actual.weekday() >= 5:  # Sábado
                    num_producciones = random.randint(
                        int(producciones_por_dia * 1.2), 
                        int(producciones_por_dia * 1.8)
                    )
                else:
                    num_producciones = random.randint(
                        int(producciones_por_dia * 0.8), 
                        int(producciones_por_dia * 1.2)
                    )
                
                # Producir platos
                for _ in range(num_producciones):
                    plato = random.choice(platos_con_receta)
                    recetas = Receta.objects.filter(id_plato=plato).select_related('id_insumo')
                    
                    if not recetas.exists():
                        continue
                    
                    # Hora de producción (distribuida durante el día)
                    hora_produccion = random.randint(8, 20)
                    fecha_produccion = datetime.combine(
                        fecha_actual,
                        datetime.min.time().replace(hour=hora_produccion, minute=random.randint(0, 59))
                    )
                    fecha_produccion = timezone.make_aware(fecha_produccion)
                    
                    # Verificar que hay lotes disponibles para todos los ingredientes
                    lotes_disponibles = {}
                    puede_producir = True
                    
                    for receta in recetas:
                        # Buscar lote disponible (FIFO por fecha de vencimiento)
                        # Buscar en bodega primero, luego en cocina
                        lote = Lote.objects.filter(
                            id_insumo=receta.id_insumo,
                            cantidad_actual__gt=0,
                            fecha_ingreso__lte=fecha_actual
                        ).order_by('fecha_vencimiento', 'fecha_ingreso').first()
                        
                        if not lote:
                            puede_producir = False
                            break
                        
                        # Verificar que hay suficiente cantidad
                        if lote.cantidad_actual < receta.cantidad_necesaria:
                            # Intentar buscar otro lote del mismo insumo
                            lotes_alternativos = Lote.objects.filter(
                                id_insumo=receta.id_insumo,
                                cantidad_actual__gt=0,
                                fecha_ingreso__lte=fecha_actual
                            ).exclude(id_lote=lote.id_lote).order_by('fecha_vencimiento', 'fecha_ingreso')
                            
                            cantidad_total = lote.cantidad_actual
                            for lote_alt in lotes_alternativos:
                                cantidad_total += lote_alt.cantidad_actual
                                if cantidad_total >= receta.cantidad_necesaria:
                                    break
                            
                            if cantidad_total < receta.cantidad_necesaria:
                                puede_producir = False
                                break
                        
                        lotes_disponibles[receta.id_insumo] = lote
                    
                    if not puede_producir:
                        continue
                    
                    # Crear plato producido
                    # IMPORTANTE: Usar save() con update_fields para evitar auto_now_add
                    plato_producido = PlatoProducido(
                        id_plato=plato,
                        id_ubicacion=ubicacion_cocina,
                        estado='venta',  # Directamente vendido
                        fecha_entrega=fecha_produccion + timedelta(minutes=random.randint(15, 45)),
                        id_usuario=usuario_django
                    )
                    # Guardar primero sin fecha_produccion
                    plato_producido.save()
                    # Luego actualizar la fecha_produccion manualmente
                    PlatoProducido.objects.filter(id_plato_producido=plato_producido.id_plato_producido).update(
                        fecha_produccion=fecha_produccion
                    )
                    plato_producido.refresh_from_db()
                    platos_producidos += 1
                    
                    # Crear detalles de producción y descontar lotes
                    for receta in recetas:
                        lote = lotes_disponibles[receta.id_insumo]
                        cantidad_usada = receta.cantidad_necesaria
                        
                        # Variar ligeramente la cantidad usada
                        cantidad_usada = cantidad_usada * Decimal(random.uniform(0.95, 1.05))
                        cantidad_usada = cantidad_usada.quantize(Decimal('0.01'))
                        
                        # Crear detalle de producción
                        DetalleProduccionInsumo.objects.create(
                            id_plato_producido=plato_producido,
                            id_lote=lote,
                            id_insumo=receta.id_insumo,
                            cantidad_usada=cantidad_usada,
                            fecha_uso=fecha_produccion
                        )
                        
                        # Descontar del lote
                        lote.cantidad_actual -= cantidad_usada
                        if lote.cantidad_actual < 0:
                            lote.cantidad_actual = Decimal('0')
                        lote.save()
                        
                        # Crear movimiento de stock (salida por producción)
                        MovimientoStock.objects.create(
                            id_lote=lote,
                            id_usuario=usuario,
                            fecha_movimiento=fecha_actual,
                            tipo_movimiento='salida',
                            origen_movimiento='produccion',
                            cantidad=cantidad_usada
                        )
                    
                    # Crear registro de venta con la MISMA fecha que la producción
                    # Esto asegura consistencia en las predicciones
                    fecha_venta = fecha_produccion.date()  # Usar la fecha exacta de producción
                    RegistroVentaPlato.objects.create(
                        id_plato=plato,
                        fecha_venta=fecha_venta,
                        cantidad_vendida=1
                    )
                    ventas_creadas += 1
        
        self.stdout.write(self.style.SUCCESS('\n' + '='*60))
        self.stdout.write(self.style.SUCCESS(f'RESUMEN DE DATOS GENERADOS PARA {año}:'))
        self.stdout.write(self.style.SUCCESS('='*60))
        self.stdout.write(self.style.SUCCESS(f'Ordenes de compra: {ordenes_creadas}'))
        self.stdout.write(self.style.SUCCESS(f'Lotes creados: {lotes_creados}'))
        self.stdout.write(self.style.SUCCESS(f'Platos producidos: {platos_producidos}'))
        self.stdout.write(self.style.SUCCESS(f'Ventas registradas: {ventas_creadas}'))
        self.stdout.write(self.style.SUCCESS('='*60))
        self.stdout.write(self.style.SUCCESS(f'\n[OK] Datos historicos de {año} generados exitosamente!'))
        self.stdout.write(self.style.SUCCESS('Las fechas de venta coinciden con las fechas de produccion.'))
        self.stdout.write(self.style.SUCCESS('Ahora puedes usar las predicciones con comparacion ano anterior.'))

