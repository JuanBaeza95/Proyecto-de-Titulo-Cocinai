"""
Vistas del módulo de Predicciones
"""
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum, Count
from django.core.paginator import Paginator
from usuarios.permissions import menu_required
from . import analytics
from .config_ml import obtener_configuracion_ml, NIVEL_DATOS_DEFAULT
from inventario.models import Plato, Insumo
from datetime import date, timedelta, datetime
import json


@login_required
@menu_required('prediccion', 'predicciones')
def index(request):
    """Dashboard principal de predicciones con insights generales"""
    try:
        insights = analytics.obtener_insights_dashboard()
        
        context = {
            'title': 'Dashboard de Predicciones',
            'insights': insights,
        }
        return render(request, 'prediccion/index.html', context)
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"Error en dashboard de predicciones: {error_trace}")  # Para debugging
        messages.error(request, f'Error al cargar el dashboard: {str(e)}')
        # Proporcionar un contexto mínimo para que el template no falle
        context = {
            'title': 'Dashboard de Predicciones',
            'insights': {
                'ventas_mes': 0,
                'mermas_mes': 0,
                'platos_mas_vendidos': [],
                'analisis_semanal': {'sugerencias': [], 'total_actual': 0, 'total_anterior': 0},
                'analisis_mermas': {'alertas': [], 'total_mermas': 0, 'total_registros': 0},
                'insumos_urgentes': [],
                'anomalias_ventas': [],
                'anomalias_mermas': []
            },
            'error': str(e)
        }
        return render(request, 'prediccion/index.html', context)


@login_required
@menu_required('prediccion', 'predicciones')
def analisis_ventas_semanales(request):
    """Análisis de ventas semanales comparando con año anterior"""
    plato_id = request.GET.get('plato', None)
    plato_seleccionado = None
    
    if plato_id:
        try:
            plato_seleccionado = Plato.objects.get(id_plato=plato_id)
        except Plato.DoesNotExist:
            messages.warning(request, 'Plato no encontrado')
    
    try:
        analisis = analytics.analizar_ventas_semanales(plato_id=int(plato_id) if plato_id else None)
        platos = Plato.objects.all().order_by('nombre_plato')
        
        # Agregar predicciones ML si está disponible
        predicciones_ml = {}
        if analytics.ML_DISPONIBLE:
            try:
                predicciones_ml = analytics.predecir_ventas_ml(
                    plato_id=int(plato_id) if plato_id else None,
                    dias_prediccion=7
                )
            except Exception as e:
                print(f"Error al obtener predicciones ML: {e}")
        
        context = {
            'title': 'Análisis de Ventas Semanales',
            'analisis': analisis,
            'platos': platos,
            'plato_seleccionado': plato_seleccionado,
            'predicciones_ml': predicciones_ml,
            'ml_disponible': analytics.ML_DISPONIBLE,
        }
        return render(request, 'prediccion/ventas_semanales.html', context)
    except Exception as e:
        messages.error(request, f'Error al analizar ventas semanales: {str(e)}')
        return redirect('prediccion:index')


@login_required
@menu_required('prediccion', 'predicciones')
def analisis_ventas_mensuales(request):
    """Análisis de ventas mensuales comparando con mes anterior"""
    plato_id = request.GET.get('plato', None)
    plato_seleccionado = None
    
    if plato_id:
        try:
            plato_seleccionado = Plato.objects.get(id_plato=plato_id)
        except Plato.DoesNotExist:
            messages.warning(request, 'Plato no encontrado')
    
    try:
        analisis = analytics.analizar_ventas_mensuales(plato_id=int(plato_id) if plato_id else None)
        platos = Plato.objects.all().order_by('nombre_plato')
        
        context = {
            'title': 'Análisis de Ventas Mensuales',
            'analisis': analisis,
            'platos': platos,
            'plato_seleccionado': plato_seleccionado,
        }
        return render(request, 'prediccion/ventas_mensuales.html', context)
    except Exception as e:
        messages.error(request, f'Error al analizar ventas mensuales: {str(e)}')
        return redirect('prediccion:index')


