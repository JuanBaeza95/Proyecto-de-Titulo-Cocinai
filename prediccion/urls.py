from django.urls import path
from . import views

app_name = 'prediccion'

urlpatterns = [
    path('', views.index, name='index'),
    path('ventas/semanales/', views.analisis_ventas_semanales, name='ventas_semanales'),
    path('ventas/mensuales/', views.analisis_ventas_mensuales, name='ventas_mensuales'),
    path('mermas/', views.analisis_mermas, name='mermas'),
    path('mermas/platos/', views.analisis_mermas_platos, name='mermas_platos'),
    path('proyeccion-compras/', views.proyeccion_compras, name='proyeccion_compras'),
    path('anomalias/', views.anomalias, name='anomalias'),
    path('reporte-completo/', views.reporte_completo, name='reporte_completo'),
    # Nuevas rutas para predicciones ML
    path('predicciones/ventas/', views.predicciones_ventas, name='predicciones_ventas'),
    path('predicciones/ventas-periodo/', views.predicciones_ventas_periodo, name='predicciones_ventas_periodo'),
    path('predicciones/demanda/', views.predicciones_demanda, name='predicciones_demanda'),
    # Vista para reentrenar modelo
    path('reentrenar-modelo/', views.reentrenar_modelo, name='reentrenar_modelo'),
]