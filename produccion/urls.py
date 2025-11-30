from django.urls import path
from . import views

app_name = 'produccion'

# The list MUST be named 'urlpatterns'
urlpatterns = [
    path('', views.index, name='index'),
    
    # Gestión de Recetas
    path('recetas/', views.lista_recetas, name='lista_recetas'),
    path('recetas/crear/', views.crear_receta, name='crear_receta'),
    path('recetas/editar/<int:plato_id>/', views.editar_receta, name='editar_receta'),
    path('recetas/detalle/<int:plato_id>/', views.detalle_receta, name='detalle_receta'),
    path('recetas/eliminar/<int:plato_id>/', views.eliminar_receta, name='eliminar_receta'),
    
    # Gestión de Platos
    path('platos/', views.lista_platos, name='lista_platos'),
    path('platos/crear/', views.crear_plato, name='crear_plato'),
    path('platos/editar/<int:plato_id>/', views.editar_plato, name='editar_plato'),
    path('platos/eliminar/<int:plato_id>/', views.eliminar_plato, name='eliminar_plato'),
    
    # Gestión de Platos Producidos
    path('platos-producidos/', views.lista_platos_producidos, name='lista_platos_producidos'),
    path('platos-producidos/crear/', views.crear_plato_producido, name='crear_plato_producido'),
    path('platos-producidos/detalle/<int:plato_producido_id>/', views.detalle_plato_producido, name='detalle_plato_producido'),
    path('platos-producidos/mover-mesa/<int:plato_producido_id>/', views.mover_plato_a_mesa, name='mover_plato_a_mesa'),
    path('platos-producidos/eliminar/<int:plato_producido_id>/', views.eliminar_plato_producido, name='eliminar_plato_producido'),
    path('platos-producidos/mermar/<int:plato_producido_id>/', views.redirigir_mermar_plato, name='redirigir_mermar_plato'),
    
    # Gestión de Comandas
    path('comandas/', views.lista_comandas, name='lista_comandas'),
    path('comandas/detalle/<int:comanda_id>/', views.detalle_comanda_produccion, name='detalle_comanda_produccion'),
    path('comandas/actualizar/<int:comanda_id>/', views.actualizar_estado_detalles, name='actualizar_estado_detalles'),
]