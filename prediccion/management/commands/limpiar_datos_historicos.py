"""
Comando para limpiar datos históricos de 2024 y 2025
Elimina producción, ventas y registros relacionados manteniendo integridad referencial
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from datetime import date
from inventario.models import (
    PlatoProducido, DetalleProduccionInsumo, RegistroVentaPlato,
    MovimientoStock, Merma, Lote, DetalleCompra, OrdenCompra
)
from ventas.models import DetalleComanda, Comanda, MovimientoMesa


class Command(BaseCommand):
    help = 'Limpia todos los datos historicos de 2024 y 2025'

    def add_arguments(self, parser):
        parser.add_argument(
            '--año',
            type=int,
            help='Año específico a limpiar (2024 o 2025). Si no se especifica, limpia ambos.'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Solo mostrar qué se eliminaría sin hacer cambios'
        )

    def handle(self, *args, **options):
        año = options.get('año')
        dry_run = options['dry_run']
        
        años_a_limpiar = []
        if año:
            if año not in [2024, 2025]:
                self.stdout.write(self.style.ERROR('El año debe ser 2024 o 2025'))
                return
            años_a_limpiar = [año]
        else:
            años_a_limpiar = [2024, 2025]
        
        self.stdout.write(f'\n{"="*60}')
        self.stdout.write(f'LIMPIEZA DE DATOS HISTORICOS')
        self.stdout.write(f'{"="*60}')
        self.stdout.write(f'Anos a limpiar: {", ".join(map(str, años_a_limpiar))}')
        self.stdout.write(f'Modo: {"DRY RUN (sin cambios)" if dry_run else "EJECUCION REAL"}')
        self.stdout.write(f'{"="*60}\n')
        
        try:
            with transaction.atomic():
                total_eliminado = {
                    'platos_producidos': 0,
                    'detalles_produccion': 0,
                    'ventas': 0,
                    'movimientos_mesa': 0,
                    'mermas': 0,
                    'detalles_comanda': 0,
                    'lotes': 0,
                    'ordenes_compra': 0
                }
                
                for año_limpiar in años_a_limpiar:
                    self.stdout.write(f'\n--- Limpiando datos de {año_limpiar} ---')
                    
                    # 1. Obtener platos producidos del año
                    platos = PlatoProducido.objects.filter(
                        fecha_produccion__year=año_limpiar
                    )
                    count_platos = platos.count()
                    
                    if count_platos > 0:
                        # Obtener IDs antes de eliminar
                        platos_ids = list(platos.values_list('id_plato_producido', flat=True))
                        
                        # Contar registros relacionados
                        detalles_produccion = DetalleProduccionInsumo.objects.filter(
                            id_plato_producido__in=platos_ids
                        ).count()
                        
                        movimientos_mesa = MovimientoMesa.objects.filter(
                            id_plato_producido__in=platos_ids
                        ).count()
                        
                        mermas = Merma.objects.filter(
                            id_plato_producido__in=platos_ids
                        ).count()
                        
                        detalles_comanda = DetalleComanda.objects.filter(
                            id_plato_producido__in=platos_ids
                        ).count()
                        
                        # Obtener fechas de producción para eliminar ventas
                        fechas_produccion = platos.values_list('fecha_produccion__date', 'id_plato').distinct()
                        platos_ids_for_ventas = platos.values_list('id_plato', flat=True).distinct()
                        
                        # Contar ventas relacionadas
                        ventas_count = 0
                        for fecha_prod, plato_id in fechas_produccion:
                            ventas = RegistroVentaPlato.objects.filter(
                                id_plato=plato_id,
                                fecha_venta=fecha_prod
                            )
                            ventas_count += ventas.count()
                        
                        self.stdout.write(f'  Platos producidos: {count_platos}')
                        self.stdout.write(f'  Detalles de produccion: {detalles_produccion}')
                        self.stdout.write(f'  Ventas relacionadas: {ventas_count}')
                        self.stdout.write(f'  Movimientos de mesa: {movimientos_mesa}')
                        self.stdout.write(f'  Mermas: {mermas}')
                        self.stdout.write(f'  Detalles de comanda: {detalles_comanda}')
                        
                        if not dry_run:
                            # Eliminar en orden inverso de dependencias
                            # 1. Movimientos de mesa (RESTRICT)
                            MovimientoMesa.objects.filter(
                                id_plato_producido__in=platos_ids
                            ).delete()
                            
                            # 2. Mermas
                            Merma.objects.filter(
                                id_plato_producido__in=platos_ids
                            ).delete()
                            
                            # 3. Desvincular detalles de comanda
                            DetalleComanda.objects.filter(
                                id_plato_producido__in=platos_ids
                            ).update(id_plato_producido=None)
                            
                            # 4. Eliminar ventas relacionadas (misma fecha que producción)
                            for fecha_prod, plato_id in fechas_produccion:
                                RegistroVentaPlato.objects.filter(
                                    id_plato=plato_id,
                                    fecha_venta=fecha_prod
                                ).delete()
                            
                            # 5. Los detalles de producción se eliminan por CASCADE
                            # 6. Eliminar platos producidos
                            platos.delete()
                            
                            total_eliminado['platos_producidos'] += count_platos
                            total_eliminado['detalles_produccion'] += detalles_produccion
                            total_eliminado['ventas'] += ventas_count
                            total_eliminado['movimientos_mesa'] += movimientos_mesa
                            total_eliminado['mermas'] += mermas
                            total_eliminado['detalles_comanda'] += detalles_comanda
                    
                    # 2. Eliminar ventas adicionales del año (sin plato producido relacionado)
                    ventas_adicionales = RegistroVentaPlato.objects.filter(
                        fecha_venta__year=año_limpiar
                    )
                    count_ventas_adicionales = ventas_adicionales.count()
                    
                    if count_ventas_adicionales > 0:
                        self.stdout.write(f'  Ventas adicionales (sin plato producido): {count_ventas_adicionales}')
                        if not dry_run:
                            ventas_adicionales.delete()
                            total_eliminado['ventas'] += count_ventas_adicionales
                    
                    # 3. Eliminar lotes del año (opcional, solo si no hay stock actual)
                    lotes = Lote.objects.filter(
                        fecha_ingreso__year=año_limpiar,
                        cantidad_actual=0  # Solo lotes vacíos
                    )
                    count_lotes = lotes.count()
                    
                    if count_lotes > 0:
                        self.stdout.write(f'  Lotes vacios: {count_lotes}')
                        if not dry_run:
                            # Verificar que no tengan movimientos de stock
                            lotes_ids = list(lotes.values_list('id_lote', flat=True))
                            movimientos = MovimientoStock.objects.filter(
                                id_lote__in=lotes_ids
                            ).count()
                            
                            if movimientos == 0:
                                # Eliminar detalles de compra relacionados
                                detalles_compra = DetalleCompra.objects.filter(
                                    id_detalle_compra__in=lotes.values_list('id_detalle_compra', flat=True)
                                )
                                detalles_compra_ids = list(detalles_compra.values_list('id_detalle_compra', flat=True))
                                
                                # Eliminar órdenes de compra si no tienen otros detalles
                                ordenes_ids = list(detalles_compra.values_list('id_orden_compra', flat=True).distinct())
                                for orden_id in ordenes_ids:
                                    otros_detalles = DetalleCompra.objects.filter(
                                        id_orden_compra=orden_id
                                    ).exclude(id_detalle_compra__in=detalles_compra_ids).count()
                                    
                                    if otros_detalles == 0:
                                        OrdenCompra.objects.filter(id_orden_compra=orden_id).delete()
                                
                                detalles_compra.delete()
                                lotes.delete()
                                total_eliminado['lotes'] += count_lotes
                
                if dry_run:
                    self.stdout.write(self.style.WARNING('\n[DRY RUN] MODO DRY RUN: No se realizaron cambios'))
                    self.stdout.write('Ejecuta sin --dry-run para aplicar los cambios')
                else:
                    self.stdout.write(self.style.SUCCESS('\n' + '='*60))
                    self.stdout.write(self.style.SUCCESS('RESUMEN DE LIMPIEZA:'))
                    self.stdout.write(self.style.SUCCESS('='*60))
                    self.stdout.write(f'  Platos producidos eliminados: {total_eliminado["platos_producidos"]}')
                    self.stdout.write(f'  Detalles de produccion eliminados: {total_eliminado["detalles_produccion"]}')
                    self.stdout.write(f'  Ventas eliminadas: {total_eliminado["ventas"]}')
                    self.stdout.write(f'  Movimientos de mesa eliminados: {total_eliminado["movimientos_mesa"]}')
                    self.stdout.write(f'  Mermas eliminadas: {total_eliminado["mermas"]}')
                    self.stdout.write(f'  Detalles de comanda desvinculados: {total_eliminado["detalles_comanda"]}')
                    self.stdout.write(f'  Lotes eliminados: {total_eliminado["lotes"]}')
                    self.stdout.write(f'  Ordenes de compra eliminadas: {total_eliminado["ordenes_compra"]}')
                    self.stdout.write(self.style.SUCCESS('='*60))
                    self.stdout.write(self.style.SUCCESS('\n[OK] Limpieza completada exitosamente!'))
                    self.stdout.write(self.style.SUCCESS('Ahora puedes generar datos nuevos equilibrados.'))
        
        except Exception as e:
            error_msg = str(e).encode('ascii', 'ignore').decode('ascii')
            self.stdout.write(self.style.ERROR(f'\n[ERROR] Error al limpiar datos: {error_msg}'))
            import traceback
            try:
                traceback_str = traceback.format_exc()
                traceback_clean = traceback_str.encode('ascii', 'ignore').decode('ascii')
                self.stdout.write(traceback_clean)
            except:
                pass
            raise

