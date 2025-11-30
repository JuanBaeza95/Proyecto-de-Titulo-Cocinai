from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

# Create your models here.

class CategoriaProducto(models.Model):
    """Tabla CATEGORIA_PRODUCTO - Categorías de productos"""
    id_categoria = models.AutoField(primary_key=True)
    nombre_categoria = models.CharField(max_length=100, verbose_name="Nombre de la Categoría")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción")
    
    class Meta:
        db_table = 'CATEGORIA_PRODUCTO'
        verbose_name = "Categoría de Producto"
        verbose_name_plural = "Categorías de Productos"
        ordering = ['nombre_categoria']
    
    def __str__(self):
        return self.nombre_categoria

class UnidadMedida(models.Model):
    """Tabla UNIDAD_MEDIDA - Unidades de medida"""
    id_unidad = models.AutoField(primary_key=True)
    nombre_unidad = models.CharField(max_length=50, verbose_name="Nombre de la Unidad")
    abreviatura = models.CharField(max_length=10, verbose_name="Abreviatura")
    
    class Meta:
        db_table = 'UNIDAD_MEDIDA'
        verbose_name = "Unidad de Medida"
        verbose_name_plural = "Unidades de Medida"
        ordering = ['nombre_unidad']
    
    def __str__(self):
        return f"{self.nombre_unidad} ({self.abreviatura})"

class Insumo(models.Model):
    """Tabla INSUMO - Maestro de insumos/productos del restaurante"""
    id_insumo = models.AutoField(primary_key=True)
    nombre_insumo = models.CharField(max_length=100, verbose_name="Nombre del Insumo")
    unidad_medida = models.CharField(max_length=50, verbose_name="Unidad de Medida")
    costo_promedio = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Costo Promedio")
    codigo = models.CharField(max_length=30, verbose_name="Código", unique=True)
    
    class Meta:
        db_table = 'INSUMO'
        verbose_name = "Insumo"
        verbose_name_plural = "Insumos"
        ordering = ['nombre_insumo']
    
    def __str__(self):
        return f"{self.nombre_insumo} ({self.unidad_medida})"

class Proveedor(models.Model):
    """Tabla PROVEEDOR - Proveedores de insumos"""
    id_proveedor = models.AutoField(primary_key=True)
    nombre_proveedor = models.CharField(max_length=120, verbose_name="Nombre del Proveedor")
    direccion_proveedor = models.CharField(max_length=50, verbose_name="Dirección", default='', blank=True)
    telefono_proveedor = models.CharField(max_length=15, verbose_name="Teléfono", default='', blank=True)
    correo_proveedor = models.EmailField(max_length=50, verbose_name="Correo Electrónico", default='', blank=True)
    
    class Meta:
        db_table = 'PROVEEDOR'
        verbose_name = "Proveedor"
        verbose_name_plural = "Proveedores"
        ordering = ['nombre_proveedor']
    
    def __str__(self):
        return self.nombre_proveedor

class OrdenCompra(models.Model):
    """Tabla ORDEN_COMPRA - Órdenes de compra a proveedores"""
    id_orden_compra = models.AutoField(primary_key=True)
    id_proveedor = models.ForeignKey(Proveedor, on_delete=models.RESTRICT, db_column='id_proveedor', verbose_name="Proveedor")
    fecha_pedido = models.DateField(verbose_name="Fecha del Pedido")
    estado = models.CharField(max_length=50, default='pendiente', verbose_name="Estado")
    
    class Meta:
        db_table = 'ORDEN_COMPRA'
        verbose_name = "Orden de Compra"
        verbose_name_plural = "Órdenes de Compra"
        ordering = ['-fecha_pedido']
    
    def __str__(self):
        return f"Orden {self.id_orden_compra} - {self.id_proveedor.nombre_proveedor}"

