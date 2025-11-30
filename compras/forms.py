from django import forms
from django.forms import inlineformset_factory, formset_factory, BaseInlineFormSet
from inventario.models import OrdenCompra, DetalleCompra, Proveedor, Insumo, Ubicacion
from datetime import date


class OrdenCompraForm(forms.ModelForm):
    """Formulario para crear/editar órdenes de compra"""
    class Meta:
        model = OrdenCompra
        fields = ['id_proveedor', 'fecha_pedido', 'estado']
        widgets = {
            'id_proveedor': forms.Select(attrs={
                'class': 'form-select',
                'required': True
            }),
            'fecha_pedido': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'required': True
            }),
            'estado': forms.Select(attrs={
                'class': 'form-select'
            }, choices=[
                ('pendiente', 'Pendiente'),
                ('en_proceso', 'En Proceso'),
                ('recibida', 'Recibida'),
                ('cancelada', 'Cancelada'),
            ])
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['id_proveedor'].queryset = Proveedor.objects.all().order_by('nombre_proveedor')
        if not self.instance.pk:
            self.fields['estado'].initial = 'pendiente'


class DetalleCompraForm(forms.ModelForm):
    """Formulario para los detalles de compra (usado en formset)"""
    class Meta:
        model = DetalleCompra
        fields = ['id_insumo', 'cantidad_pedida', 'costo_unitario_acordado']
        widgets = {
            'id_insumo': forms.Select(attrs={
                'class': 'form-select'
            }),
            'cantidad_pedida': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.01',
                'placeholder': '0.00'
            }),
            'costo_unitario_acordado': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['id_insumo'].queryset = Insumo.objects.all().order_by('nombre_insumo')
        # El campo id no debe ser requerido para nuevos detalles
        if 'id_detalle_compra' in self.fields:
            self.fields['id_detalle_compra'].required = False
    
    def clean_cantidad_pedida(self):
        cantidad = self.cleaned_data.get('cantidad_pedida')
        if cantidad is not None and cantidad <= 0:
            raise forms.ValidationError('La cantidad debe ser mayor a cero.')
        return cantidad
    
    def clean_costo_unitario_acordado(self):
        costo = self.cleaned_data.get('costo_unitario_acordado')
        if costo is not None and costo < 0:
            raise forms.ValidationError('El costo unitario no puede ser negativo.')
        return costo


class DetalleCompraFormSetBase(BaseInlineFormSet):
    """Formset base personalizado para manejar mejor los detalles vacíos"""
    def clean(self):
        if any(self.errors):
            return
        # Filtrar formularios vacíos (excluir los que están marcados para eliminar o están completamente vacíos)
        forms_validos = []
        for form in self.forms:
            if form.cleaned_data:
                # Si está marcado para eliminar, no contarlo
                if form.cleaned_data.get('DELETE', False):
                    continue
                # Si tiene insumo y cantidad, es válido
                if form.cleaned_data.get('id_insumo') and form.cleaned_data.get('cantidad_pedida'):
                    forms_validos.append(form)
        
        if len(forms_validos) < 1:
            raise forms.ValidationError('Debes agregar al menos un detalle a la orden.')


# Formset para manejar múltiples detalles de compra
DetalleCompraFormSet = inlineformset_factory(
    OrdenCompra,
    DetalleCompra,
    form=DetalleCompraForm,
    formset=DetalleCompraFormSetBase,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=False,  # Validamos manualmente
    fields=('id_insumo', 'cantidad_pedida', 'costo_unitario_acordado')  # Especificar campos explícitamente
)


class RecepcionDetalleForm(forms.Form):
    """Formulario para recepcionar un detalle de compra"""
    detalle_id = forms.IntegerField(widget=forms.HiddenInput())
    recibir = forms.BooleanField(required=False, label="Recibir")
    cantidad_recibida = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=0.01,
        label="Cantidad Recibida",
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'min': '0.01',
            'placeholder': '0.00'
        })
    )
    fecha_vencimiento = forms.DateField(
        label="Fecha de Vencimiento",
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
            'required': True
        })
    )
    fecha_ingreso = forms.DateField(
        label="Fecha de Ingreso",
        initial=date.today,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
            'required': True
        })
    )
    id_ubicacion = forms.ModelChoiceField(
        queryset=Ubicacion.objects.all(),
        label="Ubicación",
        widget=forms.Select(attrs={
            'class': 'form-select',
            'required': True
        })
    )
    costo_unitario_real = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=0,
        label="Costo Unitario Real",
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'min': '0',
            'placeholder': '0.00'
        })
    )
    
    def __init__(self, *args, detalle=None, **kwargs):
        super().__init__(*args, **kwargs)
        if detalle:
            self.fields['detalle_id'].initial = detalle.id_detalle_compra
            self.fields['cantidad_recibida'].initial = detalle.cantidad_pedida
            self.fields['costo_unitario_real'].initial = detalle.costo_unitario_acordado
        self.fields['id_ubicacion'].queryset = Ubicacion.objects.all().order_by('nombre_ubicacion')
    
    def clean(self):
        cleaned_data = super().clean()
        recibir = cleaned_data.get('recibir')
        cantidad_recibida = cleaned_data.get('cantidad_recibida')
        fecha_vencimiento = cleaned_data.get('fecha_vencimiento')
        fecha_ingreso = cleaned_data.get('fecha_ingreso')
        
        if recibir:
            if not cantidad_recibida or cantidad_recibida <= 0:
                raise forms.ValidationError('La cantidad recibida debe ser mayor a cero.')
            
            if not fecha_vencimiento:
                raise forms.ValidationError('La fecha de vencimiento es requerida.')
            
            if not fecha_ingreso:
                raise forms.ValidationError('La fecha de ingreso es requerida.')
            
            if fecha_vencimiento < fecha_ingreso:
                raise forms.ValidationError('La fecha de vencimiento no puede ser anterior a la fecha de ingreso.')
        
        return cleaned_data


RecepcionFormSet = formset_factory(
    RecepcionDetalleForm,
    extra=0,
    can_delete=False
)

