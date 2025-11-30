# BACKUP - Modelos anteriores (antes de corregir según cocinAI.sql)
from django.db import models
from django.contrib.auth.models import User

# Create your models here.

class CategoriaProducto(models.Model):
    """Categorías para clasificar los productos (ej: Verduras, Carnes, Lácteos, etc.)"""
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True, null=True)
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Categoría de Producto"
        verbose_name_plural = "Categorías de Productos"
        ordering = ['nombre']
    
    def __str__(self):
        return self.nombre

class UnidadMedida(models.Model):
    """Unidades de medida para los productos (ej: kg, gr, lt, unidades, etc.)"""
    nombre = models.CharField(max_length=50, unique=True)
    abreviacion = models.CharField(max_length=10, unique=True)
    activo = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Unidad de Medida"
        verbose_name_plural = "Unidades de Medida"
        ordering = ['nombre']
    
    def __str__(self):
        return f"{self.nombre} ({self.abreviacion})"

class Producto(models.Model):
    """Maestro de productos/insumos del restaurante"""
    codigo = models.CharField(max_length=20, unique=True, help_text="Código único del producto")
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True, null=True)
    categoria = models.ForeignKey(CategoriaProducto, on_delete=models.PROTECT, related_name='productos')
    unidad_medida = models.ForeignKey(UnidadMedida, on_delete=models.PROTECT, related_name='productos')
    
    # Información de almacenamiento
    temperatura_almacenamiento = models.CharField(
        max_length=50, 
        choices=[
            ('AMBIENTE', 'Ambiente'),
            ('REFRIGERADO', 'Refrigerado (2-8°C)'),
            ('CONGELADO', 'Congelado (-18°C)'),
        ],
        default='REFRIGERADO',
        help_text="Tipo de almacenamiento requerido"
    )
    
    # Información de caducidad
    dias_caducidad = models.PositiveIntegerField(
        default=7,
        help_text="Días de caducidad por defecto para este producto"
    )
    
    # Información de compra
    precio_referencia = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Precio de referencia para compras"
    )
    
    # Control de estado
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    usuario_creacion = models.ForeignKey(User, on_delete=models.PROTECT, related_name='productos_creados')
    
    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"
        ordering = ['categoria', 'nombre']
        indexes = [
            models.Index(fields=['codigo']),
            models.Index(fields=['categoria', 'activo']),
        ]
    
    def __str__(self):
        return f"{self.codigo} - {self.nombre}"
    
    @property
    def nombre_completo(self):
        return f"{self.codigo} - {self.nombre} ({self.unidad_medida.abreviacion})"










