"""
Configuración para el sistema de Machine Learning
Permite ajustar los requisitos mínimos de datos según las necesidades
"""
from typing import Dict



# Niveles de requisitos de datos
NIVELES_DATOS = {
    'rapido': {
        'dias_minimos': 7,
        'descripcion': 'Modo Rápido - Predicciones básicas con datos mínimos',
        'confianza_esperada': 'baja',
        'advertencia': 'Las predicciones pueden ser menos precisas con solo 7 días de datos'
    },
    'estandar': {
        'dias_minimos': 20,
        'descripcion': 'Modo Estándar - Predicciones confiables (recomendado)',
        'confianza_esperada': 'media',
        'advertencia': None
    },
    'optimo': {
        'dias_minimos': 60,
        'descripcion': 'Modo Óptimo - Máxima precisión con datos extensos',
        'confianza_esperada': 'alta',
        'advertencia': None
    }
}

# Nivel por defecto
NIVEL_DATOS_DEFAULT = 'estandar'

# Obtener configuración actual
def obtener_configuracion_ml(nivel: str = None) -> Dict:
    """
    Obtiene la configuración de ML para un nivel específico
    
    Args:
        nivel: 'rapido', 'estandar', o 'optimo'. Si es None, usa el default.
    
    Returns:
        Dict con la configuración del nivel
    """
    if nivel is None:
        nivel = NIVEL_DATOS_DEFAULT
    
    if nivel not in NIVELES_DATOS:
        nivel = NIVEL_DATOS_DEFAULT
    
    return NIVELES_DATOS[nivel]

# Días mínimos actuales
def obtener_dias_minimos(nivel: str = None) -> int:
    """Obtiene los días mínimos requeridos para el nivel especificado"""
    config = obtener_configuracion_ml(nivel)
    return config['dias_minimos']

