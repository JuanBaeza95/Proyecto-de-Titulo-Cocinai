"""
Módulo de análisis y predicciones para CocinAI
Basado completamente en Machine Learning para predicciones avanzadas
"""
from datetime import datetime, timedelta, date
from django.db.models import Q, Sum, Count, Avg, F, DecimalField
from django.db.models.functions import TruncWeek, TruncMonth, TruncYear
from collections import defaultdict
from typing import Dict, List, Tuple, Optional
from inventario.models import (
    PlatoProducido, Merma, Lote, Insumo, Plato, Receta, 
    DetalleProduccionInsumo, CausaMerma, Usuario, Proveedor, DetalleCompra
)
from decimal import Decimal
from ventas.models import MovimientoMesa
from django.contrib.auth.models import User

# Importar modelos ML - REQUERIDO
try:
    from .ml_models import (
        predecir_ventas_futuras,
        predecir_ventas_periodo,
        predecir_demanda_insumo,
        predecir_mermas_futuras,
        recomendar_compras_ml,
        detectar_anomalias_ml_ventas,
        detectar_anomalias_ml_mermas,
        preparar_datos_ventas,
        preparar_datos_mermas
    )
    ML_DISPONIBLE = True
except ImportError as e:
    raise ImportError(
        f"ERROR CRÍTICO: Los modelos de Machine Learning no están disponibles.\n"
        f"Error: {e}\n"
        f"Por favor instala las dependencias: pip install scikit-learn pandas numpy\n"
        f"El módulo de predicciones requiere ML para funcionar."
    )


# PREDICCIONES ML DE VENTAS 

def predecir_ventas_ml(plato_id: Optional[int] = None, dias_prediccion: int = 7, modelo_tipo: str = 'auto') -> Dict:
    """
    Predice ventas futuras usando Machine Learning
    
    Args:
        plato_id: ID del plato (opcional)
        dias_prediccion: Días a predecir
        modelo_tipo: Tipo de modelo ML ('auto', 'xgboost', 'lightgbm', etc.)
    """
    if not ML_DISPONIBLE:
        return {
            'predicciones': [],
            'error': 'Machine Learning no disponible. Instala scikit-learn, pandas y numpy.',
            'metodo': 'No disponible'
        }
    
    try:
        predicciones = predecir_ventas_futuras(
            plato_id=plato_id,
            dias_prediccion=dias_prediccion,
            modelo_tipo=modelo_tipo
        )
        
        if not predicciones:
            return {
                'predicciones': [],
                'error': 'Datos insuficientes para generar predicciones',
                'metodo': 'ML (datos insuficientes)'
            }
        
        total_predicho = sum([p['ventas_predichas'] for p in predicciones])
        promedio_diario = total_predicho / len(predicciones) if predicciones else 0
        
        return {
            'predicciones': predicciones,
            'total_predicho': round(total_predicho, 1),
            'promedio_diario': round(promedio_diario, 1),
            'dias_prediccion': dias_prediccion,
            'metodo': 'Machine Learning (Random Forest)',
            'plato_id': plato_id
        }
    except Exception as e:
        return {
            'predicciones': [],
            'error': str(e),
            'metodo': 'ML (error)'
        }


def predecir_ventas_periodo_ml(fecha_inicio: date, fecha_fin: date, plato_id: Optional[int] = None, modelo_tipo: str = 'auto') -> Dict:
    """
    Predice ventas para un período configurable y compara con el año pasado
    
    Args:
        fecha_inicio: Fecha de inicio del período
        fecha_fin: Fecha de fin del período
        plato_id: ID del plato (opcional)
        modelo_tipo: Tipo de modelo ML ('auto', 'xgboost', 'lightgbm', etc.)
    
    Returns:
        Dict con predicciones y comparación con año anterior
    """
    if not ML_DISPONIBLE:
        return {
            'error': 'Machine Learning no disponible. Instala scikit-learn, pandas y numpy.',
            'predicciones': [],
            'comparacion_anio_anterior': None
        }
    
    try:
        resultado = predecir_ventas_periodo(
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            plato_id=plato_id,
            modelo_tipo=modelo_tipo
        )
        
        if resultado.get('error'):
            return resultado
        
        resultado['metodo'] = 'Machine Learning (Random Forest)'
        return resultado
    except Exception as e:
        return {
            'error': str(e),
            'predicciones': [],
            'comparacion_anio_anterior': None
        }


