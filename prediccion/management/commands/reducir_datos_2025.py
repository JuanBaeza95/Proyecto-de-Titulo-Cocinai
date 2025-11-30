"""
Comando para reducir datos de 2025 en un 80% para equilibrar con 2024
Elimina producción, ventas y registros relacionados manteniendo integridad referencial
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from datetime import datetime, date
from inventario.models import (
    PlatoProducido, DetalleProduccionInsumo, RegistroVentaPlato,
    MovimientoStock, Merma
)
from ventas.models import DetalleComanda, Comanda, MovimientoMesa
import random


class Command(BaseCommand):
    help = 'Reduce datos de 2025 en un 80% para equilibrar con 2024'

    def add_arguments(self, parser):
        parser.add_argument(
            '--porcentaje',
            type=float,
            default=80.0,
            help='Porcentaje de reducción (default: 80.0)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Solo mostrar qué se eliminaría sin hacer cambios'
        )

    def handle(self, *args, **options):
        porcentaje = options['porcentaje']
        dry_run = options['dry_run']
        
        if porcentaje < 0 or porcentaje > 100:
            self.stdout.write(self.style.ERROR('El porcentaje debe estar entre 0 y 100'))
            return
        
        # Calcular fracción a mantener (si eliminamos 80%, mantenemos 20%)
        fraccion_mantener = (100 - porcentaje) / 100.0
        
        self.stdout.write(f'\n{"="*60}')
        self.stdout.write(f'REDUCCION DE DATOS DE 2025')
        self.stdout.write(f'{"="*60}')
        self.stdout.write(f'Porcentaje de reduccion: {porcentaje}%')
        self.stdout.write(f'Fraccion a mantener: {fraccion_mantener*100:.1f}%')
        self.stdout.write(f'Modo: {"DRY RUN (sin cambios)" if dry_run else "EJECUCION REAL"}')
        self.stdout.write(f'{"="*60}\n')
        
        try:
            with transaction.atomic():
                # 1. Obtener todos los platos producidos de 2025
                platos_2025 = PlatoProducido.objects.filter(
                    fecha_produccion__year=2025
                ).order_by('fecha_produccion')
                
                total_platos = platos_2025.count()
                platos_a_mantener = int(total_platos * fraccion_mantener)
                platos_a_eliminar = total_platos - platos_a_mantener
                
                self.stdout.write(f'Platos producidos en 2025: {total_platos}')
                self.stdout.write(f'Platos a mantener: {platos_a_mantener}')
                self.stdout.write(f'Platos a eliminar: {platos_a_eliminar}')
                
                if platos_a_eliminar > 0:
                    # Seleccionar aleatoriamente qué platos mantener (distribuidos en el tiempo)
                    # Esto asegura que no eliminemos todos los datos de un mes específico
                    platos_lista = list(platos_2025)
                    
                    # Estrategia: mantener una distribución uniforme en el tiempo
                    # Dividir en grupos por mes y mantener una fracción de cada mes
                    platos_por_mes = {}
                    for plato in platos_lista:
                        mes = plato.fecha_produccion.month
                        if mes not in platos_por_mes:
                            platos_por_mes[mes] = []
                        platos_por_mes[mes].append(plato)
                    
                    platos_a_eliminar_ids = []
                    platos_a_mantener_ids = []
                    
                    for mes, platos_mes in platos_por_mes.items():
                        total_mes = len(platos_mes)
                        mantener_mes = max(1, int(total_mes * fraccion_mantener))
                        
                        # Seleccionar aleatoriamente qué mantener
                        random.shuffle(platos_mes)
                        mantener = platos_mes[:mantener_mes]
                        eliminar = platos_mes[mantener_mes:]
                        
                        platos_a_mantener_ids.extend([p.id_plato_producido for p in mantener])
                        platos_a_eliminar_ids.extend([p.id_plato_producido for p in eliminar])
                    
                    self.stdout.write(f'\nDistribucion por mes:')
                    for mes in sorted(platos_por_mes.keys()):
                        total_mes = len(platos_por_mes[mes])
                        mantener_mes = len([p for p in platos_por_mes[mes] if p.id_plato_producido in platos_a_mantener_ids])
                        self.stdout.write(f'  Mes {mes}: {total_mes} total, {mantener_mes} a mantener, {total_mes - mantener_mes} a eliminar')
                    
                    if not dry_run:
                        # Eliminar en orden inverso de dependencias
                        # 1. Detalles de producción (se eliminan automáticamente con CASCADE)
                        # 2. Movimientos de stock relacionados
                        # 3. Mermas relacionadas
                        # 4. Detalles de comanda relacionados
                        # 5. Registros de venta relacionados
                        # 6. Finalmente los platos producidos
                        
                        platos_a_eliminar_objs = PlatoProducido.objects.filter(
                            id_plato_producido__in=platos_a_eliminar_ids
                        )
                        
                        # Contar registros relacionados antes de eliminar
                        detalles_produccion = DetalleProduccionInsumo.objects.filter(
                            id_plato_producido__in=platos_a_eliminar_ids
                        ).count()
                        
                        movimientos_stock = MovimientoStock.objects.filter(
                            id_lote__in=platos_a_eliminar_objs.values_list('id_plato_producido', flat=True)
                        ).count()
                        
                        # Obtener IDs de platos para eliminar registros de venta
                        platos_ids = platos_a_eliminar_objs.values_list('id_plato', flat=True)
                        fechas_produccion = platos_a_eliminar_objs.values_list('fecha_produccion__date', flat=True)
                        
                        # Eliminar registros de venta relacionados
                        ventas_eliminadas = 0
                        for plato_obj in platos_a_eliminar_objs:
                            fecha_venta = plato_obj.fecha_produccion.date()
                            ventas = RegistroVentaPlato.objects.filter(
                                id_plato=plato_obj.id_plato,
                                fecha_venta=fecha_venta
                            )
                            ventas_eliminadas += ventas.count()
                            ventas.delete()
                        
                        # Eliminar detalles de comanda relacionados
                        detalles_comanda_eliminados = DetalleComanda.objects.filter(
                            id_plato_producido__in=platos_a_eliminar_ids
                        ).count()
                        DetalleComanda.objects.filter(
                            id_plato_producido__in=platos_a_eliminar_ids
                        ).update(id_plato_producido=None)  # No eliminar, solo desvincular
                        
                        # Eliminar mermas relacionadas
                        mermas_eliminadas = Merma.objects.filter(
                            id_plato_producido__in=platos_a_eliminar_ids
                        ).count()
                        Merma.objects.filter(
                            id_plato_producido__in=platos_a_eliminar_ids
                        ).delete()
                        
                        # Eliminar movimientos de mesa relacionados (RESTRICT)
                        movimientos_mesa_eliminados = MovimientoMesa.objects.filter(
                            id_plato_producido__in=platos_a_eliminar_ids
                        ).count()
                        MovimientoMesa.objects.filter(
                            id_plato_producido__in=platos_a_eliminar_ids
                        ).delete()
                        
                        # Los detalles de producción se eliminan automáticamente por CASCADE
                        # Eliminar los platos producidos
                        platos_a_eliminar_objs.delete()
                        
                        self.stdout.write(self.style.SUCCESS(f'\n[OK] Eliminados exitosamente:'))
                        self.stdout.write(f'  - {platos_a_eliminar} platos producidos')
                        self.stdout.write(f'  - {detalles_produccion} detalles de produccion')
                        self.stdout.write(f'  - {ventas_eliminadas} registros de venta')
                        self.stdout.write(f'  - {detalles_comanda_eliminados} detalles de comanda desvinculados')
                        self.stdout.write(f'  - {mermas_eliminadas} mermas')
                        self.stdout.write(f'  - {movimientos_mesa_eliminados} movimientos de mesa')
                    else:
                        # Contar para dry-run
                        detalles_produccion_count = DetalleProduccionInsumo.objects.filter(
                            id_plato_producido__in=platos_a_eliminar_ids
                        ).count()
                        
                        self.stdout.write(self.style.WARNING(f'\n[DRY RUN] Se eliminarian:'))
                        self.stdout.write(f'  - {platos_a_eliminar} platos producidos')
                        self.stdout.write(f'  - Aproximadamente {detalles_produccion_count} detalles de produccion')
                
                # 2. Eliminar registros de venta adicionales que no estén vinculados a platos producidos
                ventas_2025 = RegistroVentaPlato.objects.filter(
                    fecha_venta__year=2025
                )
                total_ventas = ventas_2025.count()
                ventas_a_mantener = int(total_ventas * fraccion_mantener)
                ventas_a_eliminar = total_ventas - ventas_a_mantener
                
                if ventas_a_eliminar > 0:
                    ventas_lista = list(ventas_2025)
                    random.shuffle(ventas_lista)
                    ventas_a_eliminar_objs = ventas_lista[ventas_a_mantener:]
                    
                    if not dry_run:
                        for venta in ventas_a_eliminar_objs:
                            venta.delete()
                        self.stdout.write(f'\n[OK] Eliminados {ventas_a_eliminar} registros de venta adicionales')
                    else:
                        self.stdout.write(f'\n[DRY RUN] Se eliminarian {ventas_a_eliminar} registros de venta adicionales')
                
                if dry_run:
                    self.stdout.write(self.style.WARNING('\n[DRY RUN] MODO DRY RUN: No se realizaron cambios'))
                    self.stdout.write('Ejecuta sin --dry-run para aplicar los cambios')
                else:
                    # Confirmar transacción
                    self.stdout.write(self.style.SUCCESS('\n' + '='*60))
                    self.stdout.write(self.style.SUCCESS('[OK] Reduccion completada exitosamente!'))
                    self.stdout.write(self.style.SUCCESS('='*60))
                    self.stdout.write(self.style.SUCCESS('\nLos datos de 2025 ahora estan mas equilibrados con 2024.'))
                    self.stdout.write(self.style.SUCCESS('Las predicciones deberian mostrar diferencias mas razonables.'))
        
        except Exception as e:
            error_msg = str(e).encode('ascii', 'ignore').decode('ascii')
            self.stdout.write(self.style.ERROR(f'\n[ERROR] Error al reducir datos: {error_msg}'))
            import traceback
            try:
                traceback_str = traceback.format_exc()
                traceback_clean = traceback_str.encode('ascii', 'ignore').decode('ascii')
                self.stdout.write(traceback_clean)
            except:
                pass
            raise

