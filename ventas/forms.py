from django import forms
from django.forms import inlineformset_factory, BaseInlineFormSet
from .models import Comanda, DetalleComanda, Mesa
from inventario.models import Plato

class MoverPlatoMesaForm(forms.Form):
    """Formulario para mover un plato producido a una mesa"""
    id_ubicacion = forms.ModelChoiceField(
        queryset=None,
        label='Ubicación (Mesa)',
        widget=forms.Select(attrs={
            'class': 'form-select',
            'required': True
        }),
        help_text='Seleccione la ubicación de mesa a la que se moverá el plato'
    )
    numero_mesa = forms.CharField(
        required=False,
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ej: 1, 2, 3, A1, B2... (opcional)'
        }),
        label='Número de Mesa',
        help_text='Número o identificador de la mesa específica (opcional)'
    )
    observaciones = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Observaciones opcionales...'
        }),
        label='Observaciones',
        help_text='Observaciones adicionales sobre el movimiento'
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Mostrar solo ubicaciones de tipo "mesa"
        from inventario.models import Ubicacion
        self.fields['id_ubicacion'].queryset = Ubicacion.objects.filter(
            tipo_ubicacion__iexact='mesa'
        ).order_by('nombre_ubicacion')
        
        # Si no hay ubicaciones de tipo exacto, buscar por nombre
        if not self.fields['id_ubicacion'].queryset.exists():
            self.fields['id_ubicacion'].queryset = Ubicacion.objects.filter(
                tipo_ubicacion__icontains='mesa'
            ).order_by('nombre_ubicacion')
        
        # Si aún no hay, buscar por nombre que contenga "mesa"
        if not self.fields['id_ubicacion'].queryset.exists():
            self.fields['id_ubicacion'].queryset = Ubicacion.objects.filter(
                nombre_ubicacion__icontains='mesa'
            ).order_by('nombre_ubicacion')


class ComandaForm(forms.Form):
    """Formulario para crear una comanda"""
    id_ubicacion = forms.ModelChoiceField(
        queryset=None,  # Se establecerá en __init__
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'required': True
        }),
        label='Ubicación (Mesa)',
        help_text='Seleccione la ubicación de la mesa'
    )
    numero_mesa = forms.CharField(
        max_length=10,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ej: 1, 2, 3, A1, B2...',
            'required': True
        }),
        label='Número de Mesa',
        help_text='Ingrese el número o identificador de la mesa'
    )
    observaciones = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Observaciones opcionales...'
        }),
        label='Observaciones',
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Obtener ubicaciones de tipo "mesa"
        from inventario.models import Ubicacion
        self.fields['id_ubicacion'].queryset = Ubicacion.objects.filter(
            tipo_ubicacion__icontains='mesa'
        ).order_by('nombre_ubicacion')


class DetalleComandaForm(forms.ModelForm):
    """Formulario para un detalle de comanda"""
    class Meta:
        model = DetalleComanda
        fields = ['id_plato', 'cantidad', 'observaciones']
        widgets = {
            'id_plato': forms.Select(attrs={
                'class': 'form-select',
            }),
            'cantidad': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'value': 1
            }),
            'observaciones': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Observaciones opcionales...'
            }),
        }
        labels = {
            'id_plato': 'Plato',
            'cantidad': 'Cantidad',
            'observaciones': 'Observaciones',
        }
    
    def clean(self):
        """Validación personalizada para el formulario"""
        cleaned_data = super().clean()
        id_plato = cleaned_data.get('id_plato')
        cantidad = cleaned_data.get('cantidad')
        
        # Si no tiene plato ni cantidad, es un formulario vacío (válido, será ignorado)
        if not id_plato and not cantidad:
            # Formulario vacío - no es un error, pero no se guardará
            return cleaned_data
        
        # Si tiene uno pero no el otro, es un error
        if id_plato and not cantidad:
            raise forms.ValidationError('Debe especificar la cantidad.')
        if cantidad and not id_plato:
            raise forms.ValidationError('Debe seleccionar un plato.')
        
        return cleaned_data
    
    def clean_cantidad(self):
        cantidad = self.cleaned_data.get('cantidad')
        if cantidad and cantidad < 1:
            raise forms.ValidationError('La cantidad debe ser al menos 1.')
        return cantidad
    
    def has_changed(self):
        """Sobrescribir para que Django no ignore formularios con datos"""
        # Si tiene datos iniciales (formulario existente), usar el comportamiento por defecto
        if self.initial:
            return super().has_changed()
        
        # Para formularios nuevos, verificar si tiene datos en el POST
        # Esto es crítico para que Django procese formularios vacíos correctamente
        if not hasattr(self, 'data'):
            return False
        
        id_plato = self.data.get(self.add_prefix('id_plato'))
        cantidad = self.data.get(self.add_prefix('cantidad'))
        
        # Si tiene plato Y cantidad, considerar que ha cambiado (tiene datos)
        has_data = bool(id_plato and cantidad)
        
        # Si no tiene datos, también retornar True para que Django lo procese
        # y pueda detectar que está vacío en clean()
        return True  # Siempre retornar True para que Django procese todos los formularios