class DetalleCompra(models.Model):
    """Tabla DETALLE_COMPRA - Detalles de las órdenes de compra"""
    id_detalle_compra = models.AutoField(primary_key=True)
    id_orden_compra = models.ForeignKey(OrdenCompra, on_delete=models.CASCADE, db_column='id_orden_compra', verbose_name="Orden de Compra")
    id_insumo = models.ForeignKey(Insumo, on_delete=models.RESTRICT, db_column='id_insumo', verbose_name="Insumo")
    cantidad_pedida = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Cantidad Pedida")
    costo_unitario_acordado = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Costo Unitario")
    
    class Meta:
        db_table = 'DETALLE_COMPRA'
        verbose_name = "Detalle de Compra"
        verbose_name_plural = "Detalles de Compra"
    
    def __str__(self):
        return f"{self.id_insumo.nombre_insumo} - {self.cantidad_pedida} {self.id_insumo.unidad_medida}"
    
    def cantidad_recibida(self):
        """Calcula la cantidad total recibida de este detalle sumando todos los lotes"""
        from django.db.models import Sum
        total = self.lote_set.aggregate(total=Sum('cantidad_actual'))['total'] or 0
        return total
    
    def cantidad_pendiente(self):
        """Calcula la cantidad pendiente por recibir"""
        return max(0, self.cantidad_pedida - self.cantidad_recibida())
    
    def esta_completamente_recibido(self):
        """Verifica si el detalle está completamente recibido"""
        return self.cantidad_pendiente() <= 0

class Ubicacion(models.Model):
    """Tabla UBICACION - Ubicaciones físicas (bodega, cocina, etc.)"""
    id_ubicacion = models.AutoField(primary_key=True)
    nombre_ubicacion = models.CharField(max_length=100, verbose_name="Nombre de la Ubicación")
    tipo_ubicacion = models.CharField(max_length=50, verbose_name="Tipo de Ubicación")
    
    class Meta:
        db_table = 'UBICACION'
        verbose_name = "Ubicación"
        verbose_name_plural = "Ubicaciones"
        ordering = ['nombre_ubicacion']
    
    def __str__(self):
        return f"{self.nombre_ubicacion} ({self.tipo_ubicacion})"

class Lote(models.Model):
    """Tabla LOTE - Lotes de insumos con fechas de vencimiento (FEFO)"""
    id_lote = models.AutoField(primary_key=True)
    id_detalle_compra = models.ForeignKey(DetalleCompra, on_delete=models.CASCADE, db_column='id_detalle_compra', verbose_name="Detalle de Compra")
    id_insumo = models.ForeignKey(Insumo, on_delete=models.RESTRICT, db_column='id_insumo', verbose_name="Insumo")
    id_ubicacion = models.ForeignKey(Ubicacion, on_delete=models.RESTRICT, db_column='id_ubicacion', verbose_name="Ubicación")
    costo_unitario = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Costo Unitario")
    fecha_vencimiento = models.DateField(verbose_name="Fecha de Vencimiento")
    fecha_ingreso = models.DateField(verbose_name="Fecha de Ingreso")
    cantidad_actual = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Cantidad Actual")
    numero_lote = models.CharField(max_length=50, verbose_name="Número de Lote", db_column='numero_lote')
    
    class Meta:
        db_table = 'LOTE'
        verbose_name = "Lote"
        verbose_name_plural = "Lotes"
        ordering = ['fecha_vencimiento', 'fecha_ingreso']
    
    def __str__(self):
        return f"Lote {self.numero_lote} - {self.id_insumo.nombre_insumo} (Vence: {self.fecha_vencimiento})"
    
    @property
    def dias_para_vencer(self):
        from datetime import date
        return (self.fecha_vencimiento - date.today()).days
    
    @property
    def esta_vencido(self):
        from datetime import date
        return self.fecha_vencimiento < date.today()

class Plato(models.Model):
    """Tabla PLATO - Platos del menú del restaurante"""
    id_plato = models.AutoField(primary_key=True)
    nombre_plato = models.CharField(max_length=120, verbose_name="Nombre del Plato")
    
    class Meta:
        db_table = 'PLATO'
        verbose_name = "Plato"
        verbose_name_plural = "Platos"
        ordering = ['nombre_plato']
    
    def __str__(self):
        return self.nombre_plato

class PlatoProducido(models.Model):
    """Tabla PLATO_PRODUCIDO - Instancias de platos producidos con seguimiento de ubicación y estado"""
    ESTADO_CHOICES = [
        ('en_cocina', 'En Cocina'),
        ('en_mesa', 'En Mesa'),
        ('venta', 'Vendido'),
        ('entregado', 'Entregado'),
    ]
    
    id_plato_producido = models.AutoField(primary_key=True)
    id_plato = models.ForeignKey(Plato, on_delete=models.RESTRICT, db_column='id_plato', verbose_name="Plato")
    id_ubicacion = models.ForeignKey(Ubicacion, on_delete=models.RESTRICT, db_column='id_ubicacion', verbose_name="Ubicación")
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='en_cocina', verbose_name="Estado")
    fecha_produccion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Producción")
    fecha_entrega = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de Entrega")
    id_usuario = models.ForeignKey(User, on_delete=models.RESTRICT, db_column='id_usuario', verbose_name="Usuario", related_name='platos_producidos')
    
    class Meta:
        db_table = 'PLATO_PRODUCIDO'
        verbose_name = "Plato Producido"
        verbose_name_plural = "Platos Producidos"
        ordering = ['-fecha_produccion']
    
    def __str__(self):
        return f"{self.id_plato.nombre_plato} - {self.get_estado_display()} ({self.fecha_produccion.strftime('%Y-%m-%d %H:%M')})"

