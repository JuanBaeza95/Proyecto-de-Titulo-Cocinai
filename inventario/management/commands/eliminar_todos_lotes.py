"""
Comando de Django para eliminar todos los lotes de la base de datos
ADVERTENCIA: Esta operación eliminará los lotes y sus datos relacionados
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from inventario.models import (
    Lote, DetalleProduccionInsumo, MovimientoStock, 
    Merma, DetalleVentaIns
)


class Command(BaseCommand):
    help = 'Elimina todos los lotes de la base de datos y sus datos relacionados'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirmar',
            action='store_true',
            help='Confirma que realmente quieres eliminar todos los lotes',
        )

    def handle(self, *args, **options):
        confirmar = options['confirmar']
        
        if not confirmar:
            self.stdout.write(
                self.style.WARNING(
                    '\n[ADVERTENCIA] Esta operacion eliminara TODOS los lotes y sus datos relacionados.\n'
                    'Esto incluye:\n'
                    '  - Todas las mermas relacionadas con lotes\n'
                    '  - Todos los movimientos de stock\n'
                    '  - Todos los detalles de produccion que usan lotes\n'
                    '  - Todos los detalles de venta que usan lotes\n'
                    '  - Todos los lotes\n\n'
                    'NOTA: Los insumos, recetas y otros datos NO se eliminaran.\n\n'
                    'Para confirmar, ejecuta el comando con --confirmar\n'
                )
            )
            return
        
        try:
            with transaction.atomic():
                # Contar registros antes de eliminar
                total_lotes = Lote.objects.count()
                total_mermas_lote = Merma.objects.filter(tipo_merma='lote', id_lote__isnull=False).count()
                total_movimientos = MovimientoStock.objects.count()
                total_detalles_produccion = DetalleProduccionInsumo.objects.count()
                total_detalles_venta = DetalleVentaIns.objects.count()
                
                self.stdout.write(f'\n[INFO] Registros a eliminar:')
                self.stdout.write(f'  - Lotes: {total_lotes}')
                self.stdout.write(f'  - Mermas de lotes: {total_mermas_lote}')
                self.stdout.write(f'  - Movimientos de stock: {total_movimientos}')
                self.stdout.write(f'  - Detalles de produccion: {total_detalles_produccion}')
                self.stdout.write(f'  - Detalles de venta: {total_detalles_venta}')
                
                # 1. Eliminar detalles de venta que usan lotes
                self.stdout.write('\n[PROCESO] Eliminando detalles de venta que usan lotes...')
                detalles_venta_eliminados = DetalleVentaIns.objects.all().delete()[0]
                self.stdout.write(self.style.SUCCESS(f'  [OK] Eliminados {detalles_venta_eliminados} detalles de venta'))
                
                # 2. Eliminar mermas relacionadas con lotes
                self.stdout.write('\n[PROCESO] Eliminando mermas de lotes...')
                mermas_eliminadas = Merma.objects.filter(tipo_merma='lote', id_lote__isnull=False).delete()[0]
                self.stdout.write(self.style.SUCCESS(f'  [OK] Eliminadas {mermas_eliminadas} mermas'))
                
                # 3. Eliminar movimientos de stock
                self.stdout.write('\n[PROCESO] Eliminando movimientos de stock...')
                movimientos_eliminados = MovimientoStock.objects.all().delete()[0]
                self.stdout.write(self.style.SUCCESS(f'  [OK] Eliminados {movimientos_eliminados} movimientos'))
                
                # 4. Eliminar detalles de producción que usan lotes
                self.stdout.write('\n[PROCESO] Eliminando detalles de produccion que usan lotes...')
                detalles_prod_eliminados = DetalleProduccionInsumo.objects.all().delete()[0]
                self.stdout.write(self.style.SUCCESS(f'  [OK] Eliminados {detalles_prod_eliminados} detalles'))
                
                # 5. Eliminar lotes
                self.stdout.write('\n[PROCESO] Eliminando lotes...')
                lotes_eliminados = Lote.objects.all().delete()[0]
                self.stdout.write(self.style.SUCCESS(f'  [OK] Eliminados {lotes_eliminados} lotes'))
                
                self.stdout.write(self.style.SUCCESS('\n[EXITO] Proceso completado exitosamente'))
                self.stdout.write(self.style.SUCCESS('\n[INFO] Los siguientes datos se mantuvieron intactos:'))
                self.stdout.write('  - Insumos')
                self.stdout.write('  - Recetas')
                self.stdout.write('  - Detalles de compra')
                self.stdout.write('  - Platos y platos producidos')
                self.stdout.write('  - Otros registros no relacionados con lotes')
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'\n[ERROR] Error al eliminar: {str(e)}')
            )
            raise

