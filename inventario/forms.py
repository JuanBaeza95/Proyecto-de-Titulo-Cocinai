from django import forms
from datetime import date
from .models import Insumo, Proveedor, Ubicacion, CausaMerma, Plato, CategoriaProducto, UnidadMedida

class InsumoForm(forms.ModelForm):
    class Meta:
        model = Insumo
        fields = ['codigo', 'nombre_insumo', 'unidad_medida', 'costo_promedio']
        widgets = {
            'codigo': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: TOM, LEC, POL...',
                'required': True
            }),
            'nombre_insumo': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: Tomate, Pollo, Leche...'
            }),
            'unidad_medida': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: kg, gr, lt, und...'
            }),
            'costo_promedio': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00'
            })
        }
    
    def clean_costo_promedio(self):
        costo = self.cleaned_data.get('costo_promedio')
        if costo is not None and costo < 0:
            raise forms.ValidationError('El costo promedio no puede ser negativo.')
        return costo
    
    def clean_codigo(self):
        codigo = self.cleaned_data.get('codigo')
        if codigo:
            codigo = codigo.upper().strip()
        return codigo

class ProveedorForm(forms.ModelForm):
    class Meta:
        model = Proveedor
        fields = ['nombre_proveedor', 'direccion_proveedor', 'telefono_proveedor', 'correo_proveedor']
        widgets = {
            'nombre_proveedor': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: Distribuidora Central, Mercado Mayorista...',
                'required': True
            }),
            'direccion_proveedor': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: Av. Principal 123, Ciudad...',
                'required': True
            }),
            'telefono_proveedor': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: +56 9 1234 5678',
                'required': True
            }),
            'correo_proveedor': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: contacto@proveedor.com',
                'required': True
            })
        }
    
    def clean_direccion_proveedor(self):
        direccion = self.cleaned_data.get('direccion_proveedor')
        if not direccion or direccion.strip() == '':
            raise forms.ValidationError('La dirección es obligatoria.')
        if len(direccion) > 50:
            raise forms.ValidationError('La dirección no puede exceder 50 caracteres.')
        return direccion
    
    def clean_telefono_proveedor(self):
        telefono = self.cleaned_data.get('telefono_proveedor')
        if not telefono or telefono.strip() == '':
            raise forms.ValidationError('El teléfono es obligatorio.')
        if len(telefono) > 15:
            raise forms.ValidationError('El teléfono no puede exceder 15 caracteres.')
        return telefono
    
    def clean_correo_proveedor(self):
        correo = self.cleaned_data.get('correo_proveedor')
        if not correo or correo.strip() == '':
            raise forms.ValidationError('El correo electrónico es obligatorio.')
        if len(correo) > 50:
            raise forms.ValidationError('El correo electrónico no puede exceder 50 caracteres.')
        return correo

class UbicacionForm(forms.ModelForm):
    TIPO_UBICACION_CHOICES = [
        ('bodega', 'Bodega'),
        ('cocina', 'Cocina'),
        ('mesa', 'Mesa'),
        ('camara_fria', 'Cámara Fría'),
        ('congelador', 'Congelador'),
        ('despensa', 'Despensa'),
        ('refrigerador', 'Refrigerador'),
        ('almacen', 'Almacén'),
        ('secadora', 'Secadora'),
    ]
    
    tipo_ubicacion = forms.ChoiceField(
        choices=[('', 'Seleccionar tipo...')] + TIPO_UBICACION_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'required': True
        }),
        label='Tipo de Ubicación',
        required=True
    )
    
    class Meta:
        model = Ubicacion
        fields = ['nombre_ubicacion', 'tipo_ubicacion']
        widgets = {
            'nombre_ubicacion': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: Bodega Principal, Cocina, Cámara Fría...',
                'required': True
            }),
        }

class CausaMermaForm(forms.ModelForm):
    class Meta:
        model = CausaMerma
        fields = ['nombre_causa']
        widgets = {
            'nombre_causa': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: Caducidad, Sobreproducción, Mala manipulación...',
                'required': True
            })
        }
    
    def clean_nombre_causa(self):
        nombre = self.cleaned_data.get('nombre_causa')
        if nombre and len(nombre.strip()) == 0:
            raise forms.ValidationError('El nombre de la causa no puede estar vacío.')
        return nombre.strip()


