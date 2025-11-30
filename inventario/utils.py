"""
Utilidades para el módulo de inventario
"""
from datetime import date
from django.db.models import Q
from .models import Lote, PreferenciaUsuarioVencidos
from django.contrib.auth.models import User


def obtener_lotes_vencidos(usuario=None):
    """
    Obtiene todos los lotes vencidos con cantidad actual > 0
    """
    hoy = date.today()
    lotes_vencidos = Lote.objects.filter(
        fecha_vencimiento__lt=hoy,
        cantidad_actual__gt=0
    ).select_related('id_insumo', 'id_ubicacion').order_by('fecha_vencimiento')
    
    return lotes_vencidos


def obtener_lotes_vencidos_nuevos(usuario):
    """
    Obtiene lotes vencidos que aún no se han mostrado al usuario
    Si el usuario tiene la preferencia de no mostrar, solo retorna los nuevos
    """
    if not usuario or not usuario.is_authenticated:
        return []
    
    # Obtener preferencia del usuario
    try:
        preferencia = PreferenciaUsuarioVencidos.objects.get(id_usuario=usuario)
        lotes_mostrados = preferencia.lotes_mostrados or []
    except PreferenciaUsuarioVencidos.DoesNotExist:
        preferencia = None
        lotes_mostrados = []
    
    # Obtener todos los lotes vencidos
    lotes_vencidos = obtener_lotes_vencidos()
    
    # Si el usuario tiene "no mostrar", solo retornar los nuevos
    if preferencia and preferencia.no_mostrar_alertas:
        lotes_nuevos = [lote for lote in lotes_vencidos if lote.id_lote not in lotes_mostrados]
        return lotes_nuevos
    
    # Si no tiene la preferencia, retornar todos
    return list(lotes_vencidos)


def marcar_lotes_como_mostrados(usuario, lotes_ids):
    """
    Marca los lotes como mostrados para el usuario
    """
    if not usuario or not usuario.is_authenticated:
        return
    
    try:
        preferencia = PreferenciaUsuarioVencidos.objects.get(id_usuario=usuario)
    except PreferenciaUsuarioVencidos.DoesNotExist:
        preferencia = PreferenciaUsuarioVencidos.objects.create(id_usuario=usuario)
    
    # Agregar los nuevos IDs a la lista de mostrados
    lotes_mostrados = preferencia.lotes_mostrados or []
    for lote_id in lotes_ids:
        if lote_id not in lotes_mostrados:
            lotes_mostrados.append(lote_id)
    
    preferencia.lotes_mostrados = lotes_mostrados
    preferencia.save()


def actualizar_preferencia_no_mostrar(usuario, no_mostrar):
    """
    Actualiza la preferencia de no mostrar alertas del usuario
    """
    if not usuario or not usuario.is_authenticated:
        return
    
    preferencia, created = PreferenciaUsuarioVencidos.objects.get_or_create(
        id_usuario=usuario,
        defaults={'no_mostrar_alertas': no_mostrar}
    )
    
    if not created:
        preferencia.no_mostrar_alertas = no_mostrar
        preferencia.save()