class DetalleProduccionInsumo(models.Model):
    """Tabla DETALLE_PRODUCCION_INSUMO - Detalle de insumos/lotes usados en la producción de un plato"""
    id_detalle_produccion = models.AutoField(primary_key=True)
    id_plato_producido = models.ForeignKey(PlatoProducido, on_delete=models.CASCADE, db_column='id_plato_producido', verbose_name="Plato Producido", related_name='detalles_insumos')
    id_lote = models.ForeignKey(Lote, on_delete=models.RESTRICT, db_column='id_lote', verbose_name="Lote")
    id_insumo = models.ForeignKey(Insumo, on_delete=models.RESTRICT, db_column='id_insumo', verbose_name="Insumo")
    cantidad_usada = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Cantidad Usada")
    fecha_uso = models.DateTimeField(default=timezone.now, verbose_name="Fecha de Uso")
    
    class Meta:
        db_table = 'DETALLE_PRODUCCION_INSUMO'
        verbose_name = "Detalle de Producción de Insumo"
        verbose_name_plural = "Detalles de Producción de Insumos"
        ordering = ['-fecha_uso']
    
    def __str__(self):
        return f"{self.id_plato_producido.id_plato.nombre_plato} - {self.id_insumo.nombre_insumo} ({self.cantidad_usada} {self.id_insumo.unidad_medida})"

class RegistroVentaPlato(models.Model):
    """Tabla REGISTRO_VENTA_PLATO - Registro de ventas de platos"""
    id_venta_plato = models.AutoField(primary_key=True)
    id_plato = models.ForeignKey(Plato, on_delete=models.CASCADE, db_column='id_plato', verbose_name="Plato")
    fecha_venta = models.DateField(verbose_name="Fecha de Venta")
    cantidad_vendida = models.IntegerField(verbose_name="Cantidad Vendida")
    
    class Meta:
        db_table = 'REGISTRO_VENTA_PLATO'
        verbose_name = "Venta de Plato"
        verbose_name_plural = "Ventas de Platos"
        ordering = ['-fecha_venta']
    
    def __str__(self):
        return f"{self.id_plato.nombre_plato} - {self.cantidad_vendida} unidades ({self.fecha_venta})"

class DetalleVentaIns(models.Model):
    """Tabla DETALLE_VENTA_INS - Detalle de insumos usados en ventas"""
    id_detalle_venta_insumo = models.AutoField(primary_key=True)
    id_venta_plato = models.ForeignKey(RegistroVentaPlato, on_delete=models.CASCADE, db_column='id_venta_plato', verbose_name="Venta de Plato")
    id_lote = models.ForeignKey(Lote, on_delete=models.RESTRICT, db_column='id_lote', verbose_name="Lote")
    cantidad_usada = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Cantidad Usada")
    
    class Meta:
        db_table = 'DETALLE_VENTA_INS'
        verbose_name = "Detalle de Venta de Insumo"
        verbose_name_plural = "Detalles de Venta de Insumos"
    
    def __str__(self):
        return f"{self.id_lote.id_insumo.nombre_insumo} - {self.cantidad_usada} {self.id_lote.id_insumo.unidad_medida}"

class Receta(models.Model):
    """Tabla RECETA - Recetas/escandallos de platos"""
    id_receta = models.AutoField(primary_key=True)
    id_plato = models.ForeignKey(Plato, on_delete=models.CASCADE, db_column='id_plato', verbose_name="Plato")
    id_insumo = models.ForeignKey(Insumo, on_delete=models.RESTRICT, db_column='id_insumo', verbose_name="Insumo")
    cantidad_necesaria = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Cantidad Necesaria")
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Fecha de Actualización")
    
    class Meta:
        db_table = 'RECETA'
        verbose_name = "Receta"
        verbose_name_plural = "Recetas"
        unique_together = ['id_plato', 'id_insumo']
    
    def __str__(self):
        return f"{self.id_plato.nombre_plato} - {self.id_insumo.nombre_insumo} ({self.cantidad_necesaria} {self.id_insumo.unidad_medida})"