class MermaLoteForm(forms.Form):
    """Formulario para registrar merma de un lote"""
    id_lote = forms.ModelChoiceField(
        queryset=None,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'required': True
        }),
        label='Lote',
        help_text='Seleccione el lote a mermar'
    )
    id_causa = forms.ModelChoiceField(
        queryset=None,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'required': True
        }),
        label='Causa de Merma',
        help_text='Seleccione la causa de la merma'
    )
    cantidad_desperdiciada = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'min': '0.01',
            'required': True
        }),
        label='Cantidad Desperdiciada',
        help_text='Cantidad a mermar del lote'
    )
    fecha_registro = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
            'required': True
        }),
        label='Fecha de Registro',
        initial=date.today
    )
    
    def __init__(self, *args, **kwargs):
        lote_preseleccionado = kwargs.pop('lote_preseleccionado', None)
        super().__init__(*args, **kwargs)
        from inventario.models import Lote, CausaMerma
        # Solo lotes con cantidad > 0, incluyendo información de cantidad y unidad
        lotes = Lote.objects.filter(cantidad_actual__gt=0).select_related('id_insumo', 'id_ubicacion').order_by('id_insumo__nombre_insumo', 'fecha_vencimiento')
        self.fields['id_lote'].queryset = lotes
        self.fields['id_causa'].queryset = CausaMerma.objects.all().order_by('nombre_causa')
        
        # Si hay un lote preseleccionado, deshabilitar el campo y ajustar el queryset
        if lote_preseleccionado:
            # Asegurar que el lote preseleccionado esté en el queryset
            if lote_preseleccionado not in lotes:
                lotes = Lote.objects.filter(id_lote=lote_preseleccionado.id_lote)
            self.fields['id_lote'].queryset = lotes
            # Establecer el valor inicial si no viene en initial
            if 'id_lote' not in self.initial:
                self.initial['id_lote'] = lote_preseleccionado
            # Marcar que el campo está preseleccionado (se manejará en el template)
            self.lote_preseleccionado = lote_preseleccionado
        else:
            self.lote_preseleccionado = None
        
        # Guardar información de lotes para el template
        self.lotes_info = {}
        for lote in lotes:
            self.lotes_info[str(lote.id_lote)] = {
                'cantidad': float(lote.cantidad_actual),
                'unidad': lote.id_insumo.unidad_medida,
                'insumo': lote.id_insumo.nombre_insumo,
                'numero_lote': lote.numero_lote
            }
    
    def clean_cantidad_desperdiciada(self):
        cantidad = self.cleaned_data.get('cantidad_desperdiciada')
        if cantidad and cantidad <= 0:
            raise forms.ValidationError('La cantidad debe ser mayor a cero.')
        return cantidad
    
    def clean(self):
        cleaned_data = super().clean()
        id_lote = cleaned_data.get('id_lote')
        cantidad = cleaned_data.get('cantidad_desperdiciada')
        
        if id_lote and cantidad:
            if cantidad > id_lote.cantidad_actual:
                raise forms.ValidationError({
                    'cantidad_desperdiciada': f'La cantidad no puede ser mayor a la disponible en el lote ({id_lote.cantidad_actual} {id_lote.id_insumo.unidad_medida}).'
                })
        
        return cleaned_data


class MermaPlatoForm(forms.Form):
    """Formulario para registrar merma de un plato producido"""
    id_plato_producido = forms.ModelChoiceField(
        queryset=None,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'required': True
        }),
        label='Plato Producido',
        help_text='Seleccione el plato producido a mermar'
    )
    id_causa = forms.ModelChoiceField(
        queryset=None,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'required': True
        }),
        label='Causa de Merma',
        help_text='Seleccione la causa de la merma'
    )
    cantidad_desperdiciada = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'min': '0.01',
            'required': True
        }),
        label='Cantidad Desperdiciada',
        help_text='Cantidad de platos a mermar (en unidades)'
    )
    fecha_registro = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
            'required': True
        }),
        label='Fecha de Registro',
        initial=date.today
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from inventario.models import PlatoProducido, CausaMerma, Merma
        # Solo platos producidos que no estén entregados y que NO tengan mermas asociadas
        # Obtener IDs de platos que ya tienen mermas
        platos_con_merma = Merma.objects.filter(
            tipo_merma='plato',
            id_plato_producido__isnull=False
        ).values_list('id_plato_producido', flat=True).distinct()
        
        # Filtrar platos disponibles: en cocina o mesa, y que no tengan mermas
        self.fields['id_plato_producido'].queryset = PlatoProducido.objects.filter(
            estado__in=['en_cocina', 'en_mesa']
        ).exclude(
            id_plato_producido__in=platos_con_merma
        ).order_by('-fecha_produccion')
        self.fields['id_causa'].queryset = CausaMerma.objects.all().order_by('nombre_causa')
    
    def clean_cantidad_desperdiciada(self):
        cantidad = self.cleaned_data.get('cantidad_desperdiciada')
        if cantidad and cantidad <= 0:
            raise forms.ValidationError('La cantidad debe ser mayor a cero.')
        return cantidad

