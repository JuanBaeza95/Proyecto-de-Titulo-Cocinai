from django.urls import path
from . import views

app_name = 'compras'

# The list MUST be named 'urlpatterns'
urlpatterns = [
    # Página principal
    path('', views.index, name='index'),
    
    # Gestión de Órdenes de Compra
    path('ordenes/', views.lista_ordenes, name='lista_ordenes'),
    path('ordenes/crear/', views.crear_orden, name='crear_orden'),
    path('ordenes/<int:orden_id>/', views.detalle_orden, name='detalle_orden'),
    path('ordenes/<int:orden_id>/editar/', views.editar_orden, name='editar_orden'),
    path('ordenes/<int:orden_id>/eliminar/', views.eliminar_orden, name='eliminar_orden'),
    path('ordenes/<int:orden_id>/recepcionar/', views.recepcionar_orden, name='recepcionar_orden'),
]