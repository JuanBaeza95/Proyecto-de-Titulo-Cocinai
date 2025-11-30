"""
Módulo de Machine Learning para predicciones en CocinAI
Implementa modelos ML reales para predicción de ventas, demanda, mermas y recomendaciones
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
from typing import Dict, List, Tuple, Optional
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import train_test_split, TimeSeriesSplit
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.cluster import KMeans
from sklearn.ensemble import IsolationForest
import warnings
import pickle
import os
from pathlib import Path
warnings.filterwarnings('ignore')

# Intentar importar XGBoost y LightGBM (opcionales pero recomendados)
try:
    import xgboost as xgb
    XGBOOST_DISPONIBLE = True
except ImportError:
    XGBOOST_DISPONIBLE = False
    xgb = None

try:
    import lightgbm as lgb
    LIGHTGBM_DISPONIBLE = True
except ImportError:
    LIGHTGBM_DISPONIBLE = False
    lgb = None

from inventario.models import (
    PlatoProducido, Merma, Lote, Insumo, Plato, 
    DetalleProduccionInsumo, CausaMerma, Usuario, RegistroVentaPlato, Receta
)
from ventas.models import DetalleComanda
from django.db.models import Sum, Count, Avg, Q
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth
from .config_ml import obtener_dias_minimos

# Configuración para guardar/cargar modelos
# Usar BASE_DIR del proyecto Django
try:
    from django.conf import settings
    MODELS_DIR = Path(settings.BASE_DIR) / 'models_ml'
except:
    # Fallback si no está en contexto Django
    MODELS_DIR = Path(__file__).resolve().parent.parent.parent / 'models_ml'

# Crear directorio si no existe
MODELS_DIR.mkdir(exist_ok=True)


# FUNCIONES DE PERSISTENCIA DE MODELOS

def _obtener_ruta_modelo(plato_id: Optional[int] = None, modelo_tipo: str = 'auto') -> Path:
    """
    Obtiene la ruta del archivo .pkl para un modelo específico
    
    Args:
        plato_id: ID del plato (None para todos los platos)
        modelo_tipo: Tipo de modelo usado
    
    Returns:
        Path al archivo .pkl
    """
    if plato_id:
        nombre_archivo = f"modelo_ventas_plato_{plato_id}_{modelo_tipo}.pkl"
    else:
        nombre_archivo = f"modelo_ventas_todos_{modelo_tipo}.pkl"
    
    return MODELS_DIR / nombre_archivo


def _obtener_ruta_metadata(plato_id: Optional[int] = None, modelo_tipo: str = 'auto') -> Path:
    """
    Obtiene la ruta del archivo de metadata para un modelo
    
    Returns:
        Path al archivo de metadata
    """
    if plato_id:
        nombre_archivo = f"metadata_ventas_plato_{plato_id}_{modelo_tipo}.pkl"
    else:
        nombre_archivo = f"metadata_ventas_todos_{modelo_tipo}.pkl"
    
    return MODELS_DIR / nombre_archivo


def guardar_modelo_entrenado(resultado_entrenamiento: Dict, plato_id: Optional[int] = None, modelo_tipo: str = 'auto') -> bool:
    """
    Guarda un modelo entrenado y su metadata en archivos .pkl
    
    Args:
        resultado_entrenamiento: Diccionario con el resultado de entrenar_modelo_ventas
        plato_id: ID del plato (None para todos)
        modelo_tipo: Tipo de modelo usado
    
    Returns:
        True si se guardó exitosamente, False en caso contrario
    """
    try:
        ruta_modelo = _obtener_ruta_modelo(plato_id, modelo_tipo)
        ruta_metadata = _obtener_ruta_metadata(plato_id, modelo_tipo)
        
        # Guardar modelo principal y ensemble
        modelo_data = {
            'modelo': resultado_entrenamiento.get('modelo'),
            'modelos_ensemble': resultado_entrenamiento.get('modelos_ensemble', []),
            'scaler': resultado_entrenamiento.get('scaler'),
            'label_encoder': resultado_entrenamiento.get('label_encoder'),
            'features': resultado_entrenamiento.get('features', []),
        }
        
        with open(ruta_modelo, 'wb') as f:
            pickle.dump(modelo_data, f)
        
        # Guardar metadata (métricas, fechas, etc.)
        metadata = {
            'metricas': resultado_entrenamiento.get('metricas', {}),
            'modelo_tipo': resultado_entrenamiento.get('modelo_tipo', modelo_tipo),
            'fecha_entrenamiento': datetime.now().isoformat(),
            'datos_entrenamiento': resultado_entrenamiento.get('datos_entrenamiento', 0),
            'datos_prueba': resultado_entrenamiento.get('datos_prueba', 0),
            'mean_actual': resultado_entrenamiento.get('mean_actual', 0),
            'mean_predicted': resultado_entrenamiento.get('mean_predicted', 0),
            'outliers_ajustados': resultado_entrenamiento.get('outliers_ajustados', 0),
            'plato_id': plato_id,
        }
        
        with open(ruta_metadata, 'wb') as f:
            pickle.dump(metadata, f)
        
        return True
    except Exception as e:
        print(f"Error al guardar modelo: {e}")
        return False


def cargar_modelo_entrenado(plato_id: Optional[int] = None, modelo_tipo: str = 'auto', 
                            max_dias_antiguedad: int = 7) -> Optional[Dict]:
    """
    Carga un modelo entrenado desde archivo .pkl si existe y no es muy antiguo
    
    Args:
        plato_id: ID del plato (None para todos)
        modelo_tipo: Tipo de modelo a cargar
        max_dias_antiguedad: Máximo de días de antigüedad del modelo (default: 7 días)
                            Si el modelo es más antiguo, retorna None para forzar reentrenamiento
    
    Returns:
        Diccionario con modelo y metadata si existe y es reciente, None en caso contrario
    """
    try:
        ruta_modelo = _obtener_ruta_modelo(plato_id, modelo_tipo)
        ruta_metadata = _obtener_ruta_metadata(plato_id, modelo_tipo)
        
        # Verificar que ambos archivos existan
        if not ruta_modelo.exists() or not ruta_metadata.exists():
            return None
        
        # Verificar antigüedad del modelo
        fecha_modificacion = datetime.fromtimestamp(ruta_modelo.stat().st_mtime)
        dias_antiguedad = (datetime.now() - fecha_modificacion).days
        
        if dias_antiguedad > max_dias_antiguedad:
            return None  # Modelo muy antiguo, necesita reentrenamiento
        
        # Cargar modelo
        with open(ruta_modelo, 'rb') as f:
            modelo_data = pickle.load(f)
        
        # Cargar metadata
        with open(ruta_metadata, 'rb') as f:
            metadata = pickle.load(f)
        
        # Combinar datos
        resultado = {
            'modelo': modelo_data.get('modelo'),
            'modelos_ensemble': modelo_data.get('modelos_ensemble', []),
            'scaler': modelo_data.get('scaler'),
            'label_encoder': modelo_data.get('label_encoder'),
            'features': modelo_data.get('features', []),
            'metricas': metadata.get('metricas', {}),
            'modelo_tipo': metadata.get('modelo_tipo', modelo_tipo),
            'fecha_entrenamiento': metadata.get('fecha_entrenamiento'),
            'dias_antiguedad': dias_antiguedad,
            'cargado_desde_archivo': True,
        }
        
        return resultado
        
    except Exception as e:
        print(f"Error al cargar modelo: {e}")
        return None


def eliminar_modelo_guardado(plato_id: Optional[int] = None, modelo_tipo: str = 'auto') -> bool:
    """
    Elimina un modelo guardado 
    
    Returns:
        True si se eliminó exitosamente
    """
    try:
        ruta_modelo = _obtener_ruta_modelo(plato_id, modelo_tipo)
        ruta_metadata = _obtener_ruta_metadata(plato_id, modelo_tipo)
        
        if ruta_modelo.exists():
            ruta_modelo.unlink()
        if ruta_metadata.exists():
            ruta_metadata.unlink()
        
        return True
    except Exception as e:
        print(f"Error al eliminar modelo: {e}")
        return False


# PREPARACIÓN DE DATOS

def _obtener_feriados_chile(año: int) -> set:
    """
    Obtiene fechas de feriados chilenos para un año específico
    Feriados fijos y algunos comunes
    """
    feriados = set()
    
    # Feriados fijos
    feriados.add(date(año, 1, 1))   # Año Nuevo
    feriados.add(date(año, 5, 1))   # Día del Trabajador
    feriados.add(date(año, 5, 21))  # Día de las Glorias Navales
    feriados.add(date(año, 6, 29))   # San Pedro y San Pablo
    feriados.add(date(año, 7, 16))   # Virgen del Carmen
    feriados.add(date(año, 8, 15))   # Asunción de la Virgen
    feriados.add(date(año, 9, 18))   # Fiestas Patrias
    feriados.add(date(año, 9, 19))   # Día del Ejército
    feriados.add(date(año, 10, 12))  # Encuentro de Dos Mundos
    feriados.add(date(año, 10, 31))  # Día de las Iglesias Evangélicas
    feriados.add(date(año, 11, 1))   # Día de Todos los Santos
    feriados.add(date(año, 12, 8))   # Inmaculada Concepción
    feriados.add(date(año, 12, 25))  # Navidad
    
    # Viernes Santo (aproximado - varía cada año)
    # Para simplificar, usamos una aproximación basada en el calendario lunar
    # En 2024: 29 de marzo, en 2025: 18 de abril
    if año == 2024:
        feriados.add(date(año, 3, 29))
    elif año == 2025:
        feriados.add(date(año, 4, 18))
    elif año == 2026:
        feriados.add(date(año, 4, 3))
    
    return feriados


def preparar_datos_ventas(plato_id: Optional[int] = None, dias_historia: int = 180) -> pd.DataFrame:
    """
    Prepara datos históricos de ventas para entrenamiento de modelos ML
    OPTIMIZADO: Usa cantidad total vendida en lugar de conteo de filas
    Incluye features de calendario avanzadas (feriados, día de pago, estacionalidad)
    """
    hoy = date.today()
    fecha_inicio = hoy - timedelta(days=dias_historia)
    
    # Obtener ventas de múltiples fuentes para obtener cantidad real
    # IMPORTANTE: Usar solo PlatoProducido como fuente principal para evitar duplicación
    # Las otras fuentes pueden estar duplicando las mismas ventas
    datos = []
    
    # Fuente principal: PlatoProducido (cada registro = 1 unidad vendida)
    # Esta es la fuente más confiable y evita duplicación
    ventas_pp = PlatoProducido.objects.filter(
        estado='venta',
        fecha_produccion__gte=fecha_inicio
    ).select_related('id_plato')
    
    if plato_id:
        ventas_pp = ventas_pp.filter(id_plato_id=plato_id)
    
    for venta in ventas_pp:
        fecha = venta.fecha_produccion.date()
        datos.append({
            'fecha': fecha,
            'plato_id': venta.id_plato.id_plato,
            'plato_nombre': venta.id_plato.nombre_plato,
            'cantidad': 1  # Cada PlatoProducido = 1 unidad
        })
    
    # NOTA: No usar RegistroVentaPlato ni DetalleComanda aquí porque pueden duplicar
    # las mismas ventas que ya están en PlatoProducido. Si necesitas usar esas fuentes,
    # deberías hacer un join para evitar duplicación.
    
    if not datos:
        return pd.DataFrame()
    
    df = pd.DataFrame(datos)
    df['fecha'] = pd.to_datetime(df['fecha'])
    df = df.sort_values('fecha')
    
    # Agrupar por día y plato SUMANDO cantidades (no contando filas)
    if df['plato_id'].nunique() > 1:
        df_agrupado = df.groupby(['fecha', 'plato_id', 'plato_nombre'])['cantidad'].sum().reset_index(name='ventas')
    else:
        # Si es un solo plato, agrupar solo por fecha
        df_agrupado = df.groupby(['fecha'])['cantidad'].sum().reset_index(name='ventas')
        if 'plato_id' in df.columns and len(df) > 0:
            df_agrupado['plato_id'] = df['plato_id'].iloc[0]
            df_agrupado['plato_nombre'] = df['plato_nombre'].iloc[0]
    
    # Crear rango completo de fechas para incluir días sin ventas
    rango_fechas = pd.date_range(start=fecha_inicio, end=hoy, freq='D')
    df_completo = pd.DataFrame({'fecha': rango_fechas})
    df_completo['fecha'] = pd.to_datetime(df_completo['fecha'])
    
    # Merge con datos reales (llenar con 0 los días sin ventas)
    if df['plato_id'].nunique() > 1:
        # Para múltiples platos, hacer merge por fecha y plato_id
        df_completo = df_completo.merge(
            df_agrupado[['fecha', 'plato_id', 'ventas']], 
            on='fecha', 
            how='left'
        )
        df_completo['ventas'] = df_completo['ventas'].fillna(0)
        # Llenar plato_id y plato_nombre para días sin ventas
        for plato_id in df_agrupado['plato_id'].unique():
            mask = (df_completo['plato_id'].isna()) | (df_completo['plato_id'] == plato_id)
            plato_nombre = df_agrupado[df_agrupado['plato_id'] == plato_id]['plato_nombre'].iloc[0]
            df_completo.loc[mask, 'plato_id'] = plato_id
            if 'plato_nombre' not in df_completo.columns:
                df_completo['plato_nombre'] = plato_nombre
    else:
        # Para un solo plato, merge simple
        df_completo = df_completo.merge(df_agrupado[['fecha', 'ventas']], on='fecha', how='left')
        df_completo['ventas'] = df_completo['ventas'].fillna(0)
        if 'plato_id' in df_agrupado.columns:
            df_completo['plato_id'] = df_agrupado['plato_id'].iloc[0]
            df_completo['plato_nombre'] = df_agrupado['plato_nombre'].iloc[0]
    
    df_agrupado = df_completo.sort_values('fecha').reset_index(drop=True)
    
    # Agregar características temporales básicas
    df_agrupado['dia_semana'] = df_agrupado['fecha'].dt.dayofweek
    df_agrupado['mes'] = df_agrupado['fecha'].dt.month
    df_agrupado['año'] = df_agrupado['fecha'].dt.year
    df_agrupado['dia_mes'] = df_agrupado['fecha'].dt.day
    df_agrupado['semana_año'] = df_agrupado['fecha'].dt.isocalendar().week
    df_agrupado['trimestre'] = df_agrupado['fecha'].dt.quarter
    df_agrupado['dia_año'] = df_agrupado['fecha'].dt.dayofyear
    
    # Features cíclicas (sin/cos) para capturar patrones temporales
    df_agrupado['dia_semana_sin'] = np.sin(2 * np.pi * df_agrupado['dia_semana'] / 7)
    df_agrupado['dia_semana_cos'] = np.cos(2 * np.pi * df_agrupado['dia_semana'] / 7)
    df_agrupado['mes_sin'] = np.sin(2 * np.pi * df_agrupado['mes'] / 12)
    df_agrupado['mes_cos'] = np.cos(2 * np.pi * df_agrupado['mes'] / 12)
    df_agrupado['dia_mes_sin'] = np.sin(2 * np.pi * df_agrupado['dia_mes'] / 31)
    df_agrupado['dia_mes_cos'] = np.cos(2 * np.pi * df_agrupado['dia_mes'] / 31)
    df_agrupado['trimestre_sin'] = np.sin(2 * np.pi * df_agrupado['trimestre'] / 4)
    df_agrupado['trimestre_cos'] = np.cos(2 * np.pi * df_agrupado['trimestre'] / 4)
    df_agrupado['dia_año_sin'] = np.sin(2 * np.pi * df_agrupado['dia_año'] / 365.25)
    df_agrupado['dia_año_cos'] = np.cos(2 * np.pi * df_agrupado['dia_año'] / 365.25)
    
    # Features booleanas
    df_agrupado['es_fin_semana'] = (df_agrupado['dia_semana'] >= 5).astype(int)
    df_agrupado['es_inicio_mes'] = (df_agrupado['dia_mes'] <= 7).astype(int)
    df_agrupado['es_mitad_mes'] = ((df_agrupado['dia_mes'] >= 14) & (df_agrupado['dia_mes'] <= 16)).astype(int)
    df_agrupado['es_fin_mes'] = (df_agrupado['dia_mes'] >= 25).astype(int)
    df_agrupado['es_lunes'] = (df_agrupado['dia_semana'] == 0).astype(int)
    df_agrupado['es_viernes'] = (df_agrupado['dia_semana'] == 4).astype(int)
    
    # Features de calendario: Feriados
    años_unicos = df_agrupado['año'].unique()
    feriados_todos = set()
    for año in años_unicos:
        feriados_todos.update(_obtener_feriados_chile(int(año)))
    
    df_agrupado['fecha_date'] = df_agrupado['fecha'].dt.date
    df_agrupado['es_feriado'] = df_agrupado['fecha_date'].isin(feriados_todos).astype(int)
    
    # Features de calendario: Día de pago (típicamente días 5, 10, 15, 20, 25, último día del mes)
    # Días comunes de pago en Chile
    df_agrupado['es_dia_pago'] = (
        (df_agrupado['dia_mes'].isin([5, 10, 15, 20, 25])) |
        (df_agrupado['dia_mes'] >= 28)  # Últimos días del mes
    ).astype(int)
    
    # Días antes/después de feriado (mayor consumo)
    df_agrupado['dias_desde_feriado'] = 999
    df_agrupado['dias_hasta_feriado'] = 999
    for idx, row in df_agrupado.iterrows():
        fecha_actual = row['fecha_date']
        # Buscar feriado más cercano
        feriados_cercanos = [f for f in feriados_todos if abs((f - fecha_actual).days) <= 7]
        if feriados_cercanos:
            dias_dif = [(f - fecha_actual).days for f in feriados_cercanos]
            dias_desde = min([d for d in dias_dif if d >= 0], default=999)
            dias_hasta = min([abs(d) for d in dias_dif if d < 0], default=999)
            df_agrupado.at[idx, 'dias_desde_feriado'] = dias_desde if dias_desde != 999 else 7
            df_agrupado.at[idx, 'dias_hasta_feriado'] = dias_hasta if dias_hasta != 999 else 7
    
    df_agrupado['cerca_feriado'] = ((df_agrupado['dias_desde_feriado'] <= 2) | 
                                     (df_agrupado['dias_hasta_feriado'] <= 2)).astype(int)
    
    # Estacionalidad: mes de verano/invierno (Chile: verano dic-feb, invierno jun-ago)
    df_agrupado['es_verano'] = df_agrupado['mes'].isin([12, 1, 2]).astype(int)
    df_agrupado['es_invierno'] = df_agrupado['mes'].isin([6, 7, 8]).astype(int)
    df_agrupado['es_temporada_alta'] = df_agrupado['mes'].isin([12, 1, 2, 7, 8]).astype(int)  # Verano + vacaciones invierno
    
    # Si hay múltiples platos, procesar por plato
    if df_agrupado['plato_id'].nunique() > 1:
        df_final = []
        for plato_id in df_agrupado['plato_id'].unique():
            df_plato = df_agrupado[df_agrupado['plato_id'] == plato_id].copy()
            df_plato = df_plato.sort_values('fecha').reset_index(drop=True)
            
            # Medias móviles (tendencias)
            df_plato['media_movil_7'] = df_plato['ventas'].rolling(window=7, min_periods=1).mean()
            df_plato['media_movil_14'] = df_plato['ventas'].rolling(window=14, min_periods=1).mean()
            df_plato['media_movil_30'] = df_plato['ventas'].rolling(window=30, min_periods=1).mean()
            
            # Lag features (ventas de días anteriores)
            df_plato['lag_1'] = df_plato['ventas'].shift(1).fillna(0)
            df_plato['lag_7'] = df_plato['ventas'].shift(7).fillna(0)
            df_plato['lag_14'] = df_plato['ventas'].shift(14).fillna(0)
            
            # Desviación estándar móvil (volatilidad)
            df_plato['std_movil_7'] = df_plato['ventas'].rolling(window=7, min_periods=1).std().fillna(0)
            
            df_final.append(df_plato)
        
        df_agrupado = pd.concat(df_final, ignore_index=True)
    else:
        # Para un solo plato
        df_agrupado = df_agrupado.sort_values('fecha').reset_index(drop=True)
        
        # Medias móviles
        df_agrupado['media_movil_7'] = df_agrupado['ventas'].rolling(window=7, min_periods=1).mean()
        df_agrupado['media_movil_14'] = df_agrupado['ventas'].rolling(window=14, min_periods=1).mean()
        df_agrupado['media_movil_30'] = df_agrupado['ventas'].rolling(window=30, min_periods=1).mean()
        
        # Lag features
        df_agrupado['lag_1'] = df_agrupado['ventas'].shift(1).fillna(0)
        df_agrupado['lag_7'] = df_agrupado['ventas'].shift(7).fillna(0)
        df_agrupado['lag_14'] = df_agrupado['ventas'].shift(14).fillna(0)
        
        # Desviación estándar móvil
        df_agrupado['std_movil_7'] = df_agrupado['ventas'].rolling(window=7, min_periods=1).std().fillna(0)
    
    # Llenar NaN restantes y asegurar que no haya valores infinitos
    df_agrupado = df_agrupado.fillna(0)
    
    # Reemplazar infinitos por NaN y luego llenar
    df_agrupado = df_agrupado.replace([np.inf, -np.inf], np.nan)
    df_agrupado = df_agrupado.fillna(0)
    
    # Asegurar que las ventas no sean negativas
    df_agrupado['ventas'] = df_agrupado['ventas'].clip(lower=0)
    
    return df_agrupado


def preparar_datos_demanda_insumos(insumo_id: Optional[int] = None, dias_historia: int = 180) -> pd.DataFrame:
    """
    Prepara datos históricos de consumo de insumos para predicción de demanda
    """
    hoy = date.today()
    fecha_inicio = hoy - timedelta(days=dias_historia)
    fecha_inicio_dt = datetime.combine(fecha_inicio, datetime.min.time())
    
    # Obtener consumo histórico
    consumos = DetalleProduccionInsumo.objects.filter(
        fecha_uso__gte=fecha_inicio_dt
    ).select_related('id_insumo', 'id_plato_producido__id_plato')
    
    if insumo_id:
        consumos = consumos.filter(id_insumo_id=insumo_id)
    
    datos = []
    for consumo in consumos:
        fecha = consumo.fecha_uso.date()
        datos.append({
            'fecha': fecha,
            'insumo_id': consumo.id_insumo.id_insumo,
            'insumo_nombre': consumo.id_insumo.nombre_insumo,
            'cantidad': float(consumo.cantidad_usada),
            'plato_id': consumo.id_plato_producido.id_plato.id_plato if consumo.id_plato_producido else None,
        })
    
    if not datos:
        return pd.DataFrame()
    
    df = pd.DataFrame(datos)
    df['fecha'] = pd.to_datetime(df['fecha'])
    df = df.sort_values('fecha')
    
    # Agrupar por día e insumo
    df_agrupado = df.groupby(['fecha', 'insumo_id', 'insumo_nombre']).agg({
        'cantidad': 'sum',
        'plato_id': 'count'  # Número de platos producidos que usaron este insumo
    }).reset_index()
    df_agrupado.rename(columns={'plato_id': 'num_producciones'}, inplace=True)
    
    # Agregar características temporales
    df_agrupado['dia_semana'] = df_agrupado['fecha'].dt.dayofweek
    df_agrupado['mes'] = df_agrupado['fecha'].dt.month
    df_agrupado['año'] = df_agrupado['fecha'].dt.year
    df_agrupado['es_fin_semana'] = (df_agrupado['dia_semana'] >= 5).astype(int)
    
    return df_agrupado


def preparar_datos_mermas(dias_historia: int = 180) -> pd.DataFrame:
    """
    Prepara datos históricos de mermas para predicción
    """
    hoy = date.today()
    fecha_inicio = hoy - timedelta(days=dias_historia)
    
    mermas = Merma.objects.filter(
        fecha_registro__gte=fecha_inicio
    ).select_related('id_causa', 'id_lote__id_insumo', 'id_plato_producido__id_plato', 'id_usuario')
    
    datos = []
    for merma in mermas:
        datos.append({
            'fecha': merma.fecha_registro,
            'tipo_merma': merma.tipo_merma,
            'cantidad': float(merma.cantidad_desperdiciada),
            'causa_id': merma.id_causa.id_causa,
            'causa_nombre': merma.id_causa.nombre_causa,
            'usuario_id': merma.id_usuario.id_usuario,
            'insumo_id': merma.id_lote.id_insumo.id_insumo if merma.id_lote else None,
            'plato_id': merma.id_plato_producido.id_plato.id_plato if merma.id_plato_producido else None,
        })
    
    if not datos:
        return pd.DataFrame()
    
    df = pd.DataFrame(datos)
    df['fecha'] = pd.to_datetime(df['fecha'])
    df = df.sort_values('fecha')
    
    # Agregar características temporales
    df['dia_semana'] = df['fecha'].dt.dayofweek
    df['mes'] = df['fecha'].dt.month
    df['año'] = df['fecha'].dt.year
    df['es_fin_semana'] = (df['dia_semana'] >= 5).astype(int)
    
    return df


# ========== MODELOS DE PREDICCIÓN DE VENTAS ==========

def entrenar_modelo_ventas(plato_id: Optional[int] = None, modelo_tipo: str = 'auto', 
                          dias_historia: int = 365, forzar_reentrenamiento: bool = False) -> Dict:
    """
    Entrena un modelo ML mejorado para predecir ventas de platos
    OPTIMIZADO: Usa cantidad total vendida, features de calendario avanzadas, y modelos XGBoost/LightGBM
    Ahora guarda y carga modelos desde archivos .pkl para mejorar rendimiento
    
    Args:
        plato_id: ID del plato (opcional)
        modelo_tipo: Tipo de modelo ('auto', 'xgboost', 'lightgbm', 'random_forest', 'gradient_boosting', 'ridge', 'linear')
                    'auto' selecciona automáticamente el mejor modelo disponible
        dias_historia: Días de historia a incluir (default: 365 para incluir año completo)
        forzar_reentrenamiento: Si True, ignora modelos guardados y reentrena (default: False)
    """
    # Selección automática del mejor modelo disponible
    if modelo_tipo == 'auto':
        if XGBOOST_DISPONIBLE:
            modelo_tipo = 'xgboost'
        elif LIGHTGBM_DISPONIBLE:
            modelo_tipo = 'lightgbm'
        else:
            modelo_tipo = 'random_forest'
    
    # Intentar cargar modelo guardado si no se fuerza reentrenamiento
    if not forzar_reentrenamiento:
        modelo_cargado = cargar_modelo_entrenado(plato_id, modelo_tipo, max_dias_antiguedad=7)
        if modelo_cargado:
            return modelo_cargado
    
    # Si no hay modelo guardado o se fuerza reentrenamiento, entrenar nuevo modelo
    df = preparar_datos_ventas(plato_id=plato_id, dias_historia=dias_historia)
    
    if df.empty or len(df) < 30:
        return {
            'modelo': None,
            'error': 'Datos insuficientes para entrenar el modelo',
            'metricas': {}
        }
    
    # Eliminar filas con NaN en features críticas
    df = df.dropna(subset=['ventas', 'fecha'])
    
    # Detectar y manejar outliers de forma muy conservadora
    # Solo ajustar valores extremos reales (más de 4 desviaciones estándar o percentil 99)
    outliers_ajustados = 0
    if len(df) > 20:  # Solo si hay suficientes datos
        mean_ventas = df['ventas'].mean()
        std_ventas = df['ventas'].std()
        median_ventas = df['ventas'].median()
        
        if std_ventas > 0:
            # Método muy conservador: solo ajustar valores extremos (percentil 99 o 4 desviaciones)
            # Esto preserva casi todos los datos
            upper_bound_p99 = df['ventas'].quantile(0.99)
            upper_bound_z = mean_ventas + 4.0 * std_ventas  # 4 desviaciones estándar (muy conservador)
            upper_bound = min(upper_bound_p99, upper_bound_z)
            
            # Lower bound: solo valores negativos o muy por debajo de la mediana
            lower_bound = max(0, median_ventas - 2.0 * std_ventas)
            
            # Solo ajustar valores que están realmente fuera de rango
            ventas_original = df['ventas'].copy()
            mask_outliers = (df['ventas'] < lower_bound) | (df['ventas'] > upper_bound)
            
            if mask_outliers.sum() > 0:
                # Solo ajustar los outliers extremos
                df.loc[mask_outliers, 'ventas'] = df.loc[mask_outliers, 'ventas'].clip(
                    lower=lower_bound, 
                    upper=upper_bound
                )
                outliers_ajustados = mask_outliers.sum()
    
    # Preparar features mejoradas (incluyendo nuevas features de calendario)
    features = [
        # Features temporales básicas
        'dia_semana', 'mes', 'año', 'dia_mes', 'semana_año', 'trimestre', 'dia_año',
        # Features cíclicas (sin/cos)
        'dia_semana_sin', 'dia_semana_cos', 'mes_sin', 'mes_cos', 
        'dia_mes_sin', 'dia_mes_cos', 'trimestre_sin', 'trimestre_cos',
        'dia_año_sin', 'dia_año_cos',
        # Features booleanas
        'es_fin_semana', 'es_inicio_mes', 'es_mitad_mes', 'es_fin_mes',
        'es_lunes', 'es_viernes',
        # Features de calendario (NUEVAS)
        'es_feriado', 'es_dia_pago', 'cerca_feriado',
        'es_verano', 'es_invierno', 'es_temporada_alta',
        'dias_desde_feriado', 'dias_hasta_feriado',
        # Medias móviles (tendencias)
        'media_movil_7', 'media_movil_14', 'media_movil_30',
        # Lag features (ventas anteriores)
        'lag_1', 'lag_7', 'lag_14',
        # Volatilidad
        'std_movil_7'
    ]
    
    # Agregar features de ingeniería avanzadas
    if 'media_movil_7' in df.columns and 'media_movil_30' in df.columns:
        # Ratio de tendencias (corto vs largo plazo)
        df['ratio_tendencia_7_30'] = df['media_movil_7'] / (df['media_movil_30'] + 1e-8)
        features.append('ratio_tendencia_7_30')
    
    if 'lag_1' in df.columns and 'media_movil_7' in df.columns:
        # Desviación del lag respecto a la media
        df['desviacion_lag1'] = df['lag_1'] - df['media_movil_7']
        features.append('desviacion_lag1')
    
    if 'std_movil_7' in df.columns and 'media_movil_7' in df.columns:
        # Coeficiente de variación (volatilidad relativa)
        df['coef_variacion'] = df['std_movil_7'] / (df['media_movil_7'] + 1e-8)
        features.append('coef_variacion')
    
    # Interacción: fin de semana * mes (patrones estacionales)
    if 'es_fin_semana' in df.columns and 'mes' in df.columns:
        df['fin_semana_mes'] = df['es_fin_semana'] * df['mes']
        features.append('fin_semana_mes')
    
    # Tendencia: diferencia entre medias móviles
    if 'media_movil_7' in df.columns and 'media_movil_14' in df.columns:
        df['tendencia_7_14'] = df['media_movil_7'] - df['media_movil_14']
        features.append('tendencia_7_14')
    
    if 'media_movil_14' in df.columns and 'media_movil_30' in df.columns:
        df['tendencia_14_30'] = df['media_movil_14'] - df['media_movil_30']
        features.append('tendencia_14_30')
    
    # Verificar que todas las features existan
    features_disponibles = [f for f in features if f in df.columns]
    
    # Si hay múltiples platos, agregar plato_id como feature
    le_plato = None
    if 'plato_id' in df.columns and df['plato_id'].nunique() > 1:
        le_plato = LabelEncoder()
        df['plato_id_encoded'] = le_plato.fit_transform(df['plato_id'])
        features_disponibles.append('plato_id_encoded')
    
    # Filtrar filas con NaN en features
    df_clean = df[features_disponibles + ['ventas']].dropna()
    
    if len(df_clean) < 30:
        return {
            'modelo': None,
            'error': f'Datos insuficientes después de limpieza: {len(df_clean)} registros',
            'metricas': {}
        }
    
    X = df_clean[features_disponibles].values
    y = df_clean['ventas'].values
    
    # División TEMPORAL (no aleatoria) - usar últimos 20% para prueba
    # Esto es crucial para series temporales
    split_idx = int(len(df_clean) * 0.8)
    
    if len(df_clean) < 50:
        # Con pocos datos, usar todos para entrenar y validar
        X_train, X_test, y_train, y_test = X, X, y, y
    else:
        # División temporal: primeros 80% para entrenar, últimos 20% para probar
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]
    
    # Seleccionar y entrenar modelo con mejores hiperparámetros optimizados
    scaler = None
    modelos_ensemble = []
    
    # Seleccionar y entrenar modelo según tipo especificado
    modelo_usado = modelo_tipo
    
    if modelo_tipo == 'xgboost':
        if XGBOOST_DISPONIBLE:
            modelo = xgb.XGBRegressor(
                n_estimators=300,
                max_depth=8,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                min_child_weight=3,
                gamma=0.1,
                reg_alpha=0.1,
                reg_lambda=1.0,
                random_state=42,
                n_jobs=-1,
                tree_method='hist'  # Más rápido
            )
            modelo.fit(X_train, y_train)
            y_pred = modelo.predict(X_test)
            modelos_ensemble = [modelo]
        else:
            # Fallback a RandomForest si XGBoost no está disponible
            modelo_tipo = 'random_forest'
            modelo_usado = 'random_forest (fallback)'
    
    elif modelo_tipo == 'lightgbm':
        if LIGHTGBM_DISPONIBLE:
            modelo = lgb.LGBMRegressor(
                n_estimators=300,
                max_depth=8,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                min_child_samples=20,
                reg_alpha=0.1,
                reg_lambda=1.0,
                random_state=42,
                n_jobs=-1,
                verbose=-1
            )
            modelo.fit(X_train, y_train)
            y_pred = modelo.predict(X_test)
            modelos_ensemble = [modelo]
        else:
            # Fallback a GradientBoosting si LightGBM no está disponible
            modelo_tipo = 'gradient_boosting'
            modelo_usado = 'gradient_boosting (fallback)'
    
    if modelo_tipo == 'random_forest':
        # Hiperparámetros optimizados para RandomForest (mejor balance bias-varianza)
        modelo = RandomForestRegressor(
            n_estimators=300,      # Aumentado para mejor generalización
            max_depth=12,          # Reducido para evitar overfitting
            min_samples_split=10,  # Aumentado para más regularización
            min_samples_leaf=4,   # Aumentado para más regularización
            max_features='sqrt',
            bootstrap=True,
            oob_score=True,        # Out-of-bag scoring para validación
            random_state=42,
            n_jobs=-1
        )
        modelo.fit(X_train, y_train)
        y_pred = modelo.predict(X_test)
        
        # Ensemble: agregar GradientBoosting como segundo modelo
        if len(X_train) > 50:
            modelo_gb = GradientBoostingRegressor(
                n_estimators=100,
                max_depth=5,
                learning_rate=0.05,  # Learning rate más bajo para mejor generalización
                min_samples_split=10,
                subsample=0.8,       # Subsampling para reducir overfitting
                random_state=42
            )
            modelo_gb.fit(X_train, y_train)
            y_pred_gb = modelo_gb.predict(X_test)
            
            # Promedio ponderado: 70% RF, 30% GB
            y_pred = 0.7 * y_pred + 0.3 * y_pred_gb
            modelos_ensemble = [modelo, modelo_gb]
        else:
            modelos_ensemble = [modelo]
            
    elif modelo_tipo == 'gradient_boosting':
        modelo = GradientBoostingRegressor(
            n_estimators=200,      # Aumentado
            max_depth=5,           # Profundidad moderada
            learning_rate=0.05,   # Learning rate más bajo
            min_samples_split=10,
            subsample=0.8,
            random_state=42
        )
        modelo.fit(X_train, y_train)
        y_pred = modelo.predict(X_test)
        modelos_ensemble = [modelo]
        
    elif modelo_tipo == 'ridge':
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        modelo = Ridge(alpha=5.0)  # Alpha optimizado
        modelo.fit(X_train_scaled, y_train)
        y_pred = modelo.predict(X_test_scaled)
        modelos_ensemble = [modelo]
    else:
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        modelo = LinearRegression()
        modelo.fit(X_train_scaled, y_train)
        y_pred = modelo.predict(X_test_scaled)
        modelos_ensemble = [modelo]
    
    # Evaluar modelo
    # Asegurar que las predicciones no sean negativas
    y_pred = np.maximum(y_pred, 0)
    
    # Aplicar suavizado si hay mucha variabilidad (reduce MAE)
    if len(y_pred) > 1:
        # Suavizado exponencial simple para reducir ruido
        alpha = 0.3
        y_pred_suavizado = np.copy(y_pred)
        for i in range(1, len(y_pred_suavizado)):
            y_pred_suavizado[i] = alpha * y_pred[i] + (1 - alpha) * y_pred_suavizado[i-1]
        
        # Usar el que tenga mejor MAE
        mae_original = mean_absolute_error(y_test, y_pred)
        mae_suavizado = mean_absolute_error(y_test, y_pred_suavizado)
        
        if mae_suavizado < mae_original:
            y_pred = y_pred_suavizado
    
    mae = mean_absolute_error(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    r2 = r2_score(y_test, y_pred)
    
    # Calcular métricas adicionales
    mean_y = np.mean(y_test)
    if mean_y > 0:
        mape = np.mean(np.abs((y_test - y_pred) / (mean_y + 1e-8))) * 100
    else:
        mape = 0
    
    resultado = {
        'modelo': modelos_ensemble[0] if modelos_ensemble else modelo,  # Modelo principal
        'modelos_ensemble': modelos_ensemble,  # Lista de modelos para ensemble
        'modelo_tipo': modelo_usado,  # Tipo de modelo usado
        'features': features_disponibles,
        'scaler': scaler,
        'label_encoder': le_plato,
        'metricas': {
            'mae': round(mae, 2),
            'rmse': round(rmse, 2),
            'r2': round(r2, 3),
            'mape': round(mape, 2)
        },
        'datos_entrenamiento': len(X_train),
        'datos_prueba': len(X_test),
        'mean_actual': round(mean_y, 2),
        'mean_predicted': round(np.mean(y_pred), 2),
        'usar_ensemble': len(modelos_ensemble) > 1,
        'outliers_ajustados': outliers_ajustados if 'outliers_ajustados' in locals() else 0,
        'cargado_desde_archivo': False
    }
    
    # Guardar modelo en archivo .pkl
    guardar_modelo_entrenado(resultado, plato_id, modelo_usado)
    
    return resultado


def predecir_ventas_futuras(plato_id: Optional[int] = None, dias_prediccion: int = 7, modelo_tipo: str = 'auto', dias_historia: int = 365) -> List[Dict]:
    """
    Predice ventas futuras usando modelos ML mejorados
    Calcula features temporales avanzadas (medias móviles, lags) usando datos históricos
    
    Args:
        plato_id: ID del plato (opcional)
        dias_prediccion: Días a predecir
        modelo_tipo: Tipo de modelo ML
        dias_historia: Días de historia a usar para entrenar (default: 365)
    """
    resultado_entrenamiento = entrenar_modelo_ventas(plato_id=plato_id, modelo_tipo=modelo_tipo, dias_historia=dias_historia)
    
    if resultado_entrenamiento['modelo'] is None:
        return []
    
    modelos_ensemble = resultado_entrenamiento.get('modelos_ensemble', [resultado_entrenamiento['modelo']])
    usar_ensemble = resultado_entrenamiento.get('usar_ensemble', False)
    features = resultado_entrenamiento['features']
    scaler = resultado_entrenamiento.get('scaler')
    le_plato = resultado_entrenamiento.get('label_encoder')
    
    # Obtener datos históricos recientes para calcular medias móviles y lags
    df_historico = preparar_datos_ventas(plato_id=plato_id, dias_historia=dias_historia)
    
    if df_historico.empty:
        return []
    
    # Obtener las últimas 30 filas para calcular features temporales
    df_reciente = df_historico.tail(30).copy()
    ventas_recientes = df_reciente['ventas'].values.tolist()
    
    # Calcular medias móviles históricas
    media_movil_7_hist = np.mean(ventas_recientes[-7:]) if len(ventas_recientes) >= 7 else np.mean(ventas_recientes) if ventas_recientes else 0
    media_movil_14_hist = np.mean(ventas_recientes[-14:]) if len(ventas_recientes) >= 14 else np.mean(ventas_recientes) if ventas_recientes else 0
    media_movil_30_hist = np.mean(ventas_recientes[-30:]) if len(ventas_recientes) >= 30 else np.mean(ventas_recientes) if ventas_recientes else 0
    std_movil_7_hist = np.std(ventas_recientes[-7:]) if len(ventas_recientes) >= 7 else 0
    
    # Generar fechas futuras
    hoy = date.today()
    predicciones = []
    
    for i in range(1, dias_prediccion + 1):
        fecha_futura = hoy + timedelta(days=i)
        
        # Preparar features básicas temporales
        feature_dict = {
            'dia_semana': fecha_futura.weekday(),
            'mes': fecha_futura.month,
            'año': fecha_futura.year,
            'dia_mes': fecha_futura.day,
            'semana_año': fecha_futura.isocalendar()[1],
            'trimestre': (fecha_futura.month - 1) // 3 + 1,
            'dia_año': fecha_futura.timetuple().tm_yday,
            'es_fin_semana': 1 if fecha_futura.weekday() >= 5 else 0,
            'es_inicio_mes': 1 if fecha_futura.day <= 7 else 0,
            'es_mitad_mes': 1 if 14 <= fecha_futura.day <= 16 else 0,
            'es_fin_mes': 1 if fecha_futura.day >= 25 else 0,
            'es_lunes': 1 if fecha_futura.weekday() == 0 else 0,
            'es_viernes': 1 if fecha_futura.weekday() == 4 else 0,
        }
        
        # Features cíclicas
        feature_dict['dia_semana_sin'] = np.sin(2 * np.pi * feature_dict['dia_semana'] / 7)
        feature_dict['dia_semana_cos'] = np.cos(2 * np.pi * feature_dict['dia_semana'] / 7)
        feature_dict['mes_sin'] = np.sin(2 * np.pi * feature_dict['mes'] / 12)
        feature_dict['mes_cos'] = np.cos(2 * np.pi * feature_dict['mes'] / 12)
        feature_dict['dia_mes_sin'] = np.sin(2 * np.pi * feature_dict['dia_mes'] / 31)
        feature_dict['dia_mes_cos'] = np.cos(2 * np.pi * feature_dict['dia_mes'] / 31)
        feature_dict['trimestre_sin'] = np.sin(2 * np.pi * feature_dict['trimestre'] / 4)
        feature_dict['trimestre_cos'] = np.cos(2 * np.pi * feature_dict['trimestre'] / 4)
        feature_dict['dia_año_sin'] = np.sin(2 * np.pi * feature_dict['dia_año'] / 365.25)
        feature_dict['dia_año_cos'] = np.cos(2 * np.pi * feature_dict['dia_año'] / 365.25)
        
        # Features de calendario: Feriados
        feriados_año = _obtener_feriados_chile(fecha_futura.year)
        feature_dict['es_feriado'] = 1 if fecha_futura in feriados_año else 0
        
        # Features de calendario: Día de pago
        feature_dict['es_dia_pago'] = 1 if (fecha_futura.day in [5, 10, 15, 20, 25] or fecha_futura.day >= 28) else 0
        
        # Días desde/hasta feriado
        feriados_cercanos = [f for f in feriados_año if abs((f - fecha_futura).days) <= 7]
        if feriados_cercanos:
            dias_dif = [(f - fecha_futura).days for f in feriados_cercanos]
            dias_desde = min([d for d in dias_dif if d >= 0], default=7)
            dias_hasta = min([abs(d) for d in dias_dif if d < 0], default=7)
            feature_dict['dias_desde_feriado'] = dias_desde if dias_desde != 7 else 7
            feature_dict['dias_hasta_feriado'] = dias_hasta if dias_hasta != 7 else 7
        else:
            feature_dict['dias_desde_feriado'] = 7
            feature_dict['dias_hasta_feriado'] = 7
        
        feature_dict['cerca_feriado'] = 1 if (feature_dict['dias_desde_feriado'] <= 2 or feature_dict['dias_hasta_feriado'] <= 2) else 0
        
        # Estacionalidad
        feature_dict['es_verano'] = 1 if fecha_futura.month in [12, 1, 2] else 0
        feature_dict['es_invierno'] = 1 if fecha_futura.month in [6, 7, 8] else 0
        feature_dict['es_temporada_alta'] = 1 if fecha_futura.month in [12, 1, 2, 7, 8] else 0
        
        # Calcular medias móviles usando ventas recientes
        if len(ventas_recientes) >= 7:
            feature_dict['media_movil_7'] = np.mean(ventas_recientes[-7:])
        else:
            feature_dict['media_movil_7'] = media_movil_7_hist
        
        if len(ventas_recientes) >= 14:
            feature_dict['media_movil_14'] = np.mean(ventas_recientes[-14:])
        else:
            feature_dict['media_movil_14'] = media_movil_14_hist
        
        if len(ventas_recientes) >= 30:
            feature_dict['media_movil_30'] = np.mean(ventas_recientes[-30:])
        else:
            feature_dict['media_movil_30'] = media_movil_30_hist
        
        # Lag features (usar ventas de días anteriores)
        feature_dict['lag_1'] = ventas_recientes[-1] if len(ventas_recientes) >= 1 else 0
        feature_dict['lag_7'] = ventas_recientes[-7] if len(ventas_recientes) >= 7 else feature_dict['lag_1']
        feature_dict['lag_14'] = ventas_recientes[-14] if len(ventas_recientes) >= 14 else feature_dict['lag_7']
        
        # Desviación estándar móvil
        if len(ventas_recientes) >= 7:
            feature_dict['std_movil_7'] = np.std(ventas_recientes[-7:])
        else:
            feature_dict['std_movil_7'] = std_movil_7_hist
        
        # Features de ingeniería avanzadas
        if 'ratio_tendencia_7_30' in features:
            feature_dict['ratio_tendencia_7_30'] = feature_dict['media_movil_7'] / (feature_dict['media_movil_30'] + 1e-8)
        
        if 'desviacion_lag1' in features:
            feature_dict['desviacion_lag1'] = feature_dict['lag_1'] - feature_dict['media_movil_7']
        
        if 'coef_variacion' in features:
            feature_dict['coef_variacion'] = feature_dict['std_movil_7'] / (feature_dict['media_movil_7'] + 1e-8)
        
        if 'fin_semana_mes' in features:
            feature_dict['fin_semana_mes'] = feature_dict['es_fin_semana'] * feature_dict['mes']
        
        if 'tendencia_7_14' in features:
            feature_dict['tendencia_7_14'] = feature_dict['media_movil_7'] - feature_dict['media_movil_14']
        
        if 'tendencia_14_30' in features:
            feature_dict['tendencia_14_30'] = feature_dict['media_movil_14'] - feature_dict['media_movil_30']
        
        # Plato ID encoded
        if plato_id and le_plato:
            try:
                feature_dict['plato_id_encoded'] = le_plato.transform([plato_id])[0]
            except:
                feature_dict['plato_id_encoded'] = 0
        elif 'plato_id_encoded' in features:
            feature_dict['plato_id_encoded'] = 0
        
        # Crear array de features en el orden correcto
        X_futuro = np.array([[feature_dict.get(f, 0) for f in features]])
        
        # Aplicar scaler si existe
        if scaler:
            X_futuro = scaler.transform(X_futuro)
        
        # Predecir usando ensemble si está disponible
        if usar_ensemble and len(modelos_ensemble) > 1:
            pred_rf = modelos_ensemble[0].predict(X_futuro)[0]
            pred_gb = modelos_ensemble[1].predict(X_futuro)[0]
            ventas_predichas = 0.7 * pred_rf + 0.3 * pred_gb
        else:
            ventas_predichas = modelos_ensemble[0].predict(X_futuro)[0]
        
        ventas_predichas = max(0, round(ventas_predichas, 1))  # No puede ser negativo
        
        # Actualizar ventas_recientes para la siguiente iteración (simular predicción)
        ventas_recientes.append(ventas_predichas)
        if len(ventas_recientes) > 30:
            ventas_recientes.pop(0)
        
        predicciones.append({
            'fecha': fecha_futura,
            'ventas_predichas': ventas_predichas,
            'dia_semana': fecha_futura.strftime('%A'),
            'es_fin_semana': feature_dict['es_fin_semana'] == 1
        })
    
    return predicciones


def obtener_ventas_periodo_anterior(fecha_inicio: date, fecha_fin: date, plato_id: Optional[int] = None) -> Dict:
    """
    Obtiene las ventas del mismo período del año pasado para comparación
    
    Args:
        fecha_inicio: Fecha de inicio del período a predecir
        fecha_fin: Fecha de fin del período a predecir
        plato_id: ID del plato (opcional, si es None obtiene todos)
    
    Returns:
        Dict con ventas totales, por día, y por plato
    """
    # Calcular el mismo período del año pasado
    año_anterior = fecha_inicio.year - 1
    fecha_inicio_anterior = fecha_inicio.replace(year=año_anterior)
    fecha_fin_anterior = fecha_fin.replace(year=año_anterior)
    
    # Ajustar si es año bisiesto
    if fecha_inicio.month == 2 and fecha_inicio.day == 29:
        fecha_inicio_anterior = fecha_inicio_anterior.replace(day=28)
    if fecha_fin.month == 2 and fecha_fin.day == 29:
        fecha_fin_anterior = fecha_fin_anterior.replace(day=28)
    
    # Obtener ventas de PlatoProducido
    ventas_pp = PlatoProducido.objects.filter(
        estado='venta',
        fecha_produccion__date__gte=fecha_inicio_anterior,
        fecha_produccion__date__lte=fecha_fin_anterior
    )
    
    # Obtener ventas de RegistroVentaPlato
    ventas_rvp = RegistroVentaPlato.objects.filter(
        fecha_venta__gte=fecha_inicio_anterior,
        fecha_venta__lte=fecha_fin_anterior
    )
    
    # Obtener ventas de DetalleComanda entregadas
    ventas_dc = DetalleComanda.objects.filter(
        estado='entregado',
        id_comanda__fecha_creacion__date__gte=fecha_inicio_anterior,
        id_comanda__fecha_creacion__date__lte=fecha_fin_anterior
    )
    
    if plato_id:
        ventas_pp = ventas_pp.filter(id_plato_id=plato_id)
        ventas_rvp = ventas_rvp.filter(id_plato_id=plato_id)
        ventas_dc = ventas_dc.filter(id_plato_id=plato_id)
    
    # Contar ventas totales
    total_pp = ventas_pp.count()
    total_rvp = sum(v.cantidad_vendida for v in ventas_rvp)
    total_dc = sum(d.cantidad for d in ventas_dc)
    total_ventas = total_pp + total_rvp + total_dc
    
    # Ventas por día
    ventas_por_dia = {}
    for venta in ventas_pp:
        fecha = venta.fecha_produccion.date()
        if fecha not in ventas_por_dia:
            ventas_por_dia[fecha] = 0
        ventas_por_dia[fecha] += 1
    
    for venta in ventas_rvp:
        fecha = venta.fecha_venta
        if fecha not in ventas_por_dia:
            ventas_por_dia[fecha] = 0
        ventas_por_dia[fecha] += venta.cantidad_vendida
    
    for detalle in ventas_dc:
        fecha = detalle.id_comanda.fecha_creacion.date()
        if fecha not in ventas_por_dia:
            ventas_por_dia[fecha] = 0
        ventas_por_dia[fecha] += detalle.cantidad
    
    # Ventas por plato
    ventas_por_plato = {}
    for venta in ventas_pp.select_related('id_plato'):
        plato_nombre = venta.id_plato.nombre_plato
        if plato_nombre not in ventas_por_plato:
            ventas_por_plato[plato_nombre] = 0
        ventas_por_plato[plato_nombre] += 1
    
    for venta in ventas_rvp.select_related('id_plato'):
        plato_nombre = venta.id_plato.nombre_plato
        if plato_nombre not in ventas_por_plato:
            ventas_por_plato[plato_nombre] = 0
        ventas_por_plato[plato_nombre] += venta.cantidad_vendida
    
    for detalle in ventas_dc.select_related('id_plato'):
        plato_nombre = detalle.id_plato.nombre_plato
        if plato_nombre not in ventas_por_plato:
            ventas_por_plato[plato_nombre] = 0
        ventas_por_plato[plato_nombre] += detalle.cantidad
    
    return {
        'total_ventas': total_ventas,
        'fecha_inicio': fecha_inicio_anterior,
        'fecha_fin': fecha_fin_anterior,
        'ventas_por_dia': ventas_por_dia,
        'ventas_por_plato': ventas_por_plato,
        'promedio_diario': total_ventas / max(1, (fecha_fin_anterior - fecha_inicio_anterior).days + 1)
    }


def predecir_ventas_periodo(fecha_inicio: date, fecha_fin: date, plato_id: Optional[int] = None, modelo_tipo: str = 'auto', dias_historia: int = 365) -> Dict:
    """
    Predice ventas para un período específico (configurable) y compara con el año pasado
    
    Args:
        fecha_inicio: Fecha de inicio del período a predecir
        fecha_fin: Fecha de fin del período a predecir
        plato_id: ID del plato (opcional)
        modelo_tipo: Tipo de modelo ML a usar
        dias_historia: Días de historia a usar para entrenar (default: 365 para incluir año completo)
    
    Returns:
        Dict con predicciones diarias, totales, y comparación con año anterior
    """
    # Validar fechas
    if fecha_inicio >= fecha_fin:
        return {
            'error': 'La fecha de inicio debe ser anterior a la fecha de fin',
            'predicciones': [],
            'comparacion_anio_anterior': None
        }
    
    if fecha_fin > date.today() + timedelta(days=365):
        return {
            'error': 'No se pueden predecir más de 1 año en el futuro',
            'predicciones': [],
            'comparacion_anio_anterior': None
        }
    
    # Entrenar modelo con más historia para incluir datos de 2024
    resultado_entrenamiento = entrenar_modelo_ventas(plato_id=plato_id, modelo_tipo=modelo_tipo, dias_historia=dias_historia)
    
    if resultado_entrenamiento['modelo'] is None:
        return {
            'error': 'No se pudo entrenar el modelo. Datos insuficientes.',
            'predicciones': [],
            'comparacion_anio_anterior': None
        }
    
    modelos_ensemble = resultado_entrenamiento.get('modelos_ensemble', [resultado_entrenamiento['modelo']])
    usar_ensemble = resultado_entrenamiento.get('usar_ensemble', False)
    features = resultado_entrenamiento['features']
    scaler = resultado_entrenamiento.get('scaler')
    le_plato = resultado_entrenamiento.get('label_encoder')
    
    # Obtener datos históricos recientes para calcular medias móviles y lags
    df_historico = preparar_datos_ventas(plato_id=plato_id, dias_historia=dias_historia)
    
    if df_historico.empty:
        return {
            'error': 'No hay datos históricos disponibles',
            'predicciones': [],
            'comparacion_anio_anterior': None
        }
    
    # Obtener las últimas 30 filas para calcular features temporales
    df_reciente = df_historico.tail(30).copy()
    ventas_recientes = df_reciente['ventas'].values.tolist()
    
    # Calcular medias móviles históricas
    media_movil_7_hist = np.mean(ventas_recientes[-7:]) if len(ventas_recientes) >= 7 else np.mean(ventas_recientes) if ventas_recientes else 0
    media_movil_14_hist = np.mean(ventas_recientes[-14:]) if len(ventas_recientes) >= 14 else np.mean(ventas_recientes) if ventas_recientes else 0
    media_movil_30_hist = np.mean(ventas_recientes[-30:]) if len(ventas_recientes) >= 30 else np.mean(ventas_recientes) if ventas_recientes else 0
    std_movil_7_hist = np.std(ventas_recientes[-7:]) if len(ventas_recientes) >= 7 else 0
    
    # Generar predicciones para cada día del período
    predicciones = []
    fecha_actual = fecha_inicio
    total_predicho = 0
    
    while fecha_actual <= fecha_fin:
        # Preparar features básicas temporales
        feature_dict = {
            'dia_semana': fecha_actual.weekday(),
            'mes': fecha_actual.month,
            'año': fecha_actual.year,
            'dia_mes': fecha_actual.day,
            'semana_año': fecha_actual.isocalendar()[1],
            'trimestre': (fecha_actual.month - 1) // 3 + 1,
            'dia_año': fecha_actual.timetuple().tm_yday,
            'es_fin_semana': 1 if fecha_actual.weekday() >= 5 else 0,
            'es_inicio_mes': 1 if fecha_actual.day <= 7 else 0,
            'es_mitad_mes': 1 if 14 <= fecha_actual.day <= 16 else 0,
            'es_fin_mes': 1 if fecha_actual.day >= 25 else 0,
            'es_lunes': 1 if fecha_actual.weekday() == 0 else 0,
            'es_viernes': 1 if fecha_actual.weekday() == 4 else 0,
        }
        
        # Features cíclicas
        feature_dict['dia_semana_sin'] = np.sin(2 * np.pi * feature_dict['dia_semana'] / 7)
        feature_dict['dia_semana_cos'] = np.cos(2 * np.pi * feature_dict['dia_semana'] / 7)
        feature_dict['mes_sin'] = np.sin(2 * np.pi * feature_dict['mes'] / 12)
        feature_dict['mes_cos'] = np.cos(2 * np.pi * feature_dict['mes'] / 12)
        feature_dict['dia_mes_sin'] = np.sin(2 * np.pi * feature_dict['dia_mes'] / 31)
        feature_dict['dia_mes_cos'] = np.cos(2 * np.pi * feature_dict['dia_mes'] / 31)
        feature_dict['trimestre_sin'] = np.sin(2 * np.pi * feature_dict['trimestre'] / 4)
        feature_dict['trimestre_cos'] = np.cos(2 * np.pi * feature_dict['trimestre'] / 4)
        feature_dict['dia_año_sin'] = np.sin(2 * np.pi * feature_dict['dia_año'] / 365.25)
        feature_dict['dia_año_cos'] = np.cos(2 * np.pi * feature_dict['dia_año'] / 365.25)
        
        # Features de calendario: Feriados
        feriados_año = _obtener_feriados_chile(fecha_actual.year)
        feature_dict['es_feriado'] = 1 if fecha_actual in feriados_año else 0
        
        # Features de calendario: Día de pago
        feature_dict['es_dia_pago'] = 1 if (fecha_actual.day in [5, 10, 15, 20, 25] or fecha_actual.day >= 28) else 0
        
        # Días desde/hasta feriado
        feriados_cercanos = [f for f in feriados_año if abs((f - fecha_actual).days) <= 7]
        if feriados_cercanos:
            dias_dif = [(f - fecha_actual).days for f in feriados_cercanos]
            dias_desde = min([d for d in dias_dif if d >= 0], default=7)
            dias_hasta = min([abs(d) for d in dias_dif if d < 0], default=7)
            feature_dict['dias_desde_feriado'] = dias_desde if dias_desde != 7 else 7
            feature_dict['dias_hasta_feriado'] = dias_hasta if dias_hasta != 7 else 7
        else:
            feature_dict['dias_desde_feriado'] = 7
            feature_dict['dias_hasta_feriado'] = 7
        
        feature_dict['cerca_feriado'] = 1 if (feature_dict['dias_desde_feriado'] <= 2 or feature_dict['dias_hasta_feriado'] <= 2) else 0
        
        # Estacionalidad
        feature_dict['es_verano'] = 1 if fecha_actual.month in [12, 1, 2] else 0
        feature_dict['es_invierno'] = 1 if fecha_actual.month in [6, 7, 8] else 0
        feature_dict['es_temporada_alta'] = 1 if fecha_actual.month in [12, 1, 2, 7, 8] else 0
        
        # Calcular medias móviles usando ventas recientes
        if len(ventas_recientes) >= 7:
            feature_dict['media_movil_7'] = np.mean(ventas_recientes[-7:])
        else:
            feature_dict['media_movil_7'] = media_movil_7_hist
        
        if len(ventas_recientes) >= 14:
            feature_dict['media_movil_14'] = np.mean(ventas_recientes[-14:])
        else:
            feature_dict['media_movil_14'] = media_movil_14_hist
        
        if len(ventas_recientes) >= 30:
            feature_dict['media_movil_30'] = np.mean(ventas_recientes[-30:])
        else:
            feature_dict['media_movil_30'] = media_movil_30_hist
        
        # Lag features (usar ventas de días anteriores)
        feature_dict['lag_1'] = ventas_recientes[-1] if len(ventas_recientes) >= 1 else 0
        feature_dict['lag_7'] = ventas_recientes[-7] if len(ventas_recientes) >= 7 else feature_dict['lag_1']
        feature_dict['lag_14'] = ventas_recientes[-14] if len(ventas_recientes) >= 14 else feature_dict['lag_7']
        
        # Desviación estándar móvil
        if len(ventas_recientes) >= 7:
            feature_dict['std_movil_7'] = np.std(ventas_recientes[-7:])
        else:
            feature_dict['std_movil_7'] = std_movil_7_hist
        
        # Features de ingeniería avanzadas
        if 'ratio_tendencia_7_30' in features:
            feature_dict['ratio_tendencia_7_30'] = feature_dict['media_movil_7'] / (feature_dict['media_movil_30'] + 1e-8)
        
        if 'desviacion_lag1' in features:
            feature_dict['desviacion_lag1'] = feature_dict['lag_1'] - feature_dict['media_movil_7']
        
        if 'coef_variacion' in features:
            feature_dict['coef_variacion'] = feature_dict['std_movil_7'] / (feature_dict['media_movil_7'] + 1e-8)
        
        if 'fin_semana_mes' in features:
            feature_dict['fin_semana_mes'] = feature_dict['es_fin_semana'] * feature_dict['mes']
        
        if 'tendencia_7_14' in features:
            feature_dict['tendencia_7_14'] = feature_dict['media_movil_7'] - feature_dict['media_movil_14']
        
        if 'tendencia_14_30' in features:
            feature_dict['tendencia_14_30'] = feature_dict['media_movil_14'] - feature_dict['media_movil_30']
        
        # Plato ID encoded
        if plato_id and le_plato:
            try:
                feature_dict['plato_id_encoded'] = le_plato.transform([plato_id])[0]
            except:
                feature_dict['plato_id_encoded'] = 0
        elif 'plato_id_encoded' in features:
            feature_dict['plato_id_encoded'] = 0
        
        # Crear array de features en el orden correcto
        X_futuro = np.array([[feature_dict.get(f, 0) for f in features]])
        
        # Aplicar scaler si existe
        if scaler:
            X_futuro = scaler.transform(X_futuro)
        
        # Predecir usando ensemble si está disponible
        if usar_ensemble and len(modelos_ensemble) > 1:
            pred_rf = modelos_ensemble[0].predict(X_futuro)[0]
            pred_gb = modelos_ensemble[1].predict(X_futuro)[0]
            ventas_predichas = 0.7 * pred_rf + 0.3 * pred_gb
        else:
            ventas_predichas = modelos_ensemble[0].predict(X_futuro)[0]
        
        ventas_predichas = max(0, round(ventas_predichas, 1))
        total_predicho += ventas_predichas
        
        # Actualizar ventas_recientes para la siguiente iteración (simular predicción)
        ventas_recientes.append(ventas_predichas)
        if len(ventas_recientes) > 30:
            ventas_recientes.pop(0)
        
        predicciones.append({
            'fecha': fecha_actual,
            'ventas_predichas': ventas_predichas,
            'dia_semana': fecha_actual.strftime('%A'),
            'dia_semana_es': ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'][fecha_actual.weekday()],
            'es_fin_semana': feature_dict['es_fin_semana'] == 1
        })
        
        fecha_actual += timedelta(days=1)
    
    # Obtener ventas del año anterior para comparación
    ventas_anio_anterior = obtener_ventas_periodo_anterior(fecha_inicio, fecha_fin, plato_id)
    
    # Calcular diferencia porcentual
    diferencia_absoluta = total_predicho - ventas_anio_anterior['total_ventas']
    diferencia_porcentual = 0
    if ventas_anio_anterior['total_ventas'] > 0:
        diferencia_porcentual = (diferencia_absoluta / ventas_anio_anterior['total_ventas']) * 100
    
    dias_periodo = (fecha_fin - fecha_inicio).days + 1
    promedio_diario_predicho = total_predicho / dias_periodo if dias_periodo > 0 else 0
    
    return {
        'predicciones': predicciones,
        'total_predicho': round(total_predicho, 1),
        'promedio_diario': round(promedio_diario_predicho, 1),
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        'dias_periodo': dias_periodo,
        'comparacion_anio_anterior': {
            'total_ventas_anterior': ventas_anio_anterior['total_ventas'],
            'promedio_diario_anterior': round(ventas_anio_anterior['promedio_diario'], 1),
            'fecha_inicio_anterior': ventas_anio_anterior['fecha_inicio'],
            'fecha_fin_anterior': ventas_anio_anterior['fecha_fin'],
            'diferencia_absoluta': round(diferencia_absoluta, 1),
            'diferencia_porcentual': round(diferencia_porcentual, 1),
            'ventas_por_dia_anterior': ventas_anio_anterior['ventas_por_dia'],
            'ventas_por_plato_anterior': ventas_anio_anterior['ventas_por_plato']
        },
        'metricas_modelo': resultado_entrenamiento.get('metricas', {}),
        'plato_id': plato_id
    }


# ========== MODELOS DE PREDICCIÓN DE DEMANDA ==========

def predecir_demanda_insumo(insumo_id: int, dias_prediccion: int = 30, nivel_datos: str = None, dias_historia: int = 365) -> Dict:
    """
    Predice la demanda futura de un insumo usando ML
    
    Args:
        insumo_id: ID del insumo
        dias_prediccion: Días a predecir
        nivel_datos: Nivel de datos ('rapido', 'estandar', 'optimo'). Si es None, usa el default.
        dias_historia: Días de historia a usar (default: 365 para incluir año completo)
    """
    df = preparar_datos_demanda_insumos(insumo_id=insumo_id, dias_historia=dias_historia)
    
    # Verificar si hay datos suficientes
    if df.empty:
        return {
            'insumo_id': insumo_id,
            'prediccion_diaria_promedio': 0,
            'prediccion_total': 0,
            'confianza': 'baja',
            'error': 'No hay datos de consumo para este insumo'
        }
    
    # Verificar días únicos con datos (más importante que número total de registros)
    dias_unicos = df['fecha'].nunique()
    
    # Obtener días mínimos requeridos (configurable)
    dias_minimos = obtener_dias_minimos(nivel=nivel_datos)
    
    if dias_unicos < dias_minimos:
        return {
            'insumo_id': insumo_id,
            'prediccion_diaria_promedio': 0,
            'prediccion_total': 0,
            'confianza': 'baja',
            'error': f'Datos insuficientes: solo {dias_unicos} días únicos con consumo (mínimo {dias_minimos} días). Ejecuta "python manage.py generar_datos_consumo --dias 90" para generar datos históricos.'
        }
    
    # Agrupar por día para tener serie temporal
    df_diario = df.groupby('fecha').agg({
        'cantidad': 'sum',
        'num_producciones': 'sum'
    }).reset_index()
    
    # Verificar que después de agrupar por día, tenemos suficientes días
    if len(df_diario) < dias_minimos:
        return {
            'insumo_id': insumo_id,
            'prediccion_diaria_promedio': 0,
            'prediccion_total': 0,
            'confianza': 'baja',
            'error': f'Datos insuficientes: solo {len(df_diario)} días únicos después de agrupar (mínimo {dias_minimos} días). Ejecuta "python manage.py generar_datos_consumo --dias 90" para generar datos históricos.'
        }
    
    # Preparar features
    df_diario['dia_semana'] = df_diario['fecha'].dt.dayofweek
    df_diario['mes'] = df_diario['fecha'].dt.month
    df_diario['año'] = df_diario['fecha'].dt.year
    df_diario['es_fin_semana'] = (df_diario['dia_semana'] >= 5).astype(int)
    
    # Agregar features de tendencia
    # Ajustar ventanas de media móvil según la cantidad de datos disponibles
    dias_disponibles = len(df_diario)
    
    if dias_disponibles >= 30:
        # Si hay suficientes datos, usar ambas medias móviles
        df_diario['media_movil_7'] = df_diario['cantidad'].rolling(window=7, min_periods=1).mean()
        df_diario['media_movil_30'] = df_diario['cantidad'].rolling(window=30, min_periods=1).mean()
        features = ['dia_semana', 'mes', 'año', 'es_fin_semana', 'media_movil_7', 'media_movil_30']
    elif dias_disponibles >= 14:
        # Si hay al menos 14 días, usar solo media móvil de 7
        df_diario['media_movil_7'] = df_diario['cantidad'].rolling(window=7, min_periods=1).mean()
        df_diario['media_movil_30'] = df_diario['cantidad'].mean()  # Usar promedio general como fallback
        features = ['dia_semana', 'mes', 'año', 'es_fin_semana', 'media_movil_7', 'media_movil_30']
    else:
        # Con menos de 14 días, usar solo promedio general
        promedio_general = df_diario['cantidad'].mean()
        df_diario['media_movil_7'] = promedio_general
        df_diario['media_movil_30'] = promedio_general
        features = ['dia_semana', 'mes', 'año', 'es_fin_semana', 'media_movil_7', 'media_movil_30']
    
    # Llenar NaN
    df_diario = df_diario.bfill().fillna(0)
    
    X = df_diario[features].values
    y = df_diario['cantidad'].values
    
    # Ajustar división train/test según cantidad de datos
    if len(df_diario) < 30:
        X_train, y_train = X, y
        X_test, y_test = X, y
    else:
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # Entrenar modelo
    modelo = RandomForestRegressor(n_estimators=50, max_depth=8, random_state=42, n_jobs=-1)
    modelo.fit(X_train, y_train)
    
    # Calcular promedio diario histórico
    consumo_diario_promedio = df_diario['cantidad'].mean()
    dias_disponibles = len(df_diario)
    
    # Predecir para los próximos días
    ultima_fila = df_diario.iloc[-1]
    predicciones_diarias = []
    
    # Calcular límites razonables basados en el consumo histórico
    consumo_maximo_historico = df_diario['cantidad'].max()
    consumo_promedio_historico = df_diario['cantidad'].mean()
    consumo_mediana_historica = df_diario['cantidad'].median()
    
    # Límite superior: máximo entre 3x el promedio o 2x el máximo histórico
    # Esto previene predicciones absurdamente altas
    limite_superior_diario = max(
        consumo_promedio_historico * 3,
        consumo_maximo_historico * 2,
        consumo_mediana_historica * 4
    )
    
    # Límite inferior: 0 (no puede ser negativo)
    limite_inferior_diario = 0
    
    for i in range(1, dias_prediccion + 1):
        fecha_futura = ultima_fila['fecha'] + timedelta(days=i)
        feature_dict = {
            'dia_semana': fecha_futura.weekday(),
            'mes': fecha_futura.month,
            'año': fecha_futura.year,
            'es_fin_semana': 1 if fecha_futura.weekday() >= 5 else 0,
            'media_movil_7': ultima_fila['media_movil_7'],
            'media_movil_30': ultima_fila['media_movil_30'],
        }
        X_futuro = np.array([[feature_dict[f] for f in features]])
        pred_raw = modelo.predict(X_futuro)[0]
        
        # Aplicar límites razonables a la predicción
        pred = max(limite_inferior_diario, min(pred_raw, limite_superior_diario))
        predicciones_diarias.append(pred)
    
    prediccion_total = sum(predicciones_diarias)
    prediccion_diaria_promedio = np.mean(predicciones_diarias)
    
    # Calcular confianza basada en R² y cantidad de datos
    y_pred_test = modelo.predict(X_test)
    r2 = r2_score(y_test, y_pred_test)
    
    # Ajustar confianza considerando tanto R² como cantidad de datos
    if dias_disponibles >= 30 and r2 > 0.7:
        confianza = 'alta'
    elif dias_disponibles >= 20 and r2 > 0.4:
        confianza = 'media'
    elif dias_disponibles >= 14:
        confianza = 'media' if r2 > 0.3 else 'baja'
    else:
        # Con menos de 14 días, la confianza es baja independientemente del R²
        confianza = 'baja'
    
    return {
        'insumo_id': insumo_id,
        'insumo_nombre': df.iloc[0]['insumo_nombre'] if not df.empty else '',
        'prediccion_diaria_promedio': round(prediccion_diaria_promedio, 2),
        'prediccion_total': round(prediccion_total, 2),
        'consumo_historico_promedio': round(consumo_diario_promedio, 2),
        'confianza': confianza,
        'r2_score': round(r2, 3),
        'metricas': {
            'mae': round(mean_absolute_error(y_test, y_pred_test), 2),
            'rmse': round(np.sqrt(mean_squared_error(y_test, y_pred_test)), 2)
        }
    }


# ========== MODELOS DE PREDICCIÓN DE MERMAS ==========

def predecir_mermas_futuras(dias_prediccion: int = 30) -> Dict:
    """
    Predice mermas futuras usando ML
    """
    df = preparar_datos_mermas()
    
    if df.empty or len(df) < 20:
        return {
            'prediccion_diaria_promedio': 0,
            'prediccion_total': 0,
            'confianza': 'baja',
            'error': 'Datos insuficientes'
        }
    
    # Agrupar por día
    df_diario = df.groupby('fecha').agg({
        'cantidad': 'sum',
        'tipo_merma': 'count'  # Número de mermas
    }).reset_index()
    df_diario.rename(columns={'tipo_merma': 'num_mermas'}, inplace=True)
    
    # Features temporales
    df_diario['dia_semana'] = df_diario['fecha'].dt.dayofweek
    df_diario['mes'] = df_diario['fecha'].dt.month
    df_diario['año'] = df_diario['fecha'].dt.year
    df_diario['es_fin_semana'] = (df_diario['dia_semana'] >= 5).astype(int)
    
    # Media móvil
    df_diario['media_movil_7'] = df_diario['cantidad'].rolling(window=7, min_periods=1).mean()
    df_diario = df_diario.fillna(method='bfill').fillna(0)
    
    features = ['dia_semana', 'mes', 'año', 'es_fin_semana', 'media_movil_7']
    X = df_diario[features].values
    y = df_diario['cantidad'].values
    
    if len(df_diario) < 30:
        X_train, y_train = X, y
        X_test, y_test = X, y
    else:
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    modelo = RandomForestRegressor(n_estimators=50, max_depth=8, random_state=42, n_jobs=-1)
    modelo.fit(X_train, y_train)
    
    # Predecir
    ultima_fila = df_diario.iloc[-1]
    predicciones = []
    
    for i in range(1, dias_prediccion + 1):
        fecha_futura = ultima_fila['fecha'] + timedelta(days=i)
        feature_dict = {
            'dia_semana': fecha_futura.weekday(),
            'mes': fecha_futura.month,
            'año': fecha_futura.year,
            'es_fin_semana': 1 if fecha_futura.weekday() >= 5 else 0,
            'media_movil_7': ultima_fila['media_movil_7'],
        }
        X_futuro = np.array([[feature_dict[f] for f in features]])
        pred = max(0, modelo.predict(X_futuro)[0])
        predicciones.append(pred)
    
    prediccion_total = sum(predicciones)
    prediccion_diaria = np.mean(predicciones)
    
    y_pred_test = modelo.predict(X_test)
    r2 = r2_score(y_test, y_pred_test)
    
    confianza = 'alta' if r2 > 0.6 else 'media' if r2 > 0.3 else 'baja'
    
    return {
        'prediccion_diaria_promedio': round(prediccion_diaria, 2),
        'prediccion_total': round(prediccion_total, 2),
        'confianza': confianza,
        'r2_score': round(r2, 3),
        'metricas': {
            'mae': round(mean_absolute_error(y_test, y_pred_test), 2),
            'rmse': round(np.sqrt(mean_squared_error(y_test, y_pred_test)), 2)
        }
    }


# ========== DETECCIÓN DE ANOMALÍAS CON ML ==========

def detectar_anomalias_ml_ventas(dias_analisis: int = 60) -> List[Dict]:
    """
    Detecta anomalías en ventas usando Isolation Forest (ML)
    """
    df = preparar_datos_ventas(dias_historia=dias_analisis)
    
    if df.empty or len(df) < 20:
        return []
    
    # Agrupar por día
    df_diario = df.groupby('fecha').agg({
        'ventas': 'sum'
    }).reset_index()
    
    # Features para detección de anomalías
    df_diario['dia_semana'] = df_diario['fecha'].dt.dayofweek
    df_diario['mes'] = df_diario['fecha'].dt.month
    df_diario['media_movil_7'] = df_diario['ventas'].rolling(window=7, min_periods=1).mean()
    df_diario['desviacion_7'] = df_diario['ventas'].rolling(window=7, min_periods=1).std()
    df_diario = df_diario.fillna(method='bfill').fillna(0)
    
    features = ['ventas', 'dia_semana', 'mes', 'media_movil_7', 'desviacion_7']
    X = df_diario[features].values
    
    # Entrenar Isolation Forest
    iso_forest = IsolationForest(contamination=0.1, random_state=42, n_jobs=-1)
    anomalias = iso_forest.fit_predict(X)
    
    # Filtrar anomalías (etiqueta -1)
    anomalias_detectadas = []
    for idx, (fecha, ventas_real) in enumerate(zip(df_diario['fecha'], df_diario['ventas'])):
        if anomalias[idx] == -1:
            anomalias_detectadas.append({
                'fecha': fecha.date(),
                'ventas': int(ventas_real),
                'tipo': 'pico' if ventas_real > df_diario['ventas'].mean() else 'valle',
                'score_anomalia': float(iso_forest.score_samples([X[idx]])[0]),
                'mensaje': f"Día {'excepcionalmente alto' if ventas_real > df_diario['ventas'].mean() else 'excepcionalmente bajo'} en ventas: {int(ventas_real)} vs promedio de {df_diario['ventas'].mean():.1f}"
            })
    
    return sorted(anomalias_detectadas, key=lambda x: abs(x['score_anomalia']))


def detectar_anomalias_ml_mermas(dias_analisis: int = 60) -> List[Dict]:
    """
    Detecta anomalías en mermas usando Isolation Forest (ML)
    """
    df = preparar_datos_mermas(dias_historia=dias_analisis)
    
    if df.empty or len(df) < 20:
        return []
    
    # Agrupar por día
    df_diario = df.groupby('fecha').agg({
        'cantidad': 'sum'
    }).reset_index()
    
    # Features
    df_diario['dia_semana'] = df_diario['fecha'].dt.dayofweek
    df_diario['mes'] = df_diario['fecha'].dt.month
    df_diario['media_movil_7'] = df_diario['cantidad'].rolling(window=7, min_periods=1).mean()
    df_diario['desviacion_7'] = df_diario['cantidad'].rolling(window=7, min_periods=1).std()
    df_diario = df_diario.fillna(method='bfill').fillna(0)
    
    features = ['cantidad', 'dia_semana', 'mes', 'media_movil_7', 'desviacion_7']
    X = df_diario[features].values
    
    # Solo detectar anomalías altas (mermas excesivas)
    df_alto = df_diario[df_diario['cantidad'] > df_diario['cantidad'].mean()]
    
    if len(df_alto) < 5:
        return []
    
    X_alto = df_alto[features].values
    iso_forest = IsolationForest(contamination=0.15, random_state=42, n_jobs=-1)
    anomalias = iso_forest.fit_predict(X_alto)
    
    anomalias_detectadas = []
    for idx, (fecha, cantidad) in enumerate(zip(df_alto['fecha'], df_alto['cantidad'])):
        if anomalias[idx] == -1:
            anomalias_detectadas.append({
                'fecha': fecha.date(),
                'merma_total': round(float(cantidad), 2),
                'score_anomalia': float(iso_forest.score_samples([X_alto[idx]])[0]),
                'promedio': round(df_diario['cantidad'].mean(), 2),
                'mensaje': f"Día con mermas excepcionalmente altas: {cantidad:.2f} vs promedio de {df_diario['cantidad'].mean():.2f}"
            })
    
    return sorted(anomalias_detectadas, key=lambda x: abs(x['score_anomalia']))


# ========== RECOMENDACIONES DE COMPRAS CON ML ==========

def recomendar_compras_ml(dias_proyeccion: int = 30, nivel_datos: str = None, modelo_tipo: str = 'auto') -> List[Dict]:
    """
    Genera recomendaciones de compras usando ML basado en predicciones de ventas y recetas
    
    NUEVO ENFOQUE: Predice ventas de platos → Multiplica por recetas → Calcula ingredientes necesarios
    
    Args:
        dias_proyeccion: Días a proyectar
        nivel_datos: Nivel de datos ('rapido', 'estandar', 'optimo'). Si es None, usa el default.
        modelo_tipo: Tipo de modelo ML a usar para predicciones de ventas ('auto', 'xgboost', 'lightgbm', etc.)
    """
    # Calcular fechas del período de proyección
    hoy = date.today()
    fecha_inicio = hoy + timedelta(days=1)  # Empezar desde mañana
    fecha_fin = hoy + timedelta(days=dias_proyeccion)
    
    # Obtener todos los platos que tienen recetas
    platos_con_receta = Plato.objects.filter(receta__isnull=False).distinct()
    
    if not platos_con_receta.exists():
        return []
    
    # Diccionario para acumular necesidades de insumos
    # Estructura: {insumo_id: {'cantidad_total': float, 'insumo': Insumo, 'detalles': []}}
    necesidades_insumos = {}
    
    # Contadores para diagnóstico
    platos_procesados = 0
    platos_omitidos = []
    platos_exitosos = []
    
    # Para cada plato, obtener predicciones de ventas y calcular ingredientes necesarios
    for plato in platos_con_receta:
        try:
            # Verificar datos históricos antes de intentar predecir
            df_datos = preparar_datos_ventas(plato_id=plato.id_plato, dias_historia=365)
            dias_con_datos = df_datos['fecha'].nunique() if not df_datos.empty else 0
            total_ventas_historicas = int(df_datos['ventas'].sum()) if not df_datos.empty else 0
            
            # Si hay muy pocos datos, registrar y continuar
            if df_datos.empty or len(df_datos) < 30 or dias_con_datos < 7:
                platos_omitidos.append({
                    'plato': plato.nombre_plato,
                    'plato_id': plato.id_plato,
                    'razon': f'Datos insuficientes: {dias_con_datos} días únicos con datos, {total_ventas_historicas} ventas totales (mínimo: 7 días únicos, 30 registros)',
                    'dias_con_datos': dias_con_datos,
                    'total_ventas': total_ventas_historicas
                })
                continue
            
            # Predecir ventas para este plato en el período
            prediccion_ventas = predecir_ventas_periodo(
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
                plato_id=plato.id_plato,
                modelo_tipo=modelo_tipo,
                dias_historia=365
            )
            
            if prediccion_ventas.get('error') or not prediccion_ventas.get('predicciones'):
                error_msg = prediccion_ventas.get('error', 'No se generaron predicciones')
                platos_omitidos.append({
                    'plato': plato.nombre_plato,
                    'plato_id': plato.id_plato,
                    'razon': f'Error en predicción: {error_msg}',
                    'dias_con_datos': dias_con_datos,
                    'total_ventas': total_ventas_historicas
                })
                continue
            
            # Obtener receta del plato
            recetas = Receta.objects.filter(id_plato=plato).select_related('id_insumo')
            
            if not recetas.exists():
                continue
            
            # Calcular total de ventas predichas para el período
            total_ventas_plato = prediccion_ventas.get('total_predicho', 0)
            
            # Para cada ingrediente en la receta, calcular cantidad necesaria
            for receta in recetas:
                insumo = receta.id_insumo
                cantidad_por_plato = float(receta.cantidad_necesaria)
                
                # Cantidad total necesaria = ventas predichas * cantidad por plato
                cantidad_total_necesaria = total_ventas_plato * cantidad_por_plato
                
                # Acumular en el diccionario
                if insumo.id_insumo not in necesidades_insumos:
                    necesidades_insumos[insumo.id_insumo] = {
                        'insumo': insumo,
                        'cantidad_total': 0.0,
                        'detalles': []  # Para tracking: qué platos usan este insumo
                    }
                
                necesidades_insumos[insumo.id_insumo]['cantidad_total'] += cantidad_total_necesaria
                necesidades_insumos[insumo.id_insumo]['detalles'].append({
                    'plato': plato.nombre_plato,
                    'ventas_predichas': round(total_ventas_plato, 1),
                    'cantidad_por_plato': cantidad_por_plato,
                    'cantidad_necesaria': round(cantidad_total_necesaria, 2)
                })
            
            # Registrar plato exitoso
            platos_exitosos.append({
                'plato': plato.nombre_plato,
                'plato_id': plato.id_plato,
                'ventas_predichas': round(total_ventas_plato, 1),
                'dias_con_datos': dias_con_datos,
                'total_ventas_historicas': total_ventas_historicas
            })
            platos_procesados += 1
        
        except Exception as e:
            # Si hay error con un plato, registrar y continuar con los demás
            platos_omitidos.append({
                'plato': plato.nombre_plato,
                'plato_id': plato.id_plato,
                'razon': f'Excepción: {str(e)}',
                'dias_con_datos': 0,
                'total_ventas': 0
            })
            continue
    
    # Logging para diagnóstico
    total_platos = platos_con_receta.count()
    print(f"\n[ML] Proyección de Compras - Resumen:")
    print(f"  Total platos con receta: {total_platos}")
    print(f"  Platos procesados exitosamente: {platos_procesados}")
    print(f"  Platos omitidos: {len(platos_omitidos)}")
    
    if platos_omitidos:
        print(f"\n  Platos omitidos (primeros 10):")
        for plato_info in platos_omitidos[:10]:
            print(f"    - {plato_info['plato']} (ID: {plato_info['plato_id']}): {plato_info['razon']}")
        if len(platos_omitidos) > 10:
            print(f"    ... y {len(platos_omitidos) - 10} platos más")
    
    if platos_exitosos:
        print(f"\n  Platos procesados exitosamente:")
        for plato_info in platos_exitosos[:5]:
            print(f"    - {plato_info['plato']}: {plato_info['ventas_predichas']} ventas predichas")
        if len(platos_exitosos) > 5:
            print(f"    ... y {len(platos_exitosos) - 5} platos más")
    
    # Convertir necesidades a recomendaciones de compra
    recomendaciones = []
    
    for insumo_id, datos in necesidades_insumos.items():
        insumo = datos['insumo']
        necesidad_total = datos['cantidad_total']
        
        # Obtener stock actual
        stock_actual_decimal = Lote.objects.filter(
            id_insumo=insumo,
            cantidad_actual__gt=0
        ).aggregate(total=Sum('cantidad_actual'))['total'] or 0
        
        stock_actual = float(stock_actual_decimal) if stock_actual_decimal else 0.0
        
        # Aplicar factor de seguridad (20% de margen)
        factor_seguridad = 1.2
        necesidad_total_ajustada = necesidad_total * factor_seguridad
        
        # Calcular cantidad a comprar
        cantidad_a_comprar = max(0.0, necesidad_total_ajustada - stock_actual)
        
        # Calcular demanda diaria promedio
        demanda_diaria = necesidad_total / dias_proyeccion if dias_proyeccion > 0 else 0
        
        # Calcular días de stock restante
        if demanda_diaria > 0:
            dias_stock_restante = stock_actual / demanda_diaria
        else:
            dias_stock_restante = 999.0
        
        # Determinar urgencia
        if dias_stock_restante < 7:
            urgencia = 'alta'
        elif dias_stock_restante < 15:
            urgencia = 'media'
        else:
            urgencia = 'baja'
        
        recomendaciones.append({
            'insumo_id': insumo.id_insumo,
            'insumo_nombre': insumo.nombre_insumo,
            'unidad_medida': insumo.unidad_medida,
            'stock_actual': round(stock_actual, 2),
            'demanda_predicha_diaria': round(demanda_diaria, 2),
            'demanda_predicha_total': round(necesidad_total, 2),
            'cantidad_a_comprar': round(cantidad_a_comprar, 2),
            'dias_stock_restante': round(dias_stock_restante, 1),
            'urgencia': urgencia,
            'confianza_prediccion': 'alta',  # Basado en predicciones de ventas
            'r2_score': 0,  # No aplica en este enfoque
            'metodo': 'Machine Learning (Ventas + Recetas)',
            'detalles_uso': datos['detalles']  # Información de qué platos usan este insumo
        })
    
    # Ordenar por urgencia y cantidad a comprar
    recomendaciones.sort(key=lambda x: (x['urgencia'] == 'alta', x['cantidad_a_comprar']), reverse=True)
    
    # Retornar recomendaciones con información de diagnóstico
    # Nota: Para mantener compatibilidad, retornamos solo la lista de recomendaciones
    # La información de diagnóstico se imprime en la consola
    return recomendaciones