class MovimientoStockForm(forms.Form):
    """Formulario para crear movimientos de stock (transferencias)"""
    TIPO_MOVIMIENTO_CHOICES = [
        ('transferencia', 'Transferencia'),
        ('salida', 'Salida'),
        ('ajuste', 'Ajuste'),
    ]
    
    id_lote_origen = forms.ModelChoiceField(
        queryset=None,
        label='Lote Origen',
        widget=forms.Select(attrs={
            'class': 'form-select',
            'required': True
        }),
        help_text='Seleccione el lote del cual desea mover stock (ordenado por FEFO - más próximo a vencer primero)',
        empty_label='Seleccione un lote...'
    )
    
    cantidad = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        label='Cantidad a Mover',
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'min': '0.01',
            'required': True
        }),
        help_text='Cantidad a mover del lote origen'
    )
    
    tipo_movimiento = forms.ChoiceField(
        choices=TIPO_MOVIMIENTO_CHOICES,
        label='Tipo de Movimiento',
        widget=forms.Select(attrs={
            'class': 'form-select',
            'required': True
        }),
        initial='transferencia'
    )
    
    id_ubicacion_destino = forms.ModelChoiceField(
        queryset=None,
        label='Ubicación Destino',
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        help_text='Ubicación destino (solo para transferencias)'
    )
    
    fecha_movimiento = forms.DateField(
        label='Fecha de Movimiento',
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
            'required': True
        }),
        initial=lambda: date.today()
    )
    
    observaciones = forms.CharField(
        required=False,
        label='Observaciones',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Observaciones adicionales sobre el movimiento...'
        })
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtrar solo lotes con cantidad > 0, ordenados por FEFO (fecha vencimiento más próxima primero)
        from inventario.models import Lote, Ubicacion
        from datetime import date
        
        lotes_queryset = Lote.objects.filter(
            cantidad_actual__gt=0,
            fecha_vencimiento__gte=date.today()  # Solo lotes no vencidos
        ).select_related('id_insumo', 'id_ubicacion').order_by('fecha_vencimiento', 'fecha_ingreso')
        
        self.fields['id_lote_origen'].queryset = lotes_queryset
        
        # Personalizar cómo se muestra cada opción en el select
        def label_from_instance(obj):
            """Muestra el lote con cantidad, ubicación y fecha de vencimiento"""
            dias_restantes = (obj.fecha_vencimiento - date.today()).days
            estado_vencimiento = f"({dias_restantes}d)" if dias_restantes >= 0 else "(Vencido)"
            return f"{obj.numero_lote} - {obj.id_insumo.nombre_insumo} | Stock: {obj.cantidad_actual} {obj.id_insumo.unidad_medida} | {obj.id_ubicacion.nombre_ubicacion} | Vence: {obj.fecha_vencimiento.strftime('%d/%m/%Y')} {estado_vencimiento}"
        
        self.fields['id_lote_origen'].label_from_instance = label_from_instance
        self.fields['id_ubicacion_destino'].queryset = Ubicacion.objects.all().order_by('nombre_ubicacion')
    
    def clean_cantidad(self):
        cantidad = self.cleaned_data.get('cantidad')
        if cantidad and cantidad <= 0:
            raise forms.ValidationError('La cantidad debe ser mayor a cero.')
        return cantidad
    
    def clean(self):
        cleaned_data = super().clean()
        tipo_movimiento = cleaned_data.get('tipo_movimiento')
        id_ubicacion_destino = cleaned_data.get('id_ubicacion_destino')
        id_lote_origen = cleaned_data.get('id_lote_origen')
        cantidad = cleaned_data.get('cantidad')
        
        # Validar que la cantidad no exceda la disponible
        if id_lote_origen and cantidad:
            if cantidad > id_lote_origen.cantidad_actual:
                raise forms.ValidationError({
                    'cantidad': f'La cantidad no puede ser mayor a la disponible ({id_lote_origen.cantidad_actual} {id_lote_origen.id_insumo.unidad_medida}).'
                })
        
        # Para transferencias, la ubicación destino es obligatoria
        if tipo_movimiento == 'transferencia' and not id_ubicacion_destino:
            raise forms.ValidationError({
                'id_ubicacion_destino': 'La ubicación destino es obligatoria para transferencias.'
            })
        
        # Para transferencias, no puede ser la misma ubicación
        if tipo_movimiento == 'transferencia' and id_lote_origen and id_ubicacion_destino:
            if id_lote_origen.id_ubicacion.id_ubicacion == id_ubicacion_destino.id_ubicacion:
                raise forms.ValidationError({
                    'id_ubicacion_destino': 'La ubicación destino debe ser diferente a la ubicación origen.'
                })
        
        return cleaned_data

class PlatoForm(forms.ModelForm):
    class Meta:
        model = Plato
        fields = ['nombre_plato']
        widgets = {
            'nombre_plato': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: Pollo a la Plancha, Ensalada César...'
            })
        }

class CategoriaProductoForm(forms.ModelForm):
    class Meta:
        model = CategoriaProducto
        fields = ['nombre_categoria', 'descripcion']
        widgets = {
            'nombre_categoria': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: Carnes, Verduras, Lácteos...'
            }),
            'descripcion': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Descripción opcional de la categoría...'
            })
        }

class UnidadMedidaForm(forms.ModelForm):
    class Meta:
        model = UnidadMedida
        fields = ['nombre_unidad', 'abreviatura']
        widgets = {
            'nombre_unidad': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: Kilogramo, Gramo, Litro...'
            }),
            'abreviatura': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: kg, gr, lt...'
            })
        }
