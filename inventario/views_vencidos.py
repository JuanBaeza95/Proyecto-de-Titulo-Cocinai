"""
Vistas para manejar alertas de productos vencidos
"""
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from datetime import date
import json
from .utils import (
    obtener_lotes_vencidos_nuevos, 
    marcar_lotes_como_mostrados,
    actualizar_preferencia_no_mostrar
)
from .models import Lote


@login_required
@require_http_methods(["GET"])
def obtener_productos_vencidos(request):
    """
    API endpoint para obtener productos vencidos
    Retorna JSON con los lotes vencidos
    """
    try:
        lotes_vencidos = obtener_lotes_vencidos_nuevos(request.user)
        
        lotes_data = []
        for lote in lotes_vencidos:
            lotes_data.append({
                'id_lote': lote.id_lote,
                'numero_lote': lote.numero_lote,
                'insumo_nombre': lote.id_insumo.nombre_insumo,
                'insumo_unidad': lote.id_insumo.unidad_medida,
                'cantidad_actual': float(lote.cantidad_actual),
                'fecha_vencimiento': lote.fecha_vencimiento.strftime('%d/%m/%Y'),
                'dias_vencido': (date.today() - lote.fecha_vencimiento).days,
                'ubicacion': lote.id_ubicacion.nombre_ubicacion,
            })
        
        return JsonResponse({
            'success': True,
            'lotes_vencidos': lotes_data,
            'cantidad': len(lotes_data)
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'lotes_vencidos': [],
            'cantidad': 0
        })


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def marcar_vencidos_vistos(request):
    """
    Marca los lotes vencidos como vistos por el usuario
    """
    try:
        data = json.loads(request.body)
        lotes_ids = data.get('lotes_ids', [])
        no_mostrar = data.get('no_mostrar', False)
        
        # Marcar lotes como mostrados
        if lotes_ids:
            marcar_lotes_como_mostrados(request.user, lotes_ids)
        
        # Actualizar preferencia de no mostrar
        actualizar_preferencia_no_mostrar(request.user, no_mostrar)
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["GET"])
def redirigir_mermar_lote(request, lote_id):
    """
    Redirige a la página de mermar lote con el lote pre-seleccionado
    """
    from django.shortcuts import redirect
    return redirect(f'/inventario/mermas/crear-lote/?lote_id={lote_id}')