class CausaMerma(models.Model):
    """Tabla CAUSA_MERMA - Causas de desperdicio/merma"""
    id_causa = models.AutoField(primary_key=True)
    nombre_causa = models.CharField(max_length=100, verbose_name="Nombre de la Causa")
    
    class Meta:
        db_table = 'CAUSA_MERMA'
        verbose_name = "Causa de Merma"
        verbose_name_plural = "Causas de Merma"
        ordering = ['nombre_causa']
    
    def __str__(self):
        return self.nombre_causa

class Rol(models.Model):
    """Tabla ROL - Roles de usuario del sistema"""
    id_rol = models.AutoField(primary_key=True)
    nombre_rol = models.CharField(max_length=50, verbose_name="Nombre del Rol")
    
    class Meta:
        db_table = 'ROL'
        verbose_name = "Rol"
        verbose_name_plural = "Roles"
        ordering = ['nombre_rol']
    
    def __str__(self):
        return self.nombre_rol

class Usuario(models.Model):
    """Tabla USUARIO - Usuarios del sistema (complementa Django User)"""
    id_usuario = models.AutoField(primary_key=True)
    id_rol = models.ForeignKey(Rol, on_delete=models.RESTRICT, db_column='id_rol', verbose_name="Rol")
    nombre = models.CharField(max_length=100, verbose_name="Nombre")
    email = models.EmailField(unique=True, verbose_name="Email")
    password_hash = models.CharField(max_length=128, verbose_name="Hash de Contraseña")
    # Campo opcional que puede no existir en la base de datos
    # user_django = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True, verbose_name="Usuario Django")
    
    class Meta:
        db_table = 'USUARIO'
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"
        ordering = ['nombre']
    
    def __str__(self):
        return f"{self.nombre} ({self.id_rol.nombre_rol})"

class Merma(models.Model):
    """Tabla MERMA - Registro de desperdicios/mermas"""
    TIPO_MERMA_CHOICES = [
        ('lote', 'Lote'),
        ('plato', 'Plato Producido'),
    ]
    
    id_merma = models.AutoField(primary_key=True)
    tipo_merma = models.CharField(max_length=10, choices=TIPO_MERMA_CHOICES, default='lote', verbose_name="Tipo de Merma")
    id_lote = models.ForeignKey(Lote, on_delete=models.RESTRICT, db_column='id_lote', verbose_name="Lote", null=True, blank=True)
    id_plato_producido = models.ForeignKey('PlatoProducido', on_delete=models.RESTRICT, db_column='id_plato_producido', verbose_name="Plato Producido", null=True, blank=True, related_name='mermas')
    id_causa = models.ForeignKey(CausaMerma, on_delete=models.RESTRICT, db_column='id_causa', verbose_name="Causa")
    id_usuario = models.ForeignKey(Usuario, on_delete=models.RESTRICT, db_column='id_usuario', verbose_name="Usuario")
    fecha_registro = models.DateField(verbose_name="Fecha de Registro")
    cantidad_desperdiciada = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Cantidad Desperdiciada")
    
    class Meta:
        db_table = 'MERMA'
        verbose_name = "Merma"
        verbose_name_plural = "Mermas"
        ordering = ['-fecha_registro']
    
    def clean(self):
        """Validar que tenga lote o plato, pero no ambos"""
        from django.core.exceptions import ValidationError
        if not self.id_lote and not self.id_plato_producido:
            raise ValidationError('Debe especificar un lote o un plato producido.')
        if self.id_lote and self.id_plato_producido:
            raise ValidationError('No puede especificar tanto un lote como un plato producido.')
    
    def __str__(self):
        if self.id_lote:
            return f"Merma {self.id_merma} - {self.id_lote.id_insumo.nombre_insumo} ({self.cantidad_desperdiciada} {self.id_lote.id_insumo.unidad_medida})"
        elif self.id_plato_producido:
            return f"Merma {self.id_merma} - {self.id_plato_producido.id_plato.nombre_plato} ({self.cantidad_desperdiciada} unidades)"
        return f"Merma {self.id_merma}"