class DetalleComandaFormSet(BaseInlineFormSet):
    """Formset personalizado para detalles de comanda"""
    def clean(self):
        if any(self.errors):
            return
        
        # Validar que haya al menos un detalle
        forms_validos = []
        for i, form in enumerate(self.forms):
            # Si el formulario está marcado para eliminar, saltarlo
            if self.can_delete and self._should_delete_form(form):
                continue
            
            # Solo validar si el formulario tiene cleaned_data (fue procesado)
            if not hasattr(form, 'cleaned_data'):
                print(f"[DEBUG FormSet.clean] Form {i} NO tiene cleaned_data")
                continue
            
            id_plato = form.cleaned_data.get('id_plato')
            cantidad = form.cleaned_data.get('cantidad')
            delete = form.cleaned_data.get('DELETE', False)
            
            print(f"[DEBUG FormSet.clean] Form {i}: plato={id_plato}, cantidad={cantidad}, DELETE={delete}")
            
            # Si tiene plato y cantidad y no está marcado para eliminar, es válido
            if id_plato and cantidad and not delete:
                forms_validos.append(form)
                print(f"[DEBUG FormSet.clean] Form {i} es VÁLIDO")
        
        print(f"[DEBUG FormSet.clean] Total forms válidos: {len(forms_validos)}")
        
        if not forms_validos:
            raise forms.ValidationError('Debe agregar al menos un plato a la comanda.')
    
    def save(self, commit=True):
        """Override save para asegurar que se guarden todos los formularios válidos"""
        # Primero, obtener todas las instancias que el formset base quiere guardar
        instances = super().save(commit=False)
        
        print(f"[DEBUG FormSet.save] Instancias del formset base: {len(instances)}")
        
        # Pero el formset base puede haber ignorado algunos formularios
        # Necesitamos procesar manualmente todos los formularios que tienen datos
        saved_instances = list(instances)
        
        # Procesar todos los formularios para encontrar los que tienen datos pero no fueron incluidos
        for i, form in enumerate(self.forms):
            # Si el formulario está marcado para eliminar, saltarlo
            if self.can_delete and self._should_delete_form(form):
                continue
            
            # Si el formulario tiene errores, saltarlo
            if form.errors:
                print(f"[DEBUG FormSet.save] Form {i} tiene errores: {form.errors}")
                continue
            
            # Verificar si el formulario tiene datos
            if hasattr(form, 'cleaned_data'):
                id_plato = form.cleaned_data.get('id_plato')
                cantidad = form.cleaned_data.get('cantidad')
                delete = form.cleaned_data.get('DELETE', False)
                
                # Si tiene plato y cantidad y no está marcado para eliminar
                if id_plato and cantidad and not delete:
                    # Verificar si esta instancia ya está en saved_instances
                    # (comparando por el índice del formulario)
                    form_instance = form.instance
                    
                    # Si form.instance no tiene id, es una nueva instancia
                    if not form_instance.pk:
                        # Verificar si ya está en saved_instances
                        already_saved = any(
                            inst.pk == form_instance.pk or 
                            (not inst.pk and getattr(inst, '_form_index', None) == i)
                            for inst in saved_instances
                        )
                        
                        if not already_saved:
                            # Marcar el índice del formulario para referencia
                            form_instance._form_index = i
                            saved_instances.append(form_instance)
                            print(f"[DEBUG FormSet.save] Agregando nueva instancia del form {i}: plato={id_plato}, cantidad={cantidad}")
                    else:
                        # Es una instancia existente, debería estar en saved_instances
                        if form_instance not in saved_instances:
                            saved_instances.append(form_instance)
                            print(f"[DEBUG FormSet.save] Agregando instancia existente del form {i}")
        
        print(f"[DEBUG FormSet.save] Total instancias a guardar: {len(saved_instances)}")
        
        # Guardar todas las instancias
        if commit:
            for instance in saved_instances:
                # Asegurarse de que la instancia tiene la relación con la comanda
                if not instance.id_comanda_id:
                    instance.id_comanda = self.instance
                instance.save()
                print(f"[DEBUG FormSet.save] Instancia guardada: id={instance.id_detalle_comanda}, plato={instance.id_plato_id}, cantidad={instance.cantidad}")
            
            # Guardar también los que se marcaron para eliminar
            self.save_m2m()
        
        return saved_instances


# Formset para gestionar múltiples detalles de comanda
DetalleComandaInlineFormSet = inlineformset_factory(
    Comanda,
    DetalleComanda,
    form=DetalleComandaForm,
    formset=DetalleComandaFormSet,
    extra=1,
    can_delete=True,
    fields=['id_plato', 'cantidad', 'observaciones'],
    validate_min=False,  # No validar mínimo en el formset base, lo hacemos en clean()
    min_num=0  # Permitir 0 inicialmente, validamos en clean()
)
