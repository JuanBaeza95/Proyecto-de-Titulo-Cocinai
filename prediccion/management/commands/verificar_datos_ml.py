"""
Comando para verificar qué datos tiene el sistema para Machine Learning
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta, date
from django.db.models import Sum, Count
from inventario.models import (
    Insumo, Plato, DetalleProduccionInsumo, 
    Lote, Receta, DetalleReceta, PlatoProducido
)


class Command(BaseCommand):
    help = 'Verifica qué datos tiene el sistema para Machine Learning'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n=== VERIFICACIÓN DE DATOS PARA ML ===\n'))
        
        # 1. Verificar insumos
        total_insumos = Insumo.objects.count()
        self.stdout.write(f'✓ Insumos en el sistema: {total_insumos}')
        
        # 2. Verificar platos
        total_platos = Plato.objects.count()
        self.stdout.write(f'✓ Platos en el sistema: {total_platos}')
        
        # 3. Verificar recetas
        total_recetas = Receta.objects.count()
        platos_sin_receta = Plato.objects.exclude(
            id_plato__in=Receta.objects.values_list('id_plato_id', flat=True)
        ).count()
        self.stdout.write(f'✓ Recetas en el sistema: {total_recetas}')
        if platos_sin_receta > 0:
            self.stdout.write(self.style.WARNING(f'  ⚠️  {platos_sin_receta} platos SIN receta'))
        
        # 4. Verificar lotes con stock
        lotes_con_stock = Lote.objects.filter(cantidad_actual__gt=0).count()
        total_lotes = Lote.objects.count()
        self.stdout.write(f'✓ Lotes con stock: {lotes_con_stock} de {total_lotes} totales')
        
        # 5. Verificar consumo histórico (LO MÁS IMPORTANTE)
        hoy = date.today()
        fecha_inicio_180 = hoy - timedelta(days=180)
        fecha_inicio_30 = hoy - timedelta(days=30)
        fecha_inicio_7 = hoy - timedelta(days=7)
        
        fecha_inicio_180_dt = datetime.combine(fecha_inicio_180, datetime.min.time())
        fecha_inicio_180_dt = timezone.make_aware(fecha_inicio_180_dt)
        
        fecha_inicio_30_dt = datetime.combine(fecha_inicio_30, datetime.min.time())
        fecha_inicio_30_dt = timezone.make_aware(fecha_inicio_30_dt)
        
        fecha_inicio_7_dt = datetime.combine(fecha_inicio_7, datetime.min.time())
        fecha_inicio_7_dt = timezone.make_aware(fecha_inicio_7_dt)
        
        consumos_180 = DetalleProduccionInsumo.objects.filter(
            fecha_uso__gte=fecha_inicio_180_dt
        ).count()
        
        consumos_30 = DetalleProduccionInsumo.objects.filter(
            fecha_uso__gte=fecha_inicio_30_dt
        ).count()
        
        consumos_7 = DetalleProduccionInsumo.objects.filter(
            fecha_uso__gte=fecha_inicio_7_dt
        ).count()
        
        total_consumos = DetalleProduccionInsumo.objects.count()
        
        self.stdout.write(f'\n📊 REGISTROS DE CONSUMO (DetalleProduccionInsumo):')
        self.stdout.write(f'  • Total en el sistema: {total_consumos}')
        self.stdout.write(f'  • Últimos 180 días: {consumos_180}')
        self.stdout.write(f'  • Últimos 30 días: {consumos_30}')
        self.stdout.write(f'  • Últimos 7 días: {consumos_7}')
        
        # Verificar días únicos con datos
        fechas_unicas = DetalleProduccionInsumo.objects.filter(
            fecha_uso__gte=fecha_inicio_180_dt
        ).values_list('fecha_uso__date', flat=True).distinct().count()
        
        self.stdout.write(f'  • Días únicos con datos (últimos 180 días): {fechas_unicas}')
        
        # 6. Verificar consumo por insumo
        self.stdout.write(f'\n📦 CONSUMO POR INSUMO (últimos 180 días):')
        insumos_con_consumo = DetalleProduccionInsumo.objects.filter(
            fecha_uso__gte=fecha_inicio_180_dt
        ).values('id_insumo__nombre_insumo', 'id_insumo__id_insumo').annotate(
            total_consumo=Sum('cantidad_usada'),
            num_registros=Count('id_detalle_produccion')
        ).order_by('-total_consumo')[:10]
        
        if insumos_con_consumo:
            for item in insumos_con_consumo:
                self.stdout.write(
                    f'  • {item["id_insumo__nombre_insumo"]}: '
                    f'{item["num_registros"]} registros, '
                    f'{item["total_consumo"]:.2f} unidades consumidas'
                )
        else:
            self.stdout.write(self.style.ERROR('  ❌ NO HAY DATOS DE CONSUMO'))
        
        # 7. Verificar platos producidos
        platos_producidos_total = PlatoProducido.objects.count()
        platos_producidos_180 = PlatoProducido.objects.filter(
            fecha_produccion__gte=fecha_inicio_180_dt
        ).count()
        
        self.stdout.write(f'\n🍽️  PLATOS PRODUCIDOS:')
        self.stdout.write(f'  • Total: {platos_producidos_total}')
        self.stdout.write(f'  • Últimos 180 días: {platos_producidos_180}')
        
        # 8. Diagnóstico
        self.stdout.write(f'\n🔍 DIAGNÓSTICO:')
        
        problemas = []
        if total_insumos == 0:
            problemas.append('No hay insumos en el sistema')
        if total_platos == 0:
            problemas.append('No hay platos en el sistema')
        if total_recetas == 0:
            problemas.append('No hay recetas en el sistema')
        if lotes_con_stock == 0:
            problemas.append('No hay lotes con stock')
        if consumos_180 < 20:
            problemas.append(f'Solo hay {consumos_180} registros de consumo (mínimo 20)')
        if fechas_unicas < 20:
            problemas.append(f'Solo hay {fechas_unicas} días únicos con datos (mínimo 20 días)')
        
        if problemas:
            self.stdout.write(self.style.ERROR('\n❌ PROBLEMAS ENCONTRADOS:'))
            for problema in problemas:
                self.stdout.write(self.style.ERROR(f'  • {problema}'))
            
            self.stdout.write(self.style.WARNING('\n💡 SOLUCIÓN:'))
            if consumos_180 < 20 or fechas_unicas < 20:
                self.stdout.write(
                    '  El sistema necesita datos de CONSUMO de insumos, no solo compras.\n'
                    '  Los datos de consumo se generan cuando:\n'
                    '  1. Produces platos en el sistema\n'
                    '  2. El sistema registra automáticamente el consumo según las recetas\n\n'
                    '  Para generar datos de prueba, ejecuta:\n'
                    '  python manage.py generar_datos_consumo --dias 90'
                )
        else:
            self.stdout.write(self.style.SUCCESS('\n✅ El sistema tiene suficientes datos para ML'))
        
        self.stdout.write('\n')