class PrediccionDemanda(models.Model):
    """Tabla PREDICCION_DEMANDA - Predicciones de demanda de platos"""
    id_prediccion = models.AutoField(primary_key=True)
    id_plato = models.ForeignKey(Plato, on_delete=models.CASCADE, verbose_name="Plato")
    fecha_prediccion = models.DateField(verbose_name="Fecha de Predicción")
    cantidad_pronosticada = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Cantidad Pronosticada")
    
    class Meta:
        db_table = 'PREDICCION_DEMANDA'
        verbose_name = "Predicción de Demanda"
        verbose_name_plural = "Predicciones de Demanda"
        ordering = ['-fecha_prediccion']
    
    def __str__(self):
        return f"{self.id_plato.nombre_plato} - {self.cantidad_pronosticada} unidades ({self.fecha_prediccion})"

class MovimientoStock(models.Model):
    """Tabla MOVIMIENTO_STOCK - Movimientos de stock (entrada, salida, transferencia, ajuste)"""
    TIPO_MOVIMIENTO_CHOICES = [
        ('entrada', 'Entrada'),
        ('salida', 'Salida'),
        ('transferencia', 'Transferencia'),
        ('ajuste', 'Ajuste'),
    ]
    
    ORIGEN_MOVIMIENTO_CHOICES = [
        ('compra', 'Compra'),
        ('venta', 'Venta'),
        ('merma', 'Merma'),
        ('prediccion', 'Predicción'),
        ('manual', 'Manual'),
        ('produccion', 'Producción'),
    ]
    
    id_movimiento = models.AutoField(primary_key=True)
    id_lote = models.ForeignKey(Lote, on_delete=models.RESTRICT, db_column='id_lote', verbose_name="Lote")
    id_usuario = models.ForeignKey(Usuario, on_delete=models.RESTRICT, db_column='id_usuario', verbose_name="Usuario")
    fecha_movimiento = models.DateField(verbose_name="Fecha de Movimiento")
    tipo_movimiento = models.CharField(max_length=20, choices=TIPO_MOVIMIENTO_CHOICES, verbose_name="Tipo de Movimiento")
    origen_movimiento = models.CharField(max_length=20, choices=ORIGEN_MOVIMIENTO_CHOICES, verbose_name="Origen del Movimiento")
    cantidad = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Cantidad")
    
    class Meta:
        db_table = 'MOVIMIENTO_STOCK'
        verbose_name = "Movimiento de Stock"
        verbose_name_plural = "Movimientos de Stock"
        ordering = ['-fecha_movimiento']
    
    def __str__(self):
        return f"{self.get_tipo_movimiento_display()} - {self.id_lote.id_insumo.nombre_insumo} ({self.cantidad} {self.id_lote.id_insumo.unidad_medida})"

class EvaluacionProveedor(models.Model):
    """Tabla EVALUACION_PROVEEDOR - Evaluaciones de proveedores"""
    id_evaluacion = models.AutoField(primary_key=True)
    id_proveedor = models.ForeignKey(Proveedor, on_delete=models.CASCADE, verbose_name="Proveedor")
    fecha = models.DateField(verbose_name="Fecha")
    criterio = models.CharField(max_length=100, verbose_name="Criterio")
    puntaje = models.DecimalField(max_digits=4, decimal_places=2, verbose_name="Puntaje")
    observaciones = models.TextField(blank=True, null=True, verbose_name="Observaciones")
    
    class Meta:
        db_table = 'EVALUACION_PROVEEDOR'
        verbose_name = "Evaluación de Proveedor"
        verbose_name_plural = "Evaluaciones de Proveedores"
        ordering = ['-fecha']
    
    def __str__(self):
        return f"{self.id_proveedor.nombre_proveedor} - {self.criterio} ({self.puntaje})"


class PreferenciaUsuarioVencidos(models.Model):
    """Preferencias del usuario sobre alertas de productos vencidos"""
    id_preferencia = models.AutoField(primary_key=True)
    id_usuario = models.ForeignKey(User, on_delete=models.CASCADE, db_column='id_usuario', verbose_name="Usuario", related_name='preferencias_vencidos')
    no_mostrar_alertas = models.BooleanField(default=False, verbose_name="No Mostrar Alertas")
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Fecha de Actualización")
    # Guardar los IDs de lotes vencidos que ya se mostraron
    lotes_mostrados = models.JSONField(default=list, blank=True, verbose_name="Lotes Ya Mostrados")
    
    class Meta:
        db_table = 'PREFERENCIA_USUARIO_VENCIDOS'
        verbose_name = "Preferencia de Usuario - Vencidos"
        verbose_name_plural = "Preferencias de Usuarios - Vencidos"
        unique_together = ['id_usuario']
    
    def __str__(self):
        return f"Preferencias de {self.id_usuario.username} - No mostrar: {self.no_mostrar_alertas}"