def predecir_demanda_insumos_ml(dias_prediccion: int = 30) -> List[Dict]:
    """
    Predice demanda de insumos usando ML
    OPTIMIZADO: Solo procesa insumos que tienen datos de consumo suficientes
    """
    if not ML_DISPONIBLE:
        return []
    
    # OPTIMIZACIÓN: Filtrar solo insumos con datos de consumo
    # Esto evita procesar insumos sin datos y reduce significativamente el tiempo
    from inventario.models import DetalleProduccionInsumo
    from django.db.models import Count
    from datetime import timedelta
    
    fecha_limite = date.today() - timedelta(days=365)
    
    # Obtener solo insumos que tienen al menos 1 registro de consumo en el último año
    insumos_con_datos = DetalleProduccionInsumo.objects.filter(
        fecha_uso__gte=fecha_limite
    ).values('id_insumo').annotate(
        total_registros=Count('id_detalle_produccion')
    ).filter(
        total_registros__gte=1  # Al menos 1 registro
    ).values_list('id_insumo', flat=True)
    
    # Obtener solo esos insumos
    insumos = Insumo.objects.filter(id_insumo__in=insumos_con_datos)
    
    predicciones = []
    insumos_sin_datos = []
    
    for insumo in insumos:
        try:
            pred = predecir_demanda_insumo(insumo.id_insumo, dias_prediccion=dias_prediccion)
            
            # Solo agregar si la predicción fue exitosa (no tiene error)
            if not pred.get('error'):
                pred['insumo_nombre'] = insumo.nombre_insumo
                pred['unidad_medida'] = insumo.unidad_medida
                predicciones.append(pred)
            else:
                # Guardar para logging pero no agregar a resultados
                insumos_sin_datos.append({
                    'insumo': insumo.nombre_insumo,
                    'error': pred.get('error', 'Error desconocido')
                })
        except Exception as e:
            # Solo loggear errores, no agregar a resultados
            insumos_sin_datos.append({
                'insumo': insumo.nombre_insumo,
                'error': f'Error al procesar: {str(e)}'
            })
            continue
    
    # Logging opcional (solo si hay muchos insumos sin datos)
    if len(insumos_sin_datos) > 0 and len(insumos_sin_datos) <= 10:
        # Solo mostrar si son pocos, para no saturar la consola
        print(f"[ML] {len(insumos_sin_datos)} insumos sin datos suficientes para predicción")
        for item in insumos_sin_datos[:5]:  # Mostrar solo los primeros 5
            print(f"  - {item['insumo']}: {item['error']}")
    elif len(insumos_sin_datos) > 10:
        # Si son muchos, solo mostrar el total
        print(f"[ML] {len(insumos_sin_datos)} insumos sin datos suficientes (omitiendo detalles)")
    
    return predicciones


def predecir_mermas_ml(dias_prediccion: int = 30) -> Dict:
    """
    Predice mermas futuras usando ML
    """
    if not ML_DISPONIBLE:
        return {
            'prediccion_diaria_promedio': 0,
            'prediccion_total': 0,
            'confianza': 'baja',
            'error': 'Machine Learning no disponible'
        }
    
    try:
        return predecir_mermas_futuras(dias_prediccion=dias_prediccion)
    except Exception as e:
        return {
            'prediccion_diaria_promedio': 0,
            'prediccion_total': 0,
            'confianza': 'baja',
            'error': str(e)
        }


# ========== ANÁLISIS DE VENTAS CON ML ==========

def analizar_ventas_semanales(plato_id: Optional[int] = None) -> Dict:
    """
    Analiza las ventas semanales usando Machine Learning
    Usa modelos ML para predecir y comparar patrones
    """
    if not ML_DISPONIBLE:
        raise RuntimeError("Machine Learning no está disponible. El módulo requiere ML para funcionar.")
    
    # Obtener predicciones ML para la próxima semana
    predicciones_ml = predecir_ventas_ml(plato_id=plato_id, dias_prediccion=7)
    
    # Obtener datos históricos usando ML
    df_ventas = preparar_datos_ventas(plato_id=plato_id, dias_historia=180)
    
    if df_ventas.empty:
        return {
            'semana_actual': date.today().isocalendar()[1],
            'año_actual': date.today().year,
            'ventas_actuales': {},
            'ventas_anterior': {},
            'sugerencias': [],
            'comparacion_platos': [],
            'total_actual': 0,
            'total_anterior': 0,
            'diferencia_total': 0,
            'predicciones_ml': predicciones_ml,
            'metodo': 'Machine Learning',
            'error': 'Datos insuficientes para análisis'
        }
    
    # Agrupar por semana y plato
    df_ventas['semana'] = df_ventas['fecha'].dt.isocalendar().week
    df_ventas['año'] = df_ventas['fecha'].dt.year
    
    hoy = date.today()
    semana_actual = hoy.isocalendar()[1]
    año_actual = hoy.year
    
    # Ventas de la semana actual
    ventas_semana_actual = df_ventas[
        (df_ventas['semana'] == semana_actual) & 
        (df_ventas['año'] == año_actual)
    ]
    
    # Ventas de la semana anterior (mismo año) o año anterior
    ventas_semana_anterior = df_ventas[
        ((df_ventas['semana'] == semana_actual - 1) & (df_ventas['año'] == año_actual)) |
        ((df_ventas['semana'] == semana_actual) & (df_ventas['año'] == año_actual - 1))
    ]
    
    # Agrupar por plato
    ventas_actuales_dict = ventas_semana_actual.groupby('plato_nombre')['ventas'].sum().to_dict()
    ventas_anterior_dict = ventas_semana_anterior.groupby('plato_nombre')['ventas'].sum().to_dict()
    
    # Generar sugerencias basadas en ML
    sugerencias = []
    todos_platos = set(list(ventas_actuales_dict.keys()) + list(ventas_anterior_dict.keys()))
    
    for plato in todos_platos:
        actual = int(ventas_actuales_dict.get(plato, 0))
        anterior = int(ventas_anterior_dict.get(plato, 0))
        
        if anterior > 0:
            diferencia = actual - anterior
            porcentaje = (diferencia / anterior) * 100 if anterior > 0 else 0
            
            if diferencia > 0:
                sugerencias.append({
                    'plato': plato,
                    'tipo': 'aumento',
                    'actual': actual,
                    'anterior': anterior,
                    'diferencia': diferencia,
                    'porcentaje': round(porcentaje, 2),
                    'mensaje': f"Vendiste {diferencia} más que el período anterior ({porcentaje:.1f}% más)"
                })
            elif diferencia < 0:
                sugerencias.append({
                    'plato': plato,
                    'tipo': 'disminucion',
                    'actual': actual,
                    'anterior': anterior,
                    'diferencia': abs(diferencia),
                    'porcentaje': round(abs(porcentaje), 2),
                    'mensaje': f"Vendiste {abs(diferencia)} menos que el período anterior ({abs(porcentaje):.1f}% menos)"
                })
        elif actual > 0:
            sugerencias.append({
                'plato': plato,
                'tipo': 'nuevo',
                'actual': actual,
                'anterior': 0,
                'diferencia': actual,
                'porcentaje': 100,
                'mensaje': f"Nuevo plato vendido esta semana: {actual} unidades"
            })
    
    # Comparación de platos
    comparacion_platos = []
    for plato in todos_platos:
        actual = int(ventas_actuales_dict.get(plato, 0))
        anterior = int(ventas_anterior_dict.get(plato, 0))
        diferencia = actual - anterior
        porcentaje_cambio = ((diferencia / anterior) * 100) if anterior > 0 else (100 if actual > 0 else 0)
        comparacion_platos.append({
            'plato': plato,
            'actual': actual,
            'anterior': anterior,
            'diferencia': diferencia,
            'porcentaje_cambio': round(porcentaje_cambio, 2)
        })
    comparacion_platos.sort(key=lambda x: abs(x['diferencia']), reverse=True)
    
    return {
        'semana_actual': semana_actual,
        'año_actual': año_actual,
        'año_anterior': año_actual - 1,
        'ventas_actuales': {k: int(v) for k, v in ventas_actuales_dict.items()},
        'ventas_anterior': {k: int(v) for k, v in ventas_anterior_dict.items()},
        'sugerencias': sorted(sugerencias, key=lambda x: abs(x.get('diferencia', 0)), reverse=True),
        'comparacion_platos': comparacion_platos,
        'total_actual': int(sum(ventas_actuales_dict.values())),
        'total_anterior': int(sum(ventas_anterior_dict.values())),
        'diferencia_total': int(sum(ventas_actuales_dict.values()) - sum(ventas_anterior_dict.values())),
        'predicciones_ml': predicciones_ml,
        'metodo': 'Machine Learning'
    }