@login_required
@menu_required('prediccion', 'predicciones')
def analisis_mermas(request):
    """Análisis detallado de mermas mensuales"""
    try:
        analisis = analytics.analizar_mermas_mensuales()
        tendencias = analytics.analizar_tendencias_mermas(meses_atras=6)
        
        context = {
            'title': 'Análisis de Mermas',
            'analisis': analisis,
            'tendencias': tendencias,
        }
        return render(request, 'prediccion/mermas.html', context)
    except Exception as e:
        messages.error(request, f'Error al analizar mermas: {str(e)}')
        return redirect('prediccion:index')


@login_required
@menu_required('prediccion', 'predicciones')
def analisis_mermas_platos(request):
    """Análisis de mermas de platos producidos con cálculo de insumos equivalentes"""
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    
    # Establecer fechas por defecto (últimos 30 días)
    hoy = date.today()
    fecha_desde_default = hoy - timedelta(days=30)
    
    try:
        # Convertir fechas del formulario
        fecha_desde_obj = None
        fecha_hasta_obj = None
        
        if fecha_desde:
            try:
                fecha_desde_obj = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
            except ValueError:
                messages.warning(request, 'Fecha de inicio inválida. Usando fecha por defecto.')
                fecha_desde_obj = fecha_desde_default
        else:
            fecha_desde_obj = fecha_desde_default
        
        if fecha_hasta:
            try:
                fecha_hasta_obj = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
            except ValueError:
                messages.warning(request, 'Fecha de fin inválida. Usando fecha actual.')
                fecha_hasta_obj = hoy
        else:
            fecha_hasta_obj = hoy
        
        # Validar que fecha_desde <= fecha_hasta
        if fecha_desde_obj > fecha_hasta_obj:
            messages.warning(request, 'La fecha de inicio debe ser anterior a la fecha de fin.')
            fecha_desde_obj, fecha_hasta_obj = fecha_hasta_obj, fecha_desde_obj
        
        # Obtener análisis
        analisis = analytics.analizar_mermas_platos_producidos(
            fecha_desde=fecha_desde_obj,
            fecha_hasta=fecha_hasta_obj
        )
        
        context = {
            'title': 'Análisis de Mermas de Platos Producidos',
            'analisis': analisis,
            'fecha_desde': fecha_desde_obj,
            'fecha_hasta': fecha_hasta_obj,
        }
        return render(request, 'prediccion/mermas_platos.html', context)
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"Error en análisis de mermas de platos: {error_trace}")
        messages.error(request, f'Error al analizar mermas de platos: {str(e)}')
        return redirect('prediccion:index')


