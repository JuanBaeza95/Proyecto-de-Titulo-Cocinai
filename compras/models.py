# Importamos los modelos desde inventario para mantener consistencia
from inventario.models import OrdenCompra, DetalleCompra, Proveedor, Insumo

# Los modelos ya están definidos en inventario.models
# Aquí solo los importamos para facilitar el acceso desde compras
__all__ = ['OrdenCompra', 'DetalleCompra', 'Proveedor', 'Insumo']