def analizar_ventas_mensuales(plato_id: Optional[int] = None) -> Dict:
    """
    Analiza las ventas mensuales usando Machine Learning
    """
    if not ML_DISPONIBLE:
        raise RuntimeError("Machine Learning no está disponible. El módulo requiere ML para funcionar.")
    
    # Obtener datos históricos usando ML
    df_ventas = preparar_datos_ventas(plato_id=plato_id, dias_historia=365)
    
    if df_ventas.empty:
        return {
            'mes_actual': date.today().month,
            'mes_anterior': date.today().month - 1 if date.today().month > 1 else 12,
            'año_actual': date.today().year,
            'ventas_actuales': {},
            'ventas_anterior': {},
            'sugerencias': [],
            'comparacion_platos': [],
            'total_actual': 0,
            'total_anterior': 0,
            'diferencia_total': 0,
            'metodo': 'Machine Learning',
            'error': 'Datos insuficientes para análisis'
        }
    
    # Agrupar por mes y plato
    df_ventas['mes'] = df_ventas['fecha'].dt.month
    df_ventas['año'] = df_ventas['fecha'].dt.year
    
    hoy = date.today()
    mes_actual = hoy.month
    año_actual = hoy.year
    
    # Mes anterior
    if mes_actual == 1:
        mes_anterior = 12
        año_anterior = año_actual - 1
    else:
        mes_anterior = mes_actual - 1
        año_anterior = año_actual
    
    # Ventas del mes actual
    ventas_mes_actual = df_ventas[
        (df_ventas['mes'] == mes_actual) & 
        (df_ventas['año'] == año_actual)
    ]
    
    # Ventas del mes anterior
    ventas_mes_anterior = df_ventas[
        (df_ventas['mes'] == mes_anterior) & 
        (df_ventas['año'] == año_anterior)
    ]
    
    # Agrupar por plato
    ventas_actuales_dict = ventas_mes_actual.groupby('plato_nombre')['ventas'].sum().to_dict()
    ventas_anterior_dict = ventas_mes_anterior.groupby('plato_nombre')['ventas'].sum().to_dict()
    
    # Generar sugerencias
    sugerencias = []
    todos_platos = set(list(ventas_actuales_dict.keys()) + list(ventas_anterior_dict.keys()))
    
    for plato in todos_platos:
        actual = int(ventas_actuales_dict.get(plato, 0))
        anterior = int(ventas_anterior_dict.get(plato, 0))
        
        if anterior > 0:
            diferencia = actual - anterior
            porcentaje = (diferencia / anterior) * 100 if anterior > 0 else 0
            sugerencias.append({
                'plato': plato,
                'actual': actual,
                'anterior': anterior,
                'diferencia': diferencia,
                'porcentaje': round(porcentaje, 2)
            })
    
    # Comparación de platos
    comparacion_platos = []
    for plato in todos_platos:
        actual = int(ventas_actuales_dict.get(plato, 0))
        anterior = int(ventas_anterior_dict.get(plato, 0))
        diferencia = actual - anterior
        porcentaje_cambio = ((diferencia / anterior) * 100) if anterior > 0 else (100 if actual > 0 else 0)
        comparacion_platos.append({
            'plato': plato,
            'actual': actual,
            'anterior': anterior,
            'diferencia': diferencia,
            'porcentaje_cambio': round(porcentaje_cambio, 2)
        })
    comparacion_platos.sort(key=lambda x: abs(x['diferencia']), reverse=True)
    
    return {
        'mes_actual': mes_actual,
        'mes_anterior': mes_anterior,
        'año_actual': año_actual,
        'año_anterior': año_anterior,
        'ventas_actuales': {k: int(v) for k, v in ventas_actuales_dict.items()},
        'ventas_anterior': {k: int(v) for k, v in ventas_anterior_dict.items()},
        'sugerencias': sorted(sugerencias, key=lambda x: abs(x['diferencia']), reverse=True),
        'comparacion_platos': comparacion_platos,
        'total_actual': int(sum(ventas_actuales_dict.values())),
        'total_anterior': int(sum(ventas_anterior_dict.values())),
        'diferencia_total': int(sum(ventas_actuales_dict.values()) - sum(ventas_anterior_dict.values())),
        'metodo': 'Machine Learning'
    }