@login_required
@menu_required('prediccion', 'predicciones')
def proyeccion_compras(request):
    """Proyección de compras necesarias basada en Machine Learning usando predicciones de ventas y recetas"""
    dias_proyeccion = request.GET.get('dias', '30')
    usar_ml = request.GET.get('ml', 'true').lower() == 'true'
    nivel_datos = request.GET.get('nivel', NIVEL_DATOS_DEFAULT)  # 'rapido', 'estandar', 'optimo'
    modelo_tipo = request.GET.get('modelo_tipo', 'auto')  # Tipo de modelo ML para predicciones de ventas
    
    # Obtener configuración del nivel seleccionado
    config_ml = obtener_configuracion_ml(nivel_datos)
    dias_minimos = config_ml['dias_minimos']
    
    try:
        dias = int(dias_proyeccion)
        if dias < 7 or dias > 90:
            dias = 30
            messages.warning(request, 'Días de proyección ajustados a 30 (rango válido: 7-90)')
    except ValueError:
        dias = 30
    
    # Obtener modelos disponibles para el selector
    try:
        from .ml_models import XGBOOST_DISPONIBLE, LIGHTGBM_DISPONIBLE
        modelos_disponibles = ['auto']
        if XGBOOST_DISPONIBLE:
            modelos_disponibles.append('xgboost')
        if LIGHTGBM_DISPONIBLE:
            modelos_disponibles.append('lightgbm')
        modelos_disponibles.extend(['random_forest', 'gradient_boosting'])
    except:
        modelos_disponibles = ['auto', 'random_forest', 'gradient_boosting']
    
    try:
        proyecciones = analytics.proyectar_compras_insumos(
            dias_proyeccion=dias, 
            usar_ml=usar_ml, 
            nivel_datos=nivel_datos,
            modelo_tipo=modelo_tipo
        )
        
        # Diagnóstico: contar cuántos insumos tienen datos suficientes
        total_insumos_sistema = Insumo.objects.count()
        insumos_con_prediccion = len(proyecciones)
        insumos_sin_datos = total_insumos_sistema - insumos_con_prediccion
        
        # Verificar cuántos platos tienen recetas
        from inventario.models import Receta
        total_platos_con_receta = Plato.objects.filter(receta__isnull=False).distinct().count()
        
        # Si no hay proyecciones, puede ser por falta de datos de ventas de platos
        if not proyecciones:
            mensaje_base = (
                f'No se encontraron proyecciones. El sistema requiere que los platos tengan: '
                f'1) Receta definida, 2) Al menos 7 días únicos con ventas históricas, '
                f'3) Mínimo 30 registros de ventas en los últimos 365 días. '
                f'De {total_platos_con_receta} platos con receta, ninguno cumple estos requisitos.'
            )
            
            mensaje_base += (
                f' Revisa la consola del servidor para ver detalles de qué platos se omitieron. '
                f'Para generar datos históricos, ejecuta: "python manage.py generar_datos_ml --dias 365"'
            )
            
            messages.warning(request, mensaje_base)
        elif insumos_sin_datos > 0:
            # Calcular cuántos platos se procesaron exitosamente
            platos_procesados = len(set([
                detalle.get('plato') 
                for proy in proyecciones 
                for detalle in proy.get('detalles_uso', [])
            ]))
            
            from inventario.models import Receta
            total_platos_con_receta = Plato.objects.filter(receta__isnull=False).distinct().count()
            platos_omitidos = total_platos_con_receta - platos_procesados
            
            mensaje_info = (
                f'Se encontraron proyecciones para {insumos_con_prediccion} de {total_insumos_sistema} insumos. '
            )
            
            if platos_omitidos > 0:
                mensaje_info += (
                    f'Nota: {platos_omitidos} de {total_platos_con_receta} platos con receta no tienen suficientes datos históricos de ventas '
                    f'(mínimo: 7 días únicos con ventas, 30 registros en últimos 365 días). '
                    f'Revisa la consola del servidor para ver detalles.'
                )
            
            messages.info(request, mensaje_info)
            
            # Mostrar advertencia si está en modo rápido
            if nivel_datos == 'rapido' and config_ml.get('advertencia'):
                messages.warning(request, config_ml['advertencia'])
        
        # Mostrar TODAS las proyecciones, no solo las que necesitan compra
        # El usuario puede filtrar después si quiere
        proyecciones_filtradas = proyecciones  # Mostrar todas
        # Opción: Si quieres mostrar solo los que necesitan compra, descomenta la siguiente línea:
        # proyecciones_filtradas = [p for p in proyecciones if p['cantidad_a_comprar'] > 0]
        
        # Paginación
        paginator = Paginator(proyecciones_filtradas, 20)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Estadísticas
        total_insumos = len(proyecciones_filtradas)
        insumos_urgentes = len([p for p in proyecciones_filtradas if p['urgencia'] == 'alta'])
        insumos_medios = len([p for p in proyecciones_filtradas if p['urgencia'] == 'media'])
        insumos_bajos = len([p for p in proyecciones_filtradas if p['urgencia'] == 'baja'])
        
        # Determinar método usado
        metodo_usado = 'Estadístico'
        if proyecciones and proyecciones[0].get('metodo'):
            metodo_usado = proyecciones[0].get('metodo', 'Estadístico')
        ml_disponible = analytics.ML_DISPONIBLE
        
        context = {
            'title': 'Proyección de Compras',
            'page_obj': page_obj,
            'dias_proyeccion': dias,
            'total_insumos': total_insumos,
            'insumos_urgentes': insumos_urgentes,
            'insumos_medios': insumos_medios,
            'insumos_bajos': insumos_bajos,
            'proyecciones_json': json.dumps(proyecciones_filtradas[:50]),  # Para gráficos
            'metodo_usado': metodo_usado,
            'ml_disponible': ml_disponible,
            'usar_ml': usar_ml,
            'nivel_datos': nivel_datos,
            'config_ml': config_ml,
            'dias_minimos': dias_minimos,
            'modelo_tipo': modelo_tipo,
            'modelos_disponibles': modelos_disponibles,
        }
        return render(request, 'prediccion/proyeccion_compras.html', context)
    except Exception as e:
        messages.error(request, f'Error al proyectar compras: {str(e)}')
        return redirect('prediccion:index')


