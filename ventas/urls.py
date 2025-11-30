from django.urls import path
from . import views

app_name = 'ventas'

# The list MUST be named 'urlpatterns'
urlpatterns = [
    path('', views.index, name='index'),
    
    # Movimientos a Mesa
    path('mover-mesa/<int:plato_producido_id>/', views.mover_plato_a_mesa, name='mover_plato_a_mesa'),
    path('historial-movimientos-mesa/', views.historial_movimientos_mesa, name='historial_movimientos_mesa'),
    
    # Gestión de Mesas y Cierre de Ventas
    path('mesas-activas/', views.lista_mesas_activas, name='lista_mesas_activas'),
    path('cerrar-venta-mesa/', views.cerrar_venta_mesa, name='cerrar_venta_mesa'),
    path('historial-ventas-platos/', views.historial_ventas_platos, name='historial_ventas_platos'),
    
    # Gestión de Comandas
    path('comandas/', views.lista_comandas, name='lista_comandas'),
    path('comandas/crear/', views.crear_comanda, name='crear_comanda'),
    path('comandas/detalle/<int:comanda_id>/', views.detalle_comanda, name='detalle_comanda'),
    path('comandas/entregar/<int:comanda_id>/', views.entregar_platos_comanda, name='entregar_platos_comanda'),
]