# ========== ANÁLISIS DE MERMAS CON ML ==========

def analizar_mermas_mensuales() -> Dict:
    """
    Analiza las mermas del mes actual usando Machine Learning
    Agrupa por usuario, causa, proveedor y tipo
    """
    if not ML_DISPONIBLE:
        raise RuntimeError("Machine Learning no está disponible. El módulo requiere ML para funcionar.")
    
    # Obtener datos históricos usando ML
    df_mermas = preparar_datos_mermas(dias_historia=365)
    
    if df_mermas.empty:
        return {
            'mes': date.today().month,
            'año': date.today().year,
            'total_mermas': 0,
            'total_registros': 0,
            'por_usuario': {},
            'por_causa': {},
            'por_proveedor': {},
            'por_tipo': {},
            'alertas': [],
            'promedio_usuario': 0,
            'metodo': 'Machine Learning',
            'error': 'Datos insuficientes para análisis'
        }
    
    # Filtrar por mes actual
    hoy = date.today()
    df_mermas['mes'] = df_mermas['fecha'].dt.month
    df_mermas['año'] = df_mermas['fecha'].dt.year
    
    mermas_mes = df_mermas[
        (df_mermas['mes'] == hoy.month) & 
        (df_mermas['año'] == hoy.year)
    ]
    
    # Si no hay datos del mes actual, usar el mes más reciente
    if len(mermas_mes) == 0:
        mermas_mes = df_mermas.nlargest(1, 'fecha')
        if len(mermas_mes) > 0:
            mes_analisis = mermas_mes.iloc[0]['mes']
            año_analisis = mermas_mes.iloc[0]['año']
            mermas_mes = df_mermas[
                (df_mermas['mes'] == mes_analisis) & 
                (df_mermas['año'] == año_analisis)
            ]
        else:
            mes_analisis = hoy.month
            año_analisis = hoy.year
    else:
        mes_analisis = hoy.month
        año_analisis = hoy.year
    
    # Análisis por causa (tenemos causa_nombre en el DataFrame)
    if 'causa_nombre' in mermas_mes.columns:
        mermas_por_causa = mermas_mes.groupby('causa_nombre').agg({
            'cantidad': 'sum',
            'causa_id': 'count'
        }).rename(columns={'causa_id': 'registros'}).to_dict('index')
        mermas_por_causa = {k: {'cantidad': float(v['cantidad']), 'registros': int(v['registros'])} 
                           for k, v in mermas_por_causa.items()}
    else:
        mermas_por_causa = {}
    
    # Análisis por tipo
    if 'tipo_merma' in mermas_mes.columns:
        mermas_por_tipo = mermas_mes.groupby('tipo_merma').agg({
            'cantidad': 'sum',
            'tipo_merma': 'count'
        }).rename(columns={'tipo_merma': 'registros'}).to_dict('index')
        mermas_por_tipo = {k: {'cantidad': float(v['cantidad']), 'registros': int(v['registros'])} 
                          for k, v in mermas_por_tipo.items()}
    else:
        mermas_por_tipo = {}
    
    total_mermas = float(mermas_mes['cantidad'].sum())
    total_registros = len(mermas_mes)
    
    # Obtener datos adicionales desde la base de datos para usuario y proveedor
    mermas_db = Merma.objects.filter(
        fecha_registro__year=año_analisis,
        fecha_registro__month=mes_analisis
    ).select_related('id_usuario', 'id_causa', 'id_lote', 'id_plato_producido')
    
    mermas_por_usuario = defaultdict(lambda: {'cantidad': 0, 'registros': 0})
    for merma in mermas_db:
        usuario_nombre = merma.id_usuario.nombre
        mermas_por_usuario[usuario_nombre]['cantidad'] += float(merma.cantidad_desperdiciada)
        mermas_por_usuario[usuario_nombre]['registros'] += 1
    
    mermas_por_proveedor = defaultdict(lambda: {'cantidad': 0, 'registros': 0, 'lotes': set()})
    for merma in mermas_db.filter(tipo_merma='lote', id_lote__isnull=False):
        if merma.id_lote and merma.id_lote.id_detalle_compra:
            proveedor = merma.id_lote.id_detalle_compra.id_orden_compra.id_proveedor
            proveedor_nombre = proveedor.nombre_proveedor
            mermas_por_proveedor[proveedor_nombre]['cantidad'] += float(merma.cantidad_desperdiciada)
            mermas_por_proveedor[proveedor_nombre]['registros'] += 1
            mermas_por_proveedor[proveedor_nombre]['lotes'].add(merma.id_lote.id_lote)
    
    for proveedor in mermas_por_proveedor:
        mermas_por_proveedor[proveedor]['lotes'] = len(mermas_por_proveedor[proveedor]['lotes'])
    
    # Calcular promedios y alertas
    promedio_usuario = total_mermas / len(mermas_por_usuario) if mermas_por_usuario else 0
    alertas = []
    
    for usuario, datos in mermas_por_usuario.items():
        if promedio_usuario > 0 and datos['cantidad'] > promedio_usuario * 1.5:
            porcentaje = (datos['cantidad'] / promedio_usuario - 1) * 100
            alertas.append({
                'tipo': 'usuario',
                'entidad': usuario,
                'mensaje': f"El usuario {usuario} tiene {porcentaje:.1f}% más mermas que el promedio",
                'cantidad': datos['cantidad'],
                'promedio': promedio_usuario
            })
    
    if mermas_por_proveedor:
        total_proveedor = sum([m['cantidad'] for m in mermas_por_proveedor.values()])
        promedio_proveedor = total_proveedor / len(mermas_por_proveedor)
        
        for proveedor, datos in mermas_por_proveedor.items():
            if promedio_proveedor > 0 and datos['cantidad'] > promedio_proveedor * 1.5:
                porcentaje = (datos['cantidad'] / promedio_proveedor - 1) * 100
                alertas.append({
                    'tipo': 'proveedor',
                    'entidad': proveedor,
                    'mensaje': f"El proveedor {proveedor} tiene {porcentaje:.1f}% más mermas que el promedio. Revisar calidad de productos.",
                    'cantidad': datos['cantidad'],
                    'promedio': promedio_proveedor
                })
    
    return {
        'mes': mes_analisis,
        'año': año_analisis,
        'total_mermas': total_mermas,
        'total_registros': total_registros,
        'por_usuario': dict(mermas_por_usuario),
        'por_causa': mermas_por_causa,
        'por_proveedor': dict(mermas_por_proveedor),
        'por_tipo': mermas_por_tipo,
        'alertas': alertas,
        'promedio_usuario': promedio_usuario,
        'metodo': 'Machine Learning'
    }


