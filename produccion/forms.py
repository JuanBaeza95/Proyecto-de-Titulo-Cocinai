from django import forms
from django.forms import inlineformset_factory, BaseInlineFormSet, formset_factory, BaseFormSet
from inventario.models import Receta, Plato, Insumo, PlatoProducido


class PlatoForm(forms.ModelForm):
    """Formulario para crear/editar platos"""
    class Meta:
        model = Plato
        fields = ['nombre_plato']
        widgets = {
            'nombre_plato': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: Pollo a la Plancha, Ensalada César...',
                'required': True
            })
        }
    
    def clean_nombre_plato(self):
        nombre = self.cleaned_data.get('nombre_plato')
        if nombre and len(nombre.strip()) == 0:
            raise forms.ValidationError('El nombre del plato no puede estar vacío.')
        return nombre.strip()


class RecetaForm(forms.ModelForm):
    """Formulario para crear/editar recetas"""
    class Meta:
        model = Receta
        fields = ['id_insumo', 'cantidad_necesaria']
        widgets = {
            'id_insumo': forms.Select(attrs={
                'class': 'form-select',
            }),
            'cantidad_necesaria': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.01',
                'placeholder': '0.00'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['id_insumo'].queryset = Insumo.objects.all().order_by('nombre_insumo')
        
        # Para formularios nuevos (sin pk), hacer los campos opcionales
        # Para formularios existentes, mantenerlos como required
        if not self.instance or not self.instance.pk:
            self.fields['id_insumo'].required = False
            self.fields['cantidad_necesaria'].required = False
    
    def clean_cantidad_necesaria(self):
        cantidad = self.cleaned_data.get('cantidad_necesaria')
        if cantidad and cantidad <= 0:
            raise forms.ValidationError('La cantidad debe ser mayor a cero.')
        return cantidad


class RecetaFormSet(BaseInlineFormSet):
    """Formset personalizado para recetas"""
    def clean(self):
        if any(self.errors):
            return
        
        # Validar que no haya duplicados de insumos en la misma receta
        insumos = []
        for form in self.forms:
            if self.can_delete and self._should_delete_form(form):
                continue
            
            # Solo validar formularios que tienen datos
            id_insumo = form.cleaned_data.get('id_insumo')
            cantidad = form.cleaned_data.get('cantidad_necesaria')
            
            # Si tiene insumo pero no cantidad, o viceversa, es un error
            if id_insumo and not cantidad:
                raise forms.ValidationError(
                    'Debe especificar la cantidad para todos los insumos.'
                )
            if cantidad and not id_insumo:
                raise forms.ValidationError(
                    'Debe seleccionar un insumo para todas las cantidades especificadas.'
                )
            
            # Si tiene ambos, validar duplicados
            if id_insumo and cantidad:
                if id_insumo in insumos:
                    raise forms.ValidationError(
                        f'No se puede agregar el mismo insumo "{id_insumo.nombre_insumo}" dos veces a una receta.'
                    )
                insumos.append(id_insumo)


# Formset para gestionar múltiples ingredientes de una receta
RecetaInlineFormSet = inlineformset_factory(
    Plato,
    Receta,
    form=RecetaForm,
    formset=RecetaFormSet,
    extra=1,
    can_delete=True,
    fields=['id_insumo', 'cantidad_necesaria']
)


class IngredienteProduccionForm(forms.Form):
    """Formulario para un ingrediente en la producción (no guarda en BD)"""
    id_insumo = forms.ModelChoiceField(
        queryset=Insumo.objects.all().order_by('nombre_insumo'),
        widget=forms.Select(attrs={
            'class': 'form-select',
        }),
        label='Insumo',
        required=False
    )
    cantidad_necesaria = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'min': '0.01',
            'placeholder': '0.00'
        }),
        label='Cantidad',
        required=False
    )
    
    def clean_cantidad_necesaria(self):
        cantidad = self.cleaned_data.get('cantidad_necesaria')
        if cantidad and cantidad <= 0:
            raise forms.ValidationError('La cantidad debe ser mayor a cero.')
        return cantidad


class IngredienteProduccionFormSet(BaseFormSet):
    """Formset personalizado para ingredientes de producción"""
    def clean(self):
        if any(self.errors):
            return
        
        # Validar que no haya duplicados de insumos
        insumos = []
        forms_validos = []
        
        for form in self.forms:
            # Verificar si el formulario debe eliminarse
            if hasattr(form, 'cleaned_data') and form.cleaned_data.get('DELETE', False):
                continue
            
            id_insumo = form.cleaned_data.get('id_insumo') if hasattr(form, 'cleaned_data') else None
            cantidad = form.cleaned_data.get('cantidad_necesaria') if hasattr(form, 'cleaned_data') else None
            
            # Si ambos están vacíos, es un formulario vacío (válido)
            if not id_insumo and not cantidad:
                continue
            
            # Si tiene uno pero no el otro, es un error
            if id_insumo and not cantidad:
                raise forms.ValidationError(
                    'Debe especificar la cantidad para todos los insumos.'
                )
            if cantidad and not id_insumo:
                raise forms.ValidationError(
                    'Debe seleccionar un insumo para todas las cantidades especificadas.'
                )
            
            # Si tiene ambos, validar duplicados
            if id_insumo and cantidad:
                if id_insumo in insumos:
                    raise forms.ValidationError(
                        f'No se puede agregar el mismo insumo "{id_insumo.nombre_insumo}" dos veces.'
                    )
                insumos.append(id_insumo)
                forms_validos.append(form)
        
        # Validar que haya al menos un ingrediente válido
        if not forms_validos:
            raise forms.ValidationError('Debe agregar al menos un ingrediente válido.')


# Formset para ingredientes de producción (no guarda en BD)
IngredienteProduccionFormSet = formset_factory(
    IngredienteProduccionForm,
    formset=IngredienteProduccionFormSet,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=False  # Cambiar a False porque validamos manualmente en clean()
)


class PlatoProducidoForm(forms.Form):
    """Formulario para crear un plato producido"""
    id_plato = forms.ModelChoiceField(
        queryset=Plato.objects.none(),
        widget=forms.Select(attrs={
            'class': 'form-select',
            'required': True,
            'id': 'id_plato_select'
        }),
        label='Plato',
        help_text='Seleccione el plato a producir'
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Solo mostrar platos que tienen receta
        from inventario.models import Receta
        platos_ids_con_receta = Receta.objects.values_list('id_plato', flat=True).distinct()
        platos_con_receta = Plato.objects.filter(
            id_plato__in=platos_ids_con_receta
        ).order_by('nombre_plato')
        self.fields['id_plato'].queryset = platos_con_receta
