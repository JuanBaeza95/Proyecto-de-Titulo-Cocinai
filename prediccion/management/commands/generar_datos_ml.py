import random
from datetime import date, timedelta, datetime
from django.core.management.base import BaseCommand
from inventario.models import Plato, PlatoProducido, Ubicacion
from django.contrib.auth.models import User
from django.utils import timezone

class Command(BaseCommand):
    help = 'Genera datos sintéticos de ventas históricas para entrenar el modelo ML (mínimo 365 días)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dias',
            type=int,
            default=365,
            help='Número de días de historia a generar (default: 365, mínimo recomendado: 180)'
        )
        parser.add_argument(
            '--ventas-min',
            type=int,
            default=3,
            help='Ventas mínimas por día por plato (default: 3)'
        )
        parser.add_argument(
            '--ventas-max',
            type=int,
            default=15,
            help='Ventas máximas por día por plato (default: 15)'
        )

    def handle(self, *args, **options):
        dias = options['dias']
        ventas_min = options['ventas_min']
        ventas_max = options['ventas_max']
        
        if dias < 30:
            self.stdout.write(self.style.WARNING(f'Advertencia: {dias} días es muy poco. Se recomienda al menos 180 días para ML.'))
        
        self.stdout.write(f'Generando datos históricos ({dias} días)...')
        
        # Verificar que existan los datos necesarios
        platos = Plato.objects.all()
        if not platos.exists():
            self.stdout.write(self.style.ERROR('No hay platos creados. Crea platos primero.'))
            return
        
        # Obtener o crear ubicación
        ubicacion = Ubicacion.objects.filter(tipo_ubicacion='cocina').first()
        if not ubicacion:
            ubicacion = Ubicacion.objects.first()
        if not ubicacion:
            self.stdout.write(self.style.ERROR('No hay ubicaciones creadas. Crea una ubicación primero.'))
            return
        
        # Obtener usuario (usar el primero disponible o crear uno si no existe)
        usuario = User.objects.first()
        if not usuario:
            self.stdout.write(self.style.ERROR('No hay usuarios en el sistema. Crea un usuario primero.'))
            return
        
        # Configuración de fechas
        fecha_fin = timezone.now().date()
        fecha_inicio = fecha_fin - timedelta(days=dias)
        
        total_creados = 0
        fecha_actual = fecha_inicio
        
        self.stdout.write(f'Rango de fechas: {fecha_inicio} a {fecha_fin}')
        self.stdout.write(f'Platos a procesar: {platos.count()}')
        self.stdout.write('')

        while fecha_actual <= fecha_fin:
            dia_semana = fecha_actual.weekday()  # 0=Lunes, 6=Domingo
            es_fin_semana = dia_semana >= 5  # Sábado (5) y Domingo (6)
            es_viernes = dia_semana == 4
            
            # Patrones de ventas más realistas:
            # - Lunes a Jueves: base normal
            # - Viernes: +30% (inicio de fin de semana)
            # - Sábado: +50% (día más ocupado)
            # - Domingo: +20% (día medio)
            
            for plato in platos:
                # Base de ventas diarias
                cantidad_base = random.randint(ventas_min, ventas_max)
                
                # Ajustes según día de la semana
                if es_fin_semana:
                    if dia_semana == 5:  # Sábado
                        cantidad_base = int(cantidad_base * 1.5)
                    elif dia_semana == 6:  # Domingo
                        cantidad_base = int(cantidad_base * 1.2)
                elif es_viernes:
                    cantidad_base = int(cantidad_base * 1.3)
                
                # Variación aleatoria adicional (±20%)
                variacion = random.uniform(0.8, 1.2)
                cantidad_base = max(1, int(cantidad_base * variacion))
                
                # Simular ventas individuales a lo largo del día
                for _ in range(cantidad_base):
                    # Hora aleatoria entre 12:00 y 22:00 (horario de restaurante)
                    hora = random.randint(12, 22)
                    minuto = random.randint(0, 59)
                    segundo = random.randint(0, 59)
                    
                    # Crear datetime con la fecha y hora
                    fecha_venta = timezone.make_aware(
                        datetime.combine(fecha_actual, datetime.min.time().replace(hour=hora, minute=minuto, second=segundo))
                    )
                    
                    # Crear el plato producido
                    plato_producido = PlatoProducido.objects.create(
                        id_plato=plato,
                        id_ubicacion=ubicacion,
                        id_usuario=usuario,
                        estado='venta'
                    )
                    
                    # Actualizar fecha_produccion manualmente (porque tiene auto_now_add=True)
                    PlatoProducido.objects.filter(id_plato_producido=plato_producido.id_plato_producido).update(
                        fecha_produccion=fecha_venta
                    )
                    plato_producido.refresh_from_db()
                    
                    total_creados += 1
            
            # Mostrar progreso cada 30 días
            if (fecha_actual - fecha_inicio).days % 30 == 0:
                progreso = ((fecha_actual - fecha_inicio).days / dias) * 100
                self.stdout.write(f'Progreso: {progreso:.1f}% - Fecha: {fecha_actual} - Total creados: {total_creados}', ending='\r')
            
            fecha_actual += timedelta(days=1)

        self.stdout.write('')  # Nueva línea después del progreso
        self.stdout.write(self.style.SUCCESS(
            f'\n[OK] ¡Listo! Se generaron {total_creados} registros de ventas.\n'
            f'   - Periodo: {fecha_inicio} a {fecha_fin} ({dias} dias)\n'
            f'   - Promedio: {total_creados / dias:.1f} ventas/dia\n'
            f'   - Promedio por plato: {total_creados / (dias * platos.count()):.1f} ventas/dia/plato'
        ))
        
        self.stdout.write(self.style.WARNING(
            '\n[IMPORTANTE] Ahora puedes entrenar el modelo con estos datos.\n'
            '   Ejecuta: python manage.py shell\n'
            '   Luego: from prediccion.ml_models import entrenar_modelo_ventas\n'
            '   Luego: resultado = entrenar_modelo_ventas(dias_historia=365)\n'
            '   O usa la vista web: /prediccion/reentrenar-modelo/'
        ))