def analizar_mermas_platos_producidos(fecha_desde: date = None, fecha_hasta: date = None) -> Dict:
    """
    Analiza las mermas de platos producidos en un rango de fechas
    Calcula qué platos se mermaron, cuántos, y a qué cantidades de insumos equivalen
    
    Args:
        fecha_desde: Fecha de inicio del análisis (default: hace 30 días)
        fecha_hasta: Fecha de fin del análisis (default: hoy)
    
    Returns:
        Dict con:
        - platos_mermados: Lista de dicts con información por plato
        - insumos_equivalentes: Dict con totales de insumos desperdiciados
        - resumen: Totales generales
        - periodo: Rango de fechas analizado
    """
    hoy = date.today()
    
    # Establecer fechas por defecto
    if fecha_desde is None:
        fecha_desde = hoy - timedelta(days=30)
    if fecha_hasta is None:
        fecha_hasta = hoy
    
    # Obtener mermas de platos en el rango de fechas
    mermas_platos = Merma.objects.filter(
        tipo_merma='plato',
        id_plato_producido__isnull=False,
        fecha_registro__gte=fecha_desde,
        fecha_registro__lte=fecha_hasta
    ).select_related(
        'id_plato_producido__id_plato',
        'id_causa',
        'id_usuario'
    )
    
    if not mermas_platos.exists():
        return {
            'platos_mermados': [],
            'insumos_equivalentes': {},
            'resumen': {
                'total_platos_mermados': 0,
                'total_cantidad_mermada': 0,
                'total_insumos_diferentes': 0,
                'costo_estimado': 0
            },
            'periodo': {
                'fecha_desde': fecha_desde,
                'fecha_hasta': fecha_hasta
            },
            'mensaje': 'No se encontraron mermas de platos en el período seleccionado.'
        }
    
    # Agrupar mermas por plato
    mermas_por_plato = defaultdict(lambda: {
        'plato': None,
        'cantidad_mermada': Decimal('0'),
        'registros': [],
        'causas': defaultdict(int)
    })
    
    for merma in mermas_platos:
        plato = merma.id_plato_producido.id_plato
        plato_id = plato.id_plato
        
        mermas_por_plato[plato_id]['plato'] = plato
        mermas_por_plato[plato_id]['cantidad_mermada'] += Decimal(str(merma.cantidad_desperdiciada))
        mermas_por_plato[plato_id]['registros'].append({
            'fecha': merma.fecha_registro,
            'cantidad': float(merma.cantidad_desperdiciada),
            'causa': merma.id_causa.nombre_causa,
            'usuario': merma.id_usuario.nombre
        })
        mermas_por_plato[plato_id]['causas'][merma.id_causa.nombre_causa] += 1
    
    # Calcular insumos equivalentes para cada plato
    platos_mermados = []
    insumos_equivalentes = defaultdict(lambda: {
        'insumo': None,
        'cantidad_total': Decimal('0'),
        'unidad_medida': '',
        'platos_afectados': set()
    })
    
    for plato_id, datos_plato in mermas_por_plato.items():
        plato = datos_plato['plato']
        cantidad_mermada = float(datos_plato['cantidad_mermada'])
        
        # Obtener insumos de la receta del plato
        recetas = Receta.objects.filter(id_plato=plato).select_related('id_insumo')
        
        insumos_plato = []
        if recetas.exists():
            # Usar la receta estándar
            for receta in recetas:
                insumo = receta.id_insumo
                cantidad_insumo = float(receta.cantidad_necesaria) * cantidad_mermada
                
                insumos_plato.append({
                    'insumo_id': insumo.id_insumo,
                    'insumo_nombre': insumo.nombre_insumo,
                    'cantidad': cantidad_insumo,
                    'unidad_medida': insumo.unidad_medida,
                    'cantidad_por_plato': float(receta.cantidad_necesaria)
                })
                
                # Acumular en el total de insumos equivalentes
                insumos_equivalentes[insumo.id_insumo]['insumo'] = insumo
                insumos_equivalentes[insumo.id_insumo]['cantidad_total'] += Decimal(str(cantidad_insumo))
                insumos_equivalentes[insumo.id_insumo]['unidad_medida'] = insumo.unidad_medida
                insumos_equivalentes[insumo.id_insumo]['platos_afectados'].add(plato.nombre_plato)
        else:
            # Si no hay receta, intentar obtener de los detalles de producción reales
            # Buscar un plato producido mermado para obtener sus detalles
            plato_producido_mermado = mermas_platos.filter(
                id_plato_producido__id_plato=plato
            ).first()
            
            if plato_producido_mermado and plato_producido_mermado.id_plato_producido:
                detalles_produccion = DetalleProduccionInsumo.objects.filter(
                    id_plato_producido=plato_producido_mermado.id_plato_producido
                ).select_related('id_insumo')
                
                for detalle in detalles_produccion:
                    insumo = detalle.id_insumo
                    cantidad_insumo = float(detalle.cantidad_usada) * cantidad_mermada
                    
                    insumos_plato.append({
                        'insumo_id': insumo.id_insumo,
                        'insumo_nombre': insumo.nombre_insumo,
                        'cantidad': cantidad_insumo,
                        'unidad_medida': insumo.unidad_medida,
                        'cantidad_por_plato': float(detalle.cantidad_usada)
                    })
                    
                    # Acumular en el total de insumos equivalentes
                    insumos_equivalentes[insumo.id_insumo]['insumo'] = insumo
                    insumos_equivalentes[insumo.id_insumo]['cantidad_total'] += Decimal(str(cantidad_insumo))
                    insumos_equivalentes[insumo.id_insumo]['unidad_medida'] = insumo.unidad_medida
                    insumos_equivalentes[insumo.id_insumo]['platos_afectados'].add(plato.nombre_plato)
        
        # Agregar información del plato mermado
        platos_mermados.append({
            'plato_id': plato.id_plato,
            'plato_nombre': plato.nombre_plato,
            'cantidad_mermada': cantidad_mermada,
            'cantidad_registros': len(datos_plato['registros']),
            'causas': dict(datos_plato['causas']),
            'insumos_equivalentes': insumos_plato,
            'registros': datos_plato['registros']
        })
    
    # Convertir insumos equivalentes a formato serializable
    insumos_equivalentes_list = []
    for insumo_id, datos_insumo in insumos_equivalentes.items():
        insumos_equivalentes_list.append({
            'insumo_id': insumo_id,
            'insumo_nombre': datos_insumo['insumo'].nombre_insumo,
            'cantidad_total': float(datos_insumo['cantidad_total']),
            'unidad_medida': datos_insumo['unidad_medida'],
            'platos_afectados': sorted(list(datos_insumo['platos_afectados'])),
            'cantidad_platos_afectados': len(datos_insumo['platos_afectados'])
        })
    
    # Ordenar por cantidad total descendente
    insumos_equivalentes_list.sort(key=lambda x: x['cantidad_total'], reverse=True)
    
    # Calcular resumen
    total_platos_mermados = len(platos_mermados)
    total_cantidad_mermada = sum(p['cantidad_mermada'] for p in platos_mermados)
    total_insumos_diferentes = len(insumos_equivalentes_list)
    
    return {
        'platos_mermados': platos_mermados,
        'insumos_equivalentes': insumos_equivalentes_list,
        'resumen': {
            'total_platos_mermados': total_platos_mermados,
            'total_cantidad_mermada': round(total_cantidad_mermada, 2),
            'total_insumos_diferentes': total_insumos_diferentes,
            'total_registros_mermas': mermas_platos.count()
        },
        'periodo': {
            'fecha_desde': fecha_desde,
            'fecha_hasta': fecha_hasta
        }
    }


