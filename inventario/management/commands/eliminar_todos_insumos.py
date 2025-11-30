"""
Comando de Django para eliminar todos los insumos de la base de datos
ADVERTENCIA: Esta operación es destructiva y eliminará todos los datos relacionados
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from inventario.models import (
    Insumo, Lote, DetalleCompra, DetalleProduccionInsumo, 
    Receta, MovimientoStock, Merma
)
from django.db.models import Q


class Command(BaseCommand):
    help = 'Elimina todos los insumos de la base de datos y sus datos relacionados'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirmar',
            action='store_true',
            help='Confirma que realmente quieres eliminar todos los insumos',
        )
        parser.add_argument(
            '--solo-vaciar',
            action='store_true',
            help='Solo elimina los datos relacionados pero mantiene los insumos vacíos',
        )

    def handle(self, *args, **options):
        confirmar = options['confirmar']
        solo_vaciar = options['solo_vaciar']
        
        if not confirmar:
            self.stdout.write(
                self.style.WARNING(
                    '\n[ADVERTENCIA] Esta operacion eliminara TODOS los insumos y sus datos relacionados.\n'
                    'Esto incluye:\n'
                    '  - Todos los lotes\n'
                    '  - Todos los detalles de compra\n'
                    '  - Todos los detalles de produccion\n'
                    '  - Todas las recetas\n'
                    '  - Todos los movimientos de stock\n'
                    '  - Todas las mermas relacionadas con lotes\n\n'
                    'Para confirmar, ejecuta el comando con --confirmar\n'
                )
            )
            return
        
        try:
            with transaction.atomic():
                # Contar registros antes de eliminar
                total_insumos = Insumo.objects.count()
                total_lotes = Lote.objects.count()
                total_detalles_compra = DetalleCompra.objects.count()
                total_detalles_produccion = DetalleProduccionInsumo.objects.count()
                total_recetas = Receta.objects.count()
                total_movimientos = MovimientoStock.objects.count()
                total_mermas_lote = Merma.objects.filter(tipo_merma='lote', id_lote__isnull=False).count()
                
                self.stdout.write(f'\n[INFO] Registros a eliminar:')
                self.stdout.write(f'  - Insumos: {total_insumos}')
                self.stdout.write(f'  - Lotes: {total_lotes}')
                self.stdout.write(f'  - Detalles de compra: {total_detalles_compra}')
                self.stdout.write(f'  - Detalles de produccion: {total_detalles_produccion}')
                self.stdout.write(f'  - Recetas: {total_recetas}')
                self.stdout.write(f'  - Movimientos de stock: {total_movimientos}')
                self.stdout.write(f'  - Mermas de lotes: {total_mermas_lote}')
                
                if solo_vaciar:
                    self.stdout.write(self.style.WARNING('\n[ADVERTENCIA] Modo: Solo vaciar datos relacionados (mantener insumos)'))
                else:
                    self.stdout.write(self.style.WARNING('\n[ADVERTENCIA] Modo: Eliminar todo (incluyendo insumos)'))
                
                # 1. Eliminar mermas relacionadas con lotes
                self.stdout.write('\n[PROCESO] Eliminando mermas de lotes...')
                mermas_eliminadas = Merma.objects.filter(tipo_merma='lote', id_lote__isnull=False).delete()[0]
                self.stdout.write(self.style.SUCCESS(f'  [OK] Eliminadas {mermas_eliminadas} mermas'))
                
                # 2. Eliminar movimientos de stock
                self.stdout.write('\n[PROCESO] Eliminando movimientos de stock...')
                movimientos_eliminados = MovimientoStock.objects.all().delete()[0]
                self.stdout.write(self.style.SUCCESS(f'  [OK] Eliminados {movimientos_eliminados} movimientos'))
                
                # 3. Eliminar detalles de producción
                self.stdout.write('\n[PROCESO] Eliminando detalles de produccion...')
                detalles_prod_eliminados = DetalleProduccionInsumo.objects.all().delete()[0]
                self.stdout.write(self.style.SUCCESS(f'  [OK] Eliminados {detalles_prod_eliminados} detalles'))
                
                # 4. Eliminar recetas
                self.stdout.write('\n[PROCESO] Eliminando recetas...')
                recetas_eliminadas = Receta.objects.all().delete()[0]
                self.stdout.write(self.style.SUCCESS(f'  [OK] Eliminadas {recetas_eliminadas} recetas'))
                
                # 5. Eliminar lotes
                self.stdout.write('\n[PROCESO] Eliminando lotes...')
                lotes_eliminados = Lote.objects.all().delete()[0]
                self.stdout.write(self.style.SUCCESS(f'  [OK] Eliminados {lotes_eliminados} lotes'))
                
                # 6. Eliminar detalles de compra
                self.stdout.write('\n[PROCESO] Eliminando detalles de compra...')
                detalles_compra_eliminados = DetalleCompra.objects.all().delete()[0]
                self.stdout.write(self.style.SUCCESS(f'  [OK] Eliminados {detalles_compra_eliminados} detalles'))
                
                # 7. Eliminar insumos (si no es modo solo-vaciar)
                if not solo_vaciar:
                    self.stdout.write('\n[PROCESO] Eliminando insumos...')
                    insumos_eliminados = Insumo.objects.all().delete()[0]
                    self.stdout.write(self.style.SUCCESS(f'  [OK] Eliminados {insumos_eliminados} insumos'))
                else:
                    self.stdout.write(self.style.SUCCESS('\n[OK] Insumos mantenidos (solo se vaciaron datos relacionados)'))
                
                self.stdout.write(self.style.SUCCESS('\n[EXITO] Proceso completado exitosamente'))
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'\n[ERROR] Error al eliminar: {str(e)}')
            )
            raise

