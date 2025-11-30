from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from inventario.models import Usuario, PlatoProducido, Plato

# Create your models here.

class Mesa(models.Model):
    """Tabla MESA - Mesas del restaurante"""
    id_mesa = models.AutoField(primary_key=True)
    numero_mesa = models.CharField(max_length=10, unique=True, verbose_name="Número de Mesa")
    capacidad = models.IntegerField(default=4, verbose_name="Capacidad")
    estado = models.CharField(
        max_length=20,
        choices=[
            ('disponible', 'Disponible'),
            ('ocupada', 'Ocupada'),
            ('reservada', 'Reservada'),
            ('mantenimiento', 'En Mantenimiento'),
        ],
        default='disponible',
        verbose_name="Estado"
    )
    ubicacion = models.CharField(max_length=100, blank=True, null=True, verbose_name="Ubicación")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    activa = models.BooleanField(default=True, verbose_name="Activa")
    
    class Meta:
        db_table = 'MESA'
        verbose_name = "Mesa"
        verbose_name_plural = "Mesas"
        ordering = ['numero_mesa']
    
    def __str__(self):
        return f"Mesa {self.numero_mesa} ({self.get_estado_display()})"


class MovimientoMesa(models.Model):
    """Tabla MOVIMIENTO_MESA - Registro de movimientos de platos de cocina a mesa"""
    id_movimiento_mesa = models.AutoField(primary_key=True)
    id_plato_producido = models.ForeignKey(
        PlatoProducido,
        on_delete=models.RESTRICT,
        db_column='id_plato_producido',
        verbose_name="Plato Producido",
        related_name='movimientos_mesa'
    )
    id_ubicacion = models.ForeignKey(
        'inventario.Ubicacion',
        on_delete=models.RESTRICT,
        db_column='id_ubicacion',
        verbose_name="Ubicación (Mesa)"
    )
    numero_mesa = models.CharField(max_length=50, blank=True, null=True, verbose_name="Número de Mesa")
    id_usuario = models.ForeignKey(
        Usuario,
        on_delete=models.RESTRICT,
        db_column='id_usuario',
        verbose_name="Usuario"
    )
    fecha_movimiento = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Movimiento")
    observaciones = models.TextField(blank=True, null=True, verbose_name="Observaciones")
    
    class Meta:
        db_table = 'MOVIMIENTO_MESA'
        verbose_name = "Movimiento a Mesa"
        verbose_name_plural = "Movimientos a Mesas"
        ordering = ['-fecha_movimiento']
    
    def __str__(self):
        mesa_info = f"Mesa {self.numero_mesa}" if self.numero_mesa else self.id_ubicacion.nombre_ubicacion
        return f"{self.id_plato_producido.id_plato.nombre_plato} → {mesa_info} ({self.fecha_movimiento.strftime('%Y-%m-%d %H:%M')})"


class Comanda(models.Model):
    """Tabla COMANDA - Comandas de pedidos de mesas"""
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('en_preparacion', 'En Preparación'),
        ('parcialmente_lista', 'Parcialmente Lista'),
        ('lista', 'Lista'),
        ('entregada', 'Entregada'),
        ('cancelada', 'Cancelada'),
    ]
    
    id_comanda = models.AutoField(primary_key=True)
    id_mesa = models.ForeignKey(
        Mesa,
        on_delete=models.RESTRICT,
        db_column='id_mesa',
        verbose_name="Mesa",
        related_name='comandas'
    )
    id_usuario = models.ForeignKey(
        Usuario,
        on_delete=models.RESTRICT,
        db_column='id_usuario',
        verbose_name="Usuario (Garzón)",
        related_name='comandas_creadas'
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='pendiente',
        verbose_name="Estado"
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Fecha de Actualización")
    observaciones = models.TextField(blank=True, null=True, verbose_name="Observaciones")
    
    class Meta:
        db_table = 'COMANDA'
        verbose_name = "Comanda"
        verbose_name_plural = "Comandas"
        ordering = ['-fecha_creacion']
    
    def __str__(self):
        return f"Comanda #{self.id_comanda} - Mesa {self.id_mesa.numero_mesa} ({self.get_estado_display()})"
    
    def actualizar_estado(self):
        """Actualiza el estado de la comanda basado en los detalles"""
        detalles = self.detalles.all()
        if not detalles.exists():
            self.estado = 'pendiente'
            self.save()
            return
        
        estados_detalles = [detalle.estado for detalle in detalles]
        
        if all(estado == 'entregado' for estado in estados_detalles):
            self.estado = 'entregada'
        elif all(estado in ['listo', 'entregado'] for estado in estados_detalles):
            self.estado = 'lista'
        elif any(estado == 'listo' for estado in estados_detalles):
            self.estado = 'parcialmente_lista'
        elif any(estado == 'en_preparacion' for estado in estados_detalles):
            self.estado = 'en_preparacion'
        else:
            self.estado = 'pendiente'
        
        self.save()


class DetalleComanda(models.Model):
    """Tabla DETALLE_COMANDA - Detalles de platos en una comanda"""
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('en_preparacion', 'En Preparación'),
        ('listo', 'Listo'),
        ('entregado', 'Entregado'),
        ('cancelado', 'Cancelado'),
    ]
    
    id_detalle_comanda = models.AutoField(primary_key=True)
    id_comanda = models.ForeignKey(
        Comanda,
        on_delete=models.CASCADE,
        db_column='id_comanda',
        verbose_name="Comanda",
        related_name='detalles'
    )
    id_plato = models.ForeignKey(
        Plato,
        on_delete=models.RESTRICT,
        db_column='id_plato',
        verbose_name="Plato"
    )
    cantidad = models.IntegerField(default=1, verbose_name="Cantidad")
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='pendiente',
        verbose_name="Estado"
    )
    observaciones = models.TextField(blank=True, null=True, verbose_name="Observaciones")
    id_plato_producido = models.ForeignKey(
        PlatoProducido,
        on_delete=models.SET_NULL,
        db_column='id_plato_producido',
        verbose_name="Plato Producido",
        null=True,
        blank=True,
        related_name='detalles_comanda'
    )
    
    class Meta:
        db_table = 'DETALLE_COMANDA'
        verbose_name = "Detalle de Comanda"
        verbose_name_plural = "Detalles de Comanda"
        ordering = ['id_comanda', 'id_plato']
    
    def __str__(self):
        return f"{self.id_comanda} - {self.id_plato.nombre_plato} x{self.cantidad} ({self.get_estado_display()})"