def analizar_tendencias_mermas(meses_atras: int = 6) -> Dict:
    """
    Analiza las tendencias de mermas en los últimos N meses
    """
    hoy = date.today()
    mermas_mensuales = []
    
    for i in range(meses_atras):
        fecha = hoy - timedelta(days=30 * i)
        mes = fecha.month
        año = fecha.year
        
        mermas = Merma.objects.filter(
            fecha_registro__year=año,
            fecha_registro__month=mes
        )
        
        total = sum([float(m.cantidad_desperdiciada) for m in mermas])
        cantidad_registros = mermas.count()
        
        mermas_mensuales.append({
            'mes': mes,
            'año': año,
            'total': total,
            'registros': cantidad_registros,
            'promedio_por_registro': total / cantidad_registros if cantidad_registros > 0 else 0
        })
    
    mermas_mensuales.reverse()  # Del más antiguo al más reciente
    
    # Detectar tendencia
    if len(mermas_mensuales) >= 2:
        ultimo = mermas_mensuales[-1]['total']
        penultimo = mermas_mensuales[-2]['total']
        tendencia = 'aumentando' if ultimo > penultimo else 'disminuyendo' if ultimo < penultimo else 'estable'
        cambio_porcentaje = ((ultimo - penultimo) / penultimo * 100) if penultimo > 0 else 0
    else:
        tendencia = 'insuficiente_datos'
        cambio_porcentaje = 0
    
    return {
        'tendencias': mermas_mensuales,
        'tendencia_actual': tendencia,
        'cambio_porcentaje': round(cambio_porcentaje, 2)
    }


# ========== PROYECCIÓN DE COMPRAS ==========

def proyectar_compras_insumos(dias_proyeccion: int = 30, usar_ml: bool = True, nivel_datos: str = None, modelo_tipo: str = 'auto') -> List[Dict]:
    """
    Proyecta las compras necesarias de insumos usando SOLO Machine Learning
    NUEVO: Basado en predicciones de ventas multiplicadas por recetas
    
    Args:
        dias_proyeccion: Días a proyectar
        usar_ml: Siempre True - el módulo requiere ML
        nivel_datos: Nivel de datos ('rapido', 'estandar', 'optimo'). Si es None, usa el default.
        modelo_tipo: Tipo de modelo ML para predicciones de ventas ('auto', 'xgboost', 'lightgbm', etc.)
    """
    if not ML_DISPONIBLE:
        raise RuntimeError("Machine Learning no está disponible. El módulo requiere ML para funcionar.")
    
    # Usar SOLO ML - no hay fallback
    return recomendar_compras_ml(dias_proyeccion=dias_proyeccion, nivel_datos=nivel_datos, modelo_tipo=modelo_tipo)


