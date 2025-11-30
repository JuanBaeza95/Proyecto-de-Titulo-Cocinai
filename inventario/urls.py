from django.urls import path
from . import views, views_vencidos

app_name = 'inventario'

# The list MUST be named 'urlpatterns'
urlpatterns = [
    # Página principal
    path('', views.index, name='index'),
    
    # Gestión de Insumos
    path('insumos/', views.lista_insumos, name='lista_insumos'),
    path('insumos/crear/', views.crear_insumo, name='crear_insumo'),
    path('insumos/editar/<int:insumo_id>/', views.editar_insumo, name='editar_insumo'),
    path('insumos/eliminar/<int:insumo_id>/', views.eliminar_insumo, name='eliminar_insumo'),
    
    # Gestión de Productos (temporalmente redirige a insumos)
    path('productos/', views.lista_insumos, name='lista_productos'),
    
    # Gestión de Categorías
    path('categorias/', views.lista_categorias, name='lista_categorias'),
    path('categorias/crear/', views.crear_categoria, name='crear_categoria'),
    
    # Gestión de Unidades
    path('unidades/', views.lista_unidades, name='lista_unidades'),
    path('unidades/crear/', views.crear_unidad, name='crear_unidad'),
    
    # Gestión de Proveedores
    path('proveedores/', views.lista_proveedores, name='lista_proveedores'),
    path('proveedores/crear/', views.crear_proveedor, name='crear_proveedor'),
    path('proveedores/editar/<int:proveedor_id>/', views.editar_proveedor, name='editar_proveedor'),
    path('proveedores/eliminar/<int:proveedor_id>/', views.eliminar_proveedor, name='eliminar_proveedor'),
    
    # Gestión de Ubicaciones
    path('ubicaciones/', views.lista_ubicaciones, name='lista_ubicaciones'),
    path('ubicaciones/crear/', views.crear_ubicacion, name='crear_ubicacion'),
    path('ubicaciones/editar/<int:ubicacion_id>/', views.editar_ubicacion, name='editar_ubicacion'),
    path('ubicaciones/eliminar/<int:ubicacion_id>/', views.eliminar_ubicacion, name='eliminar_ubicacion'),
    
    # Gestión de Lotes
    path('lotes/', views.lista_lotes, name='lista_lotes'),
    
    # Gestión de Movimientos de Stock
    path('movimientos/crear/', views.crear_movimiento_stock, name='crear_movimiento_stock'),
    path('movimientos/historial/', views.historial_movimientos, name='historial_movimientos'),
    
    # Gestión de Causas de Merma
    path('causas-merma/', views.lista_causas_merma, name='lista_causas_merma'),
    path('causas-merma/crear/', views.crear_causa_merma, name='crear_causa_merma'),
    path('causas-merma/editar/<int:causa_id>/', views.editar_causa_merma, name='editar_causa_merma'),
    path('causas-merma/eliminar/<int:causa_id>/', views.eliminar_causa_merma, name='eliminar_causa_merma'),
    
    # Gestión de Mermas
    path('mermas/', views.lista_mermas, name='lista_mermas'),
    path('mermas/crear-lote/', views.crear_merma_lote, name='crear_merma_lote'),
    path('mermas/crear-plato/', views.crear_merma_plato, name='crear_merma_plato'),
    
    # Alertas de Productos Vencidos
    path('api/vencidos/', views_vencidos.obtener_productos_vencidos, name='api_vencidos'),
    path('api/vencidos/marcar-vistos/', views_vencidos.marcar_vencidos_vistos, name='marcar_vencidos_vistos'),
    path('vencidos/mermar/<int:lote_id>/', views_vencidos.redirigir_mermar_lote, name='redirigir_mermar_lote'),
]