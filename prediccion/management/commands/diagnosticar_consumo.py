"""
Comando para diagnosticar por qué no hay proyecciones de compras
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta, date
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from inventario.models import (
    Insumo, DetalleProduccionInsumo, 
    Lote, PlatoProducido
)


class Command(BaseCommand):
    help = 'Diagnostica por qué no hay proyecciones de compras'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n=== DIAGNOSTICO DE CONSUMO PARA ML ===\n'))
        
        # 1. Verificar registros de DetalleProduccionInsumo
        total_consumos = DetalleProduccionInsumo.objects.count()
        self.stdout.write(f'[INFO] Total de registros DetalleProduccionInsumo: {total_consumos}')
        
        if total_consumos == 0:
            self.stdout.write(self.style.ERROR(
                '\n[ERROR] PROBLEMA: No hay registros de DetalleProduccionInsumo.\n'
                '   Esto significa que aunque hayas producido platos, no se están creando\n'
                '   los registros de consumo. Verifica que al producir platos se estén\n'
                '   creando correctamente los DetalleProduccionInsumo.'
            ))
            return
        
        # 2. Verificar fechas únicas
        hoy = date.today()
        fecha_inicio_180 = hoy - timedelta(days=180)
        fecha_inicio_180_dt = datetime.combine(fecha_inicio_180, datetime.min.time())
        fecha_inicio_180_dt = timezone.make_aware(fecha_inicio_180_dt)
        
        consumos_recientes = DetalleProduccionInsumo.objects.filter(
            fecha_uso__gte=fecha_inicio_180_dt
        )
        
        # Obtener fechas únicas
        fechas_unicas = consumos_recientes.values_list('fecha_uso__date', flat=True).distinct()
        num_dias_unicos = len(fechas_unicas)
        
        self.stdout.write(f'\n[INFO] Dias unicos con consumo (ultimos 180 dias): {num_dias_unicos}')
        
        if num_dias_unicos < 20:
            self.stdout.write(self.style.ERROR(
                f'\n[ERROR] PROBLEMA PRINCIPAL: Solo tienes {num_dias_unicos} dias unicos con datos.\n'
                f'   El ML necesita MINIMO 20 dias unicos con consumo.\n'
                f'   Te faltan {20 - num_dias_unicos} dias mas.\n'
            ))
            
            # Mostrar las fechas que tienen datos
            if num_dias_unicos > 0:
                self.stdout.write('\n[INFO] Fechas con datos:')
                fechas_ordenadas = sorted(fechas_unicas)
                for fecha in fechas_ordenadas[:10]:  # Mostrar las primeras 10
                    count = consumos_recientes.filter(fecha_uso__date=fecha).count()
                    self.stdout.write(f'   - {fecha}: {count} registros')
                if len(fechas_ordenadas) > 10:
                    self.stdout.write(f'   ... y {len(fechas_ordenadas) - 10} fechas mas')
        else:
            self.stdout.write(self.style.SUCCESS(
                f'\n[OK] Tienes suficientes dias unicos ({num_dias_unicos} dias)'
            ))
        
        # 3. Verificar por insumo
        self.stdout.write(f'\n[INFO] CONSUMO POR INSUMO (ultimos 180 dias):')
        # Contar días únicos correctamente usando TruncDate
        insumos_con_consumo = consumos_recientes.annotate(
            fecha_dia=TruncDate('fecha_uso')
        ).values(
            'id_insumo__id_insumo', 
            'id_insumo__nombre_insumo'
        ).annotate(
            total_registros=Count('id_detalle_produccion'),
            total_consumido=Sum('cantidad_usada'),
            dias_unicos=Count('fecha_dia', distinct=True)
        ).order_by('-total_registros')
        
        insumos_suficientes = 0
        insumos_insuficientes = 0
        
        for item in insumos_con_consumo[:10]:  # Mostrar los primeros 10
            dias_unicos_insumo = item['dias_unicos']
            if dias_unicos_insumo >= 20:
                insumos_suficientes += 1
                status = '[OK]'
            else:
                insumos_insuficientes += 1
                status = '[!]'
            
            self.stdout.write(
                f'   {status} {item["id_insumo__nombre_insumo"]}: '
                f'{item["total_registros"]} registros, '
                f'{item["dias_unicos"]} dias unicos, '
                f'{item["total_consumido"]:.2f} unidades consumidas'
            )
        
        if len(insumos_con_consumo) > 10:
            self.stdout.write(f'   ... y {len(insumos_con_consumo) - 10} insumos mas')
        
        # 4. Resumen
        self.stdout.write(f'\n[INFO] RESUMEN:')
        self.stdout.write(f'   - Insumos con suficientes datos (>=20 dias): {insumos_suficientes}')
        self.stdout.write(f'   - Insumos con datos insuficientes (<20 dias): {insumos_insuficientes}')
        
        # 5. Recomendaciones
        if num_dias_unicos < 20:
            self.stdout.write(self.style.WARNING(
                f'\n[RECOMENDACION]:\n'
                f'   Necesitas producir platos en {20 - num_dias_unicos} dias mas.\n'
                f'   Puedes:\n'
                f'   1. Producir platos cada dia durante las proximas semanas\n'
                f'   2. O usar el comando para generar datos historicos de prueba:\n'
                f'      python manage.py generar_datos_consumo --dias 90'
            ))
        
        self.stdout.write('\n')