@login_required
@menu_required('prediccion', 'predicciones')
def anomalias(request):
    """Detección de anomalías en ventas y mermas usando ML"""
    usar_ml = request.GET.get('ml', 'true').lower() == 'true'
    
    try:
        anomalias_ventas = analytics.detectar_anomalias_ventas(usar_ml=usar_ml)
        anomalias_mermas = analytics.detectar_anomalias_mermas(usar_ml=usar_ml)
        
        ml_disponible = analytics.ML_DISPONIBLE
        
        context = {
            'title': 'Detección de Anomalías',
            'anomalias_ventas': anomalias_ventas,
            'anomalias_mermas': anomalias_mermas,
            'ml_disponible': ml_disponible,
            'usar_ml': usar_ml,
        }
        return render(request, 'prediccion/anomalias.html', context)
    except Exception as e:
        messages.error(request, f'Error al detectar anomalías: {str(e)}')
        return redirect('prediccion:index')


@login_required
@menu_required('prediccion', 'predicciones')
def reporte_completo(request):
    """Reporte completo con todos los análisis y predicciones ML"""
    try:
        # Análisis de ventas
        analisis_semanal = analytics.analizar_ventas_semanales()
        analisis_mensual = analytics.analizar_ventas_mensuales()
        
        # Análisis de mermas
        analisis_mermas = analytics.analizar_mermas_mensuales()
        tendencias_mermas = analytics.analizar_tendencias_mermas(meses_atras=6)
        
        # Proyecciones (usando ML si está disponible)
        proyecciones = analytics.proyectar_compras_insumos(dias_proyeccion=30, usar_ml=True)
        insumos_urgentes = [p for p in proyecciones if p['urgencia'] == 'alta']
        
        # Anomalías (usando ML si está disponible)
        anomalias_ventas = analytics.detectar_anomalias_ventas(usar_ml=True)[:5]
        anomalias_mermas = analytics.detectar_anomalias_mermas(usar_ml=True)[:5]
        
        # Predicciones ML
        predicciones_ventas_ml = {}
        predicciones_ventas_por_plato = []
        predicciones_mermas_ml = {}
        predicciones_demanda_ml = []
        
        if analytics.ML_DISPONIBLE:
            try:
                # Predicciones totalizadas (sin plato específico)
                predicciones_ventas_ml = analytics.predecir_ventas_ml(dias_prediccion=7)
                
                # Predicciones por plato individual
                platos = Plato.objects.all().order_by('nombre_plato')
                for plato in platos:
                    try:
                        pred_plato = analytics.predecir_ventas_ml(
                            plato_id=plato.id_plato,
                            dias_prediccion=7
                        )
                        if pred_plato.get('predicciones') and not pred_plato.get('error'):
                            predicciones_ventas_por_plato.append({
                                'plato_id': plato.id_plato,
                                'plato_nombre': plato.nombre_plato,
                                'total_predicho': pred_plato.get('total_predicho', 0),
                                'promedio_diario': pred_plato.get('promedio_diario', 0),
                                'predicciones': pred_plato.get('predicciones', [])
                            })
                    except Exception as e:
                        print(f"Error al predecir ventas para plato {plato.nombre_plato}: {e}")
                        continue
                
                # Ordenar por total predicho descendente
                predicciones_ventas_por_plato.sort(key=lambda x: x['total_predicho'], reverse=True)
                
                predicciones_mermas_ml = analytics.predecir_mermas_ml(dias_prediccion=30)
                predicciones_demanda_ml = analytics.predecir_demanda_insumos_ml(dias_prediccion=30)[:10]
            except Exception as e:
                print(f"Error en predicciones ML: {e}")
        
        context = {
            'title': 'Reporte Completo de Predicciones',
            'analisis_semanal': analisis_semanal,
            'analisis_mensual': analisis_mensual,
            'analisis_mermas': analisis_mermas,
            'tendencias_mermas': tendencias_mermas,
            'proyecciones': proyecciones[:20],  # Top 20
            'insumos_urgentes': insumos_urgentes,
            'anomalias_ventas': anomalias_ventas,
            'anomalias_mermas': anomalias_mermas,
            'ml_disponible': analytics.ML_DISPONIBLE,
            'predicciones_ventas_ml': predicciones_ventas_ml,
            'predicciones_ventas_por_plato': predicciones_ventas_por_plato,
            'predicciones_mermas_ml': predicciones_mermas_ml,
            'predicciones_demanda_ml': predicciones_demanda_ml,
        }
        return render(request, 'prediccion/reporte_completo.html', context)
    except Exception as e:
        messages.error(request, f'Error al generar reporte completo: {str(e)}')
        return redirect('prediccion:index')


