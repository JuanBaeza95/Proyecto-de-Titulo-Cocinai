"""
Definición de menús/subsecciones para cada módulo del sistema.
Cada sección tiene una lista de menús que pueden ser asignados a usuarios.
"""

MENUS_POR_SECCION = {
    'inventario': [
        ('proveedores', 'Proveedores'),
        ('insumos', 'Insumos'),
        ('ubicaciones', 'Ubicaciones'),
        ('lotes', 'Lotes'),
        ('movimientos', 'Movimientos de Stock'),
        ('mermas', 'Mermas'),
        ('causas_merma', 'Causas de Merma'),
    ],
    'compras': [
        ('ordenes', 'Órdenes de Compra'),
    ],
    'produccion': [
        ('recetas', 'Recetas'),
        ('platos', 'Platos'),
    ],
    'ventas': [
        ('mover_mesa', 'Mover a Mesa'),
        ('mesas', 'Mesas Activas'),
        ('cerrar_venta', 'Cerrar Venta'),
        ('historial_mesas', 'Historial de Movimientos'),
        ('historial_ventas', 'Historial de Ventas de Platos'),
    ],
    'prediccion': [
        ('predicciones', 'Dashboard de Predicciones'),
        ('ventas_semanales', 'Análisis Ventas Semanales'),
        ('ventas_mensuales', 'Análisis Ventas Mensuales'),
        ('mermas', 'Análisis de Mermas'),
        ('proyeccion_compras', 'Proyección de Compras'),
        ('anomalias', 'Detección de Anomalías'),
        ('reporte_completo', 'Reporte Completo'),
    ],
    'usuarios': [
        ('lista', 'Lista de Usuarios'),
        ('crear', 'Crear Usuario'),
        ('editar', 'Editar Usuario'),
        ('eliminar', 'Eliminar Usuario'),
        ('cambiar_contrasena', 'Cambiar Contraseña'),
    ],
}

def obtener_menus_por_seccion():
    """Retorna el diccionario de menús por sección"""
    return MENUS_POR_SECCION

def obtener_todos_los_menus():
    """Retorna una lista plana de todos los menús con formato 'seccion.menu'"""
    todos = []
    for seccion, menus in MENUS_POR_SECCION.items():
        for menu_id, menu_nombre in menus:
            todos.append((f'{seccion}.{menu_id}', f'{menu_nombre} ({seccion})'))
    return todos

def obtener_secciones():
    """Retorna la lista de secciones disponibles"""
    return [
        ('inventario', 'Inventario'),
        ('compras', 'Compras'),
        ('produccion', 'Producción'),
        ('ventas', 'Ventas'),
        ('prediccion', 'Predicción'),
        ('usuarios', 'Usuarios')
    ]