# ========== DETECCIÓN DE ANOMALÍAS ==========

def detectar_anomalias_ventas(usar_ml: bool = True) -> List[Dict]:
    """
    Detecta anomalías en las ventas usando SOLO Machine Learning (Isolation Forest)
    
    Args:
        usar_ml: Siempre True - el módulo requiere ML
    """
    if not ML_DISPONIBLE:
        raise RuntimeError("Machine Learning no está disponible. El módulo requiere ML para funcionar.")
    
    # Usar SOLO ML - Isolation Forest
    return detectar_anomalias_ml_ventas(dias_analisis=60)


def detectar_anomalias_mermas(usar_ml: bool = True) -> List[Dict]:
    """
    Detecta anomalías en las mermas usando SOLO Machine Learning (Isolation Forest)
    
    Args:
        usar_ml: Siempre True - el módulo requiere ML
    """
    if not ML_DISPONIBLE:
        raise RuntimeError("Machine Learning no está disponible. El módulo requiere ML para funcionar.")
    
    # Usar SOLO ML - Isolation Forest
    return detectar_anomalias_ml_mermas(dias_analisis=60)


# ========== DASHBOARD GENERAL ==========

def obtener_insights_dashboard() -> Dict:
    """
    Genera insights generales para el dashboard de predicciones
    Si no hay datos del mes actual, usa los datos más recientes disponibles
    """
    hoy = date.today()
    
    try:
        # Ventas del mes (o mes más reciente con datos)
        ventas_mes = PlatoProducido.objects.filter(
            estado='venta',
            fecha_produccion__year=hoy.year,
            fecha_produccion__month=hoy.month
        ).count()
        
        # Si hay muy pocos datos del mes actual (< 5 ventas), usar el mes más reciente con más datos
        if ventas_mes < 5:
            # Buscar el mes con más ventas en los últimos 12 meses
            from django.db.models.functions import TruncMonth
            ventas_por_mes = PlatoProducido.objects.filter(
                estado='venta'
            ).annotate(
                mes=TruncMonth('fecha_produccion')
            ).values('mes').annotate(
                total=Count('id_plato_producido')
            ).order_by('-total')[:1]
            
            if ventas_por_mes:
                mes_mejor = ventas_por_mes[0]['mes']
                ventas_mes = ventas_por_mes[0]['total']
                # mes_mejor es un datetime truncado, extraer año y mes
                if hasattr(mes_mejor, 'year'):
                    hoy = date(mes_mejor.year, mes_mejor.month, 1)
                elif isinstance(mes_mejor, datetime):
                    hoy = mes_mejor.date().replace(day=1)
                else:
                    hoy = date.today()
            else:
                # Fallback: usar el mes más reciente
                ultima_venta = PlatoProducido.objects.filter(estado='venta').order_by('-fecha_produccion').first()
                if ultima_venta:
                    fecha_ultima = ultima_venta.fecha_produccion
                    ventas_mes = PlatoProducido.objects.filter(
                        estado='venta',
                        fecha_produccion__year=fecha_ultima.year,
                        fecha_produccion__month=fecha_ultima.month
                    ).count()
                else:
                    ventas_mes = PlatoProducido.objects.filter(estado='venta').count()
    except Exception as e:
        import traceback
        print(f"Error en ventas_mes: {e}")
        print(traceback.format_exc())
        ventas_mes = 0
    
    try:
        # Mermas del mes (o mes más reciente con datos)
        resultado_aggregate = Merma.objects.filter(
            fecha_registro__year=hoy.year,
            fecha_registro__month=hoy.month
        ).aggregate(total=Sum('cantidad_desperdiciada'))
        
        # Convertir Decimal a float de forma segura
        mermas_mes = float(resultado_aggregate['total']) if resultado_aggregate['total'] is not None else 0
        
        # Si no hay datos del mes actual, usar el mes más reciente
        if mermas_mes == 0:
            ultima_merma = Merma.objects.order_by('-fecha_registro').first()
            if ultima_merma:
                fecha_ultima = ultima_merma.fecha_registro
                resultado_aggregate = Merma.objects.filter(
                    fecha_registro__year=fecha_ultima.year,
                    fecha_registro__month=fecha_ultima.month
                ).aggregate(total=Sum('cantidad_desperdiciada'))
                mermas_mes = float(resultado_aggregate['total']) if resultado_aggregate['total'] is not None else 0
            else:
                # Si no hay ninguna merma, sumar todas las mermas históricas
                resultado_aggregate = Merma.objects.aggregate(total=Sum('cantidad_desperdiciada'))
                mermas_mes = float(resultado_aggregate['total']) if resultado_aggregate['total'] is not None else 0
    except Exception as e:
        import traceback
        print(f"Error en mermas_mes: {e}")
        print(traceback.format_exc())
        mermas_mes = 0
    
    try:
        # Platos más vendidos del mes (o mes más reciente con datos)
        platos_vendidos = list(PlatoProducido.objects.filter(
            estado='venta',
            fecha_produccion__year=hoy.year,
            fecha_produccion__month=hoy.month
        ).values('id_plato__nombre_plato').annotate(
            cantidad=Count('id_plato_producido')
        ).order_by('-cantidad')[:5])
        
        # Si hay muy pocos datos del mes actual, usar el mes con más datos
        if not platos_vendidos or len(platos_vendidos) < 2:
            # Buscar el mes con más ventas
            from django.db.models.functions import TruncMonth
            ventas_por_mes = PlatoProducido.objects.filter(
                estado='venta'
            ).annotate(
                mes=TruncMonth('fecha_produccion')
            ).values('mes').annotate(
                total=Count('id_plato_producido')
            ).order_by('-total')[:1]
            
            if ventas_por_mes:
                mes_mejor = ventas_por_mes[0]['mes']
                # Extraer año y mes del datetime truncado
                if isinstance(mes_mejor, datetime):
                    año_mejor = mes_mejor.year
                    mes_mejor_num = mes_mejor.month
                elif hasattr(mes_mejor, 'year'):
                    año_mejor = mes_mejor.year
                    mes_mejor_num = mes_mejor.month
                else:
                    año_mejor = None
                    mes_mejor_num = None
                
                if año_mejor and mes_mejor_num:
                    platos_vendidos = list(PlatoProducido.objects.filter(
                        estado='venta',
                        fecha_produccion__year=año_mejor,
                        fecha_produccion__month=mes_mejor_num
                    ).values('id_plato__nombre_plato').annotate(
                        cantidad=Count('id_plato_producido')
                    ).order_by('-cantidad')[:5])
                else:
                    # Si no se puede obtener año/mes, usar todas las ventas históricas
                    platos_vendidos = list(PlatoProducido.objects.filter(
                        estado='venta'
                    ).values('id_plato__nombre_plato').annotate(
                        cantidad=Count('id_plato_producido')
                    ).order_by('-cantidad')[:5])
            else:
                # Fallback: usar todas las ventas históricas
                platos_vendidos = list(PlatoProducido.objects.filter(
                    estado='venta'
                ).values('id_plato__nombre_plato').annotate(
                    cantidad=Count('id_plato_producido')
                ).order_by('-cantidad')[:5])
    except Exception as e:
        import traceback
        print(f"Error en platos_vendidos: {e}")
        print(traceback.format_exc())
        platos_vendidos = []
    
    try:
        # Análisis de ventas semanales
        analisis_semanal = analizar_ventas_semanales()
    except Exception as e:
        analisis_semanal = {
            'semana_actual': hoy.isocalendar()[1],
            'año_actual': hoy.year,
            'año_anterior': hoy.year - 1,
            'sugerencias': [],
            'total_actual': 0,
            'total_anterior': 0
        }
    
    try:
        # Análisis de mermas
        analisis_mermas = analizar_mermas_mensuales()
    except Exception:
        analisis_mermas = {
            'mes': hoy.month,
            'año': hoy.year,
            'total_mermas': 0,
            'total_registros': 0,
            'alertas': []
        }
    
    # OPTIMIZACIÓN: No ejecutar predicciones ML pesadas en el dashboard
    # Estas se ejecutarán solo cuando el usuario las solicite explícitamente
    # Esto mejora significativamente el tiempo de carga
    try:
        # Proyecciones de compra (versión ligera, sin ML)
        # Solo mostrar insumos con stock bajo basado en consumo reciente
        from inventario.models import Lote, DetalleProduccionInsumo
        # Sum ya está importado al inicio del archivo
        from datetime import timedelta
        
        insumos_urgentes = []
        fecha_limite = hoy - timedelta(days=30)
        
        # Obtener consumo reciente por insumo
        consumo_reciente = DetalleProduccionInsumo.objects.filter(
            fecha_uso__gte=fecha_limite
        ).values('id_insumo').annotate(
            consumo_total=Sum('cantidad_usada')
        )
        
        # Calcular stock actual por insumo
        stock_actual = Lote.objects.filter(
            cantidad_actual__gt=0
        ).values('id_insumo').annotate(
            stock_total=Sum('cantidad_actual')
        )
        
        # Crear diccionarios para búsqueda rápida
        consumo_dict = {item['id_insumo']: item['consumo_total'] for item in consumo_reciente}
        stock_dict = {item['id_insumo']: item['stock_total'] for item in stock_actual}
        
        # Identificar insumos urgentes (stock bajo o sin stock)
        for insumo in Insumo.objects.all()[:20]:  # Limitar a 20 para no sobrecargar
            stock = stock_dict.get(insumo.id_insumo, 0)
            consumo = consumo_dict.get(insumo.id_insumo, 0)
            
            if stock == 0 or (consumo > 0 and stock / max(consumo / 30, 1) < 7):
                insumos_urgentes.append({
                    'insumo_id': insumo.id_insumo,
                    'insumo_nombre': insumo.nombre_insumo,
                    'stock_actual': stock,
                    'urgencia': 'alta' if stock == 0 else 'media'
                })
                if len(insumos_urgentes) >= 5:
                    break
    except Exception as e:
        print(f"Error en proyecciones ligeras: {e}")
        insumos_urgentes = []
    
    # Anomalías y predicciones ML: NO ejecutar en dashboard (muy pesado)
    # Se ejecutarán solo cuando el usuario vaya a las páginas específicas
    anomalias_ventas = []
    anomalias_mermas = []
    predicciones_ventas_ml = {}
    predicciones_mermas_ml = {}
    predicciones_demanda_ml = []
    
    return {
        'ventas_mes': ventas_mes,
        'mermas_mes': float(mermas_mes),
        'platos_mas_vendidos': list(platos_vendidos),
        'analisis_semanal': analisis_semanal,
        'analisis_mermas': analisis_mermas,
        'insumos_urgentes': insumos_urgentes,
        'anomalias_ventas': anomalias_ventas,
        'anomalias_mermas': anomalias_mermas,
        'ml_disponible': ML_DISPONIBLE,
        'predicciones_ventas_ml': predicciones_ventas_ml,
        'predicciones_mermas_ml': predicciones_mermas_ml,
        'predicciones_demanda_ml': predicciones_demanda_ml
    }