@login_required
@menu_required('prediccion', 'predicciones')
def predicciones_ventas(request):
    """Vista dedicada para predicciones ML de ventas"""
    plato_id = request.GET.get('plato', None)
    dias = request.GET.get('dias', '7')
    modelo_tipo = request.GET.get('modelo_tipo', 'auto')
    
    try:
        dias_int = int(dias)
        if dias_int < 1 or dias_int > 30:
            dias_int = 7
    except ValueError:
        dias_int = 7
    
    # Obtener modelos disponibles
    try:
        from .ml_models import XGBOOST_DISPONIBLE, LIGHTGBM_DISPONIBLE
        modelos_disponibles = ['auto']
        if XGBOOST_DISPONIBLE:
            modelos_disponibles.append('xgboost')
        if LIGHTGBM_DISPONIBLE:
            modelos_disponibles.append('lightgbm')
        modelos_disponibles.extend(['random_forest', 'gradient_boosting'])
    except:
        modelos_disponibles = ['auto', 'random_forest', 'gradient_boosting']
    
    try:
        predicciones = analytics.predecir_ventas_ml(
            plato_id=int(plato_id) if plato_id else None,
            dias_prediccion=dias_int,
            modelo_tipo=modelo_tipo
        )
        platos = Plato.objects.all().order_by('nombre_plato')
        plato_seleccionado = None
        
        if plato_id:
            try:
                plato_seleccionado = Plato.objects.get(id_plato=plato_id)
            except Plato.DoesNotExist:
                pass
        
        context = {
            'title': 'Predicciones de Ventas (Machine Learning)',
            'predicciones': predicciones,
            'platos': platos,
            'plato_seleccionado': plato_seleccionado,
            'dias_prediccion': dias_int,
            'ml_disponible': analytics.ML_DISPONIBLE,
            'modelo_tipo': modelo_tipo,
            'modelos_disponibles': modelos_disponibles,
        }
        return render(request, 'prediccion/predicciones_ventas.html', context)
    except Exception as e:
        messages.error(request, f'Error al generar predicciones: {str(e)}')
        return redirect('prediccion:index')


@login_required
@menu_required('prediccion', 'predicciones')
def predicciones_demanda(request):
    """Vista dedicada para predicciones ML de demanda de insumos"""
    dias = request.GET.get('dias', '30')
    
    try:
        dias_int = int(dias)
        if dias_int < 7 or dias_int > 90:
            dias_int = 30
    except ValueError:
        dias_int = 30
    
    try:
        predicciones = analytics.predecir_demanda_insumos_ml(dias_prediccion=dias_int)
        
        # Paginación
        paginator = Paginator(predicciones, 20)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        context = {
            'title': 'Predicciones de Demanda (Machine Learning)',
            'page_obj': page_obj,
            'dias_prediccion': dias_int,
            'total_insumos': len(predicciones),
            'ml_disponible': analytics.ML_DISPONIBLE,
        }
        return render(request, 'prediccion/predicciones_demanda.html', context)
    except Exception as e:
        messages.error(request, f'Error al generar predicciones de demanda: {str(e)}')
        return redirect('prediccion:index')


