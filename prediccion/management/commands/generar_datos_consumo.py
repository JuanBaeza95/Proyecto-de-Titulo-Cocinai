"""
Comando para generar datos históricos de consumo de insumos para ML
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta, date
from inventario.models import (
    Insumo, Plato, DetalleProduccionInsumo, 
    PlatoProducido, Receta, Ubicacion, Lote
)
from django.contrib.auth.models import User
import random


class Command(BaseCommand):
    help = 'Genera datos historicos de consumo de insumos para ML'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dias',
            type=int,
            default=90,
            help='Numero de dias de datos historicos a generar'
        )

    def handle(self, *args, **options):
        dias = options['dias']
        
        insumos = Insumo.objects.all()
        platos = Plato.objects.all()
        
        if not insumos.exists():
            self.stdout.write(self.style.ERROR('No hay insumos en el sistema'))
            return
        
        if not platos.exists():
            self.stdout.write(self.style.ERROR('No hay platos en el sistema'))
            return
        
        # Obtener ubicación y usuario por defecto
        try:
            ubicacion = Ubicacion.objects.first()
            if not ubicacion:
                self.stdout.write(self.style.ERROR('No hay ubicaciones en el sistema'))
                return
        except:
            self.stdout.write(self.style.ERROR('Error al obtener ubicacion'))
            return
        
        try:
            usuario = User.objects.first()
            if not usuario:
                self.stdout.write(self.style.ERROR('No hay usuarios en el sistema'))
                return
        except:
            self.stdout.write(self.style.ERROR('Error al obtener usuario'))
            return
        
        hoy = date.today()
        fecha_inicio = hoy - timedelta(days=dias)
        consumos_creados = 0
        platos_creados = 0
        
        self.stdout.write(f'Generando datos para {dias} dias...')
        self.stdout.write(f'Fecha inicio: {fecha_inicio}')
        self.stdout.write(f'Fecha fin: {hoy}')
        
        # Estrategia: Asegurar que cada insumo se use en al menos 20 días
        # Producir TODOS los platos cada día para maximizar el uso de insumos
        for dia in range(dias):
            fecha_actual = fecha_inicio + timedelta(days=dia)
            fecha_dt = datetime.combine(fecha_actual, datetime.min.time())
            fecha_dt = timezone.make_aware(fecha_dt)
            
            # Producir TODOS los platos que tengan recetas para maximizar uso de insumos
            platos_con_receta = [p for p in platos if Receta.objects.filter(id_plato=p).exists()]
            
            # Producir cada plato 1-3 veces por día para tener variabilidad
            for plato in platos_con_receta:
                veces_producir = random.randint(1, 3)
                
                for _ in range(veces_producir):
                
                    try:
                        # Receta es directamente la relación plato-insumo
                        recetas = Receta.objects.filter(id_plato=plato)
                        
                        if not recetas.exists():
                            continue
                        
                        # Crear plato producido
                        plato_producido = PlatoProducido.objects.create(
                            estado='venta',
                            fecha_produccion=fecha_dt,
                            fecha_entrega=fecha_dt + timedelta(hours=1),
                            id_plato=plato,
                            id_ubicacion=ubicacion,
                            id_usuario=usuario
                        )
                        platos_creados += 1
                        
                        # Crear consumo de insumos según la receta
                        for receta in recetas:
                            cantidad = float(receta.cantidad_necesaria)
                            # Variar la cantidad ligeramente para simular variabilidad real
                            cantidad_variada = cantidad * random.uniform(0.9, 1.1)
                            
                            # Necesitamos un lote para el DetalleProduccionInsumo
                            # Buscar un lote existente del insumo
                            lote = None
                            try:
                                lote = Lote.objects.filter(
                                    id_insumo=receta.id_insumo,
                                    cantidad_actual__gt=0
                                ).first()
                            except:
                                pass
                            
                            # Si no hay lote, intentar crear uno temporal
                            if not lote:
                                try:
                                    from inventario.models import DetalleCompra
                                    detalle_compra = DetalleCompra.objects.first()
                                    if detalle_compra:
                                        lote = Lote.objects.create(
                                            id_detalle_compra=detalle_compra,
                                            id_insumo=receta.id_insumo,
                                            id_ubicacion=ubicacion,
                                            costo_unitario=1000,
                                            fecha_vencimiento=hoy + timedelta(days=30),
                                            fecha_ingreso=fecha_actual,
                                            cantidad_actual=1000,
                                            numero_lote=f'TEMP-{receta.id_insumo.id_insumo}-{dia}'
                                        )
                                except Exception as e:
                                    self.stdout.write(
                                        self.style.WARNING(
                                            f'No se pudo crear lote para {receta.id_insumo.nombre_insumo}: {e}'
                                        )
                                    )
                                    continue
                            
                            if lote:
                                DetalleProduccionInsumo.objects.create(
                                    id_plato_producido=plato_producido,
                                    id_lote=lote,
                                    id_insumo=receta.id_insumo,
                                    cantidad_usada=cantidad_variada,
                                    fecha_uso=fecha_dt
                                )
                                consumos_creados += 1
                            
                    except Exception as e:
                        self.stdout.write(
                            self.style.WARNING(f'Error al procesar plato {plato.nombre_plato}: {e}')
                        )
                        continue
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n[OK] Se crearon {consumos_creados} registros de consumo para {dias} dias'
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f'[OK] Se crearon {platos_creados} platos producidos'
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f'\nAhora ejecuta: python manage.py diagnosticar_consumo'
                f' para verificar que cada insumo tenga suficientes dias unicos'
            )
        )