@login_required
@menu_required('prediccion', 'predicciones')
def reentrenar_modelo(request):
    """
    Vista para reentrenar el modelo de Machine Learning manualmente
    Permite seleccionar parámetros y ver métricas del nuevo modelo
    """
    if request.method == 'POST':
        plato_id = request.POST.get('plato', None)
        modelo_tipo = request.POST.get('modelo_tipo', 'auto')
        dias_historia = request.POST.get('dias_historia', '365')
        
        try:
            plato_id_int = int(plato_id) if plato_id else None
            dias_historia_int = int(dias_historia)
            
            if dias_historia_int < 30 or dias_historia_int > 730:
                messages.warning(request, 'Días de historia ajustados a 365 (rango válido: 30-730)')
                dias_historia_int = 365
        except ValueError:
            plato_id_int = None
            dias_historia_int = 365
            messages.warning(request, 'Parámetros inválidos. Usando valores por defecto.')
        
        try:
            from .ml_models import entrenar_modelo_ventas, eliminar_modelo_guardado
            
            # Eliminar modelo guardado para forzar reentrenamiento
            eliminar_modelo_guardado(plato_id_int, modelo_tipo)
            
            # Entrenar el modelo (forzar reentrenamiento)
            resultado = entrenar_modelo_ventas(
                plato_id=plato_id_int,
                modelo_tipo=modelo_tipo,
                dias_historia=dias_historia_int,
                forzar_reentrenamiento=True
            )
            
            if resultado.get('modelo') is None:
                messages.error(request, f"Error al entrenar el modelo: {resultado.get('error', 'Error desconocido')}")
                return redirect('prediccion:reentrenar_modelo')
            
            # Mostrar métricas
            metricas = resultado.get('metricas', {})
            modelo_tipo_usado = resultado.get('modelo_tipo', modelo_tipo)
            
            messages.success(
                request,
                f"Modelo reentrenado exitosamente. "
                f"R²: {metricas.get('r2', 'N/A')} | "
                f"MAE: {metricas.get('mae', 'N/A')} | "
                f"RMSE: {metricas.get('rmse', 'N/A')} | "
                f"Modelo: {modelo_tipo_usado}"
            )
            
            # Redirigir a la misma página para mostrar resultados
            return redirect('prediccion:reentrenar_modelo')
            
        except Exception as e:
            messages.error(request, f'Error al reentrenar el modelo: {str(e)}')
            return redirect('prediccion:reentrenar_modelo')
    
    # GET: Mostrar formulario de reentrenamiento
    platos = Plato.objects.all().order_by('nombre_plato')
    
    # Obtener información del modelo actual (cargar desde archivo o entrenar)
    metricas_actuales = {}
    modelo_info = {}
    modelo_guardado_info = {}
    
    try:
        from .ml_models import (
            entrenar_modelo_ventas, cargar_modelo_entrenado, 
            XGBOOST_DISPONIBLE, LIGHTGBM_DISPONIBLE
        )
        from .ml_models import MODELS_DIR
        
        # Intentar cargar modelo guardado primero
        modelo_cargado = cargar_modelo_entrenado(None, 'auto', max_dias_antiguedad=30)
        
        if modelo_cargado and modelo_cargado.get('cargado_desde_archivo'):
            # Usar modelo guardado
            metricas_actuales = modelo_cargado.get('metricas', {})
            modelo_info = {
                'tipo': modelo_cargado.get('modelo_tipo', 'auto'),
                'datos_entrenamiento': modelo_cargado.get('datos_entrenamiento', 0),
                'datos_prueba': modelo_cargado.get('datos_prueba', 0),
                'mean_actual': modelo_cargado.get('mean_actual', 0),
                'mean_predicted': modelo_cargado.get('mean_predicted', 0),
            }
            modelo_guardado_info = {
                'existe': True,
                'fecha_entrenamiento': modelo_cargado.get('fecha_entrenamiento'),
                'dias_antiguedad': modelo_cargado.get('dias_antiguedad', 0),
            }
        else:
            # Entrenar modelo de prueba para mostrar métricas actuales
            resultado_prueba = entrenar_modelo_ventas(modelo_tipo='auto', dias_historia=365)
            
            if resultado_prueba.get('modelo'):
                metricas_actuales = resultado_prueba.get('metricas', {})
                modelo_info = {
                    'tipo': resultado_prueba.get('modelo_tipo', 'auto'),
                    'datos_entrenamiento': resultado_prueba.get('datos_entrenamiento', 0),
                    'datos_prueba': resultado_prueba.get('datos_prueba', 0),
                    'mean_actual': resultado_prueba.get('mean_actual', 0),
                    'mean_predicted': resultado_prueba.get('mean_predicted', 0),
                    'outliers_ajustados': resultado_prueba.get('outliers_ajustados', 0),
                }
            
            modelo_guardado_info = {
                'existe': False,
            }
        
        modelos_disponibles = ['auto']
        if XGBOOST_DISPONIBLE:
            modelos_disponibles.append('xgboost')
        if LIGHTGBM_DISPONIBLE:
            modelos_disponibles.append('lightgbm')
        modelos_disponibles.extend(['random_forest', 'gradient_boosting'])
        
    except Exception as e:
        modelos_disponibles = ['auto', 'random_forest', 'gradient_boosting']
        messages.warning(request, f'No se pudieron obtener métricas actuales: {str(e)}')
    
    context = {
        'title': 'Reentrenar Modelo de Machine Learning',
        'platos': platos,
        'metricas_actuales': metricas_actuales,
        'modelo_info': modelo_info,
        'modelo_guardado_info': modelo_guardado_info,
        'modelos_disponibles': modelos_disponibles,
        'ml_disponible': analytics.ML_DISPONIBLE,
        'models_dir': str(MODELS_DIR) if 'MODELS_DIR' in locals() else 'models_ml/',
    }
    
    return render(request, 'prediccion/reentrenar_modelo.html', context)


@login_required
@menu_required('prediccion', 'predicciones')
def predicciones_ventas_periodo(request):
    """
    Vista para predicciones de ventas con rango configurable y comparación con año anterior
    """
    # Obtener parámetros del formulario
    periodo_predefinido = request.GET.get('periodo', 'semana_siguiente')
    fecha_inicio_custom = request.GET.get('fecha_inicio', None)
    fecha_fin_custom = request.GET.get('fecha_fin', None)
    plato_id = request.GET.get('plato', None)
    
    hoy = date.today()
    fecha_inicio = None
    fecha_fin = None
    
    # Calcular fechas según período predefinido o custom
    if fecha_inicio_custom and fecha_fin_custom:
        try:
            fecha_inicio = datetime.strptime(fecha_inicio_custom, '%Y-%m-%d').date()
            fecha_fin = datetime.strptime(fecha_fin_custom, '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, 'Fechas inválidas. Usando período predefinido.')
            periodo_predefinido = 'semana_siguiente'
    
    if not fecha_inicio or not fecha_fin:
        # Calcular según período predefinido
        if periodo_predefinido == 'semana_siguiente':
            # Próxima semana (lunes a domingo)
            dias_hasta_lunes = (7 - hoy.weekday()) % 7
            if dias_hasta_lunes == 0:
                dias_hasta_lunes = 7
            fecha_inicio = hoy + timedelta(days=dias_hasta_lunes)
            fecha_fin = fecha_inicio + timedelta(days=6)
        elif periodo_predefinido == '2_semanas':
            dias_hasta_lunes = (7 - hoy.weekday()) % 7
            if dias_hasta_lunes == 0:
                dias_hasta_lunes = 7
            fecha_inicio = hoy + timedelta(days=dias_hasta_lunes)
            fecha_fin = fecha_inicio + timedelta(days=13)
        elif periodo_predefinido == 'mes_siguiente':
            # Primer día del próximo mes
            if hoy.month == 12:
                fecha_inicio = date(hoy.year + 1, 1, 1)
            else:
                fecha_inicio = date(hoy.year, hoy.month + 1, 1)
            # Último día del próximo mes
            if fecha_inicio.month == 12:
                fecha_fin = date(fecha_inicio.year + 1, 1, 1) - timedelta(days=1)
            else:
                fecha_fin = date(fecha_inicio.year, fecha_inicio.month + 1, 1) - timedelta(days=1)
        elif periodo_predefinido == 'trimestre_siguiente':
            # Primer día del próximo trimestre
            proximo_trimestre = ((hoy.month - 1) // 3 + 1) % 4
            if proximo_trimestre == 0:
                proximo_trimestre = 1
                año = hoy.year + 1
            else:
                año = hoy.year
            fecha_inicio = date(año, (proximo_trimestre - 1) * 3 + 1, 1)
            # Último día del trimestre
            if proximo_trimestre == 4:
                fecha_fin = date(año + 1, 1, 1) - timedelta(days=1)
            else:
                fecha_fin = date(año, proximo_trimestre * 3 + 1, 1) - timedelta(days=1)
        else:
            # Default: semana siguiente
            dias_hasta_lunes = (7 - hoy.weekday()) % 7
            if dias_hasta_lunes == 0:
                dias_hasta_lunes = 7
            fecha_inicio = hoy + timedelta(days=dias_hasta_lunes)
            fecha_fin = fecha_inicio + timedelta(days=6)
    
    # Validar que las fechas sean futuras
    if fecha_inicio <= hoy:
        messages.warning(request, 'La fecha de inicio debe ser futura. Ajustando a la próxima semana.')
        dias_hasta_lunes = (7 - hoy.weekday()) % 7
        if dias_hasta_lunes == 0:
            dias_hasta_lunes = 7
        fecha_inicio = hoy + timedelta(days=dias_hasta_lunes)
        fecha_fin = fecha_inicio + timedelta(days=6)
    
    # Obtener modelo tipo
    modelo_tipo = request.GET.get('modelo_tipo', 'auto')
    
    # Obtener modelos disponibles
    try:
        from .ml_models import XGBOOST_DISPONIBLE, LIGHTGBM_DISPONIBLE
        modelos_disponibles = ['auto']
        if XGBOOST_DISPONIBLE:
            modelos_disponibles.append('xgboost')
        if LIGHTGBM_DISPONIBLE:
            modelos_disponibles.append('lightgbm')
        modelos_disponibles.extend(['random_forest', 'gradient_boosting'])
    except:
        modelos_disponibles = ['auto', 'random_forest', 'gradient_boosting']
    
    # Obtener predicciones
    try:
        resultado = analytics.predecir_ventas_periodo_ml(
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            plato_id=int(plato_id) if plato_id else None,
            modelo_tipo=modelo_tipo
        )
        
        platos = Plato.objects.all().order_by('nombre_plato')
        plato_seleccionado = None
        
        if plato_id:
            try:
                plato_seleccionado = Plato.objects.get(id_plato=plato_id)
            except Plato.DoesNotExist:
                pass
        
        # Preparar datos de comparación para el template
        if resultado.get('predicciones') and resultado.get('comparacion_anio_anterior'):
            comparacion_datos = resultado['comparacion_anio_anterior'].get('ventas_por_dia_anterior', {})
            predicciones_con_comparacion = []
            for pred in resultado['predicciones']:
                fecha_pred = pred['fecha']
                # Buscar ventas del año anterior para esta fecha
                ventas_anterior = 0
                for fecha_anterior, cantidad in comparacion_datos.items():
                    # Comparar mes y día (ignorar año)
                    if isinstance(fecha_anterior, date) and isinstance(fecha_pred, date):
                        if fecha_anterior.month == fecha_pred.month and fecha_anterior.day == fecha_pred.day:
                            ventas_anterior = cantidad
                            break
                    elif isinstance(fecha_anterior, str) and isinstance(fecha_pred, date):
                        try:
                            fecha_ant = datetime.strptime(fecha_anterior, '%Y-%m-%d').date()
                            if fecha_ant.month == fecha_pred.month and fecha_ant.day == fecha_pred.day:
                                ventas_anterior = cantidad
                                break
                        except:
                            pass
                
                diferencia = pred['ventas_predichas'] - ventas_anterior
                pred['ventas_anterior'] = ventas_anterior
                pred['diferencia'] = diferencia
                predicciones_con_comparacion.append(pred)
            resultado['predicciones'] = predicciones_con_comparacion
        
        context = {
            'title': 'Predicciones de Ventas por Período',
            'resultado': resultado,
            'fecha_inicio': fecha_inicio,
            'fecha_fin': fecha_fin,
            'periodo_predefinido': periodo_predefinido,
            'platos': platos,
            'plato_seleccionado': plato_seleccionado,
            'ml_disponible': analytics.ML_DISPONIBLE,
            'modelo_tipo': modelo_tipo,
            'modelos_disponibles': modelos_disponibles,
        }
        
        return render(request, 'prediccion/predicciones_ventas_periodo.html', context)
    except Exception as e:
        messages.error(request, f'Error al generar predicciones: {str(e)}')
        return redirect('prediccion:index')
