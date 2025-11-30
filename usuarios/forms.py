from django import forms
from django.contrib.auth.models import User, Group
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from django.core.exceptions import ValidationError
from .menus import MENUS_POR_SECCION, obtener_secciones
import logging

logger = logging.getLogger(__name__)


class UsuarioCrearForm(UserCreationForm):
    """Formulario para crear usuarios con selección de secciones"""
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'usuario@ejemplo.com'
        })
    )
    first_name = forms.CharField(
        required=True,
        max_length=30,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nombre'
        })
    )
    last_name = forms.CharField(
        required=True,
        max_length=30,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Apellido'
        })
    )
    
    # Secciones disponibles (grupos)
    SECCIONES_CHOICES = obtener_secciones()
    
    secciones = forms.MultipleChoiceField(
        choices=SECCIONES_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input'
        }),
        help_text='Selecciona las secciones a las que el usuario tendrá acceso'
    )
    
    # Menús por sección - se generan dinámicamente
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({'class': 'form-control'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control'})
        
        # Crear campos para cada menú de cada sección
        for seccion, menus in MENUS_POR_SECCION.items():
            for menu_id, menu_nombre in menus:
                field_name = f'menu_{seccion}_{menu_id}'
                self.fields[field_name] = forms.BooleanField(
                    required=False,
                    widget=forms.CheckboxInput(attrs={
                        'class': 'form-check-input menu-checkbox',
                        'data-seccion': seccion
                    }),
                    label=menu_nombre
                )
    
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'password1', 'password2', 'secciones']
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre de usuario'
            }),
        }
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        
        if commit:
            user.save()
            # Asignar grupos/secciones al usuario
            secciones = self.cleaned_data.get('secciones', [])
            
            # NOTA: La sección completa solo se guarda para referencia, pero NO otorga permisos
            # Los permisos se basan SOLO en los menús específicos marcados
            for seccion in secciones:
                group, created = Group.objects.get_or_create(name=seccion)
                user.groups.add(group)
                logger.debug(f"Agregado grupo de sección {seccion} al usuario {user.username} (solo referencia)")
            
            # Agregar grupos de menús específicos basado en los checks marcados
            # Esto funciona independientemente de si tiene la sección completa o no
            for seccion, menus in MENUS_POR_SECCION.items():
                for menu_id, menu_nombre in menus:
                    field_name = f'menu_{seccion}_{menu_id}'
                    if self.cleaned_data.get(field_name, False):
                        # Menú marcado: agregar grupo
                        group_name = f'{seccion}.{menu_id}'
                        group, created = Group.objects.get_or_create(name=group_name)
                        user.groups.add(group)
                        logger.debug(f"Agregado grupo {group_name} al usuario {user.username}")
                    else:
                        # Menú NO marcado: remover grupo si existe
                        group_name = f'{seccion}.{menu_id}'
                        try:
                            group = Group.objects.get(name=group_name)
                            if group in user.groups.all():
                                user.groups.remove(group)
                                logger.debug(f"Removido grupo {group_name} del usuario {user.username} (no marcado)")
                        except Group.DoesNotExist:
                            pass
        
        return user


class UsuarioEditarForm(forms.ModelForm):
    """Formulario para editar usuarios (solo superuser)"""
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control'
        })
    )
    first_name = forms.CharField(
        required=True,
        max_length=30,
        widget=forms.TextInput(attrs={
            'class': 'form-control'
        })
    )
    last_name = forms.CharField(
        required=True,
        max_length=30,
        widget=forms.TextInput(attrs={
            'class': 'form-control'
        })
    )
    is_active = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        help_text='Desmarcar para desactivar el usuario'
    )
    
    SECCIONES_CHOICES = obtener_secciones()
    
    secciones = forms.MultipleChoiceField(
        choices=SECCIONES_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input'
        }),
        help_text='Selecciona las secciones a las que el usuario tendrá acceso'
    )
    
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'is_active', 'secciones']
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-control',
                'readonly': True  # No permitir cambiar el username
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            # Pre-cargar las secciones actuales del usuario
            grupos_actuales = [g.name for g in self.instance.groups.all()]
            self.fields['secciones'].initial = [s for s, _ in self.SECCIONES_CHOICES if s in grupos_actuales]
            
            # Crear campos para cada menú de cada sección y pre-cargar valores
            for seccion, menus in MENUS_POR_SECCION.items():
                for menu_id, menu_nombre in menus:
                    field_name = f'menu_{seccion}_{menu_id}'
                    group_name = f'{seccion}.{menu_id}'
                    self.fields[field_name] = forms.BooleanField(
                        required=False,
                        widget=forms.CheckboxInput(attrs={
                            'class': 'form-check-input menu-checkbox',
                            'data-seccion': seccion
                        }),
                        label=menu_nombre
                    )
                    # Pre-cargar si el usuario tiene este menú asignado
                    self.fields[field_name].initial = group_name in grupos_actuales
        else:
            # Para nuevos usuarios, crear campos vacíos
            for seccion, menus in MENUS_POR_SECCION.items():
                for menu_id, menu_nombre in menus:
                    field_name = f'menu_{seccion}_{menu_id}'
                    self.fields[field_name] = forms.BooleanField(
                        required=False,
                        widget=forms.CheckboxInput(attrs={
                            'class': 'form-check-input menu-checkbox',
                            'data-seccion': seccion
                        }),
                        label=menu_nombre
                    )
    
    def save(self, commit=True):
        user = super().save(commit=False)
        
        if commit:
            user.save()
            # Actualizar grupos/secciones
            secciones = self.cleaned_data.get('secciones', [])
            
            # Remover todos los grupos de secciones
            grupos_secciones = [g for g in self.instance.groups.all() if g.name in [s[0] for s in self.SECCIONES_CHOICES]]
            for grupo in grupos_secciones:
                user.groups.remove(grupo)
            
            # Remover todos los grupos de menús existentes
            grupos_menus = []
            for seccion, menus in MENUS_POR_SECCION.items():
                for menu_id, _ in menus:
                    grupos_menus.append(f'{seccion}.{menu_id}')
            
            grupos_a_remover = [g for g in self.instance.groups.all() if g.name in grupos_menus]
            for grupo in grupos_a_remover:
                user.groups.remove(grupo)
            
            # NOTA: La sección completa solo se guarda para referencia, pero NO otorga permisos
            # Los permisos se basan SOLO en los menús específicos marcados
            for seccion in secciones:
                group, created = Group.objects.get_or_create(name=seccion)
                user.groups.add(group)
                logger.debug(f"Agregado grupo de sección {seccion} al usuario {user.username} (solo referencia)")
            
            # Agregar grupos de menús específicos basado en los checks marcados
            # Esto funciona independientemente de si tiene la sección completa o no
            for seccion, menus in MENUS_POR_SECCION.items():
                for menu_id, menu_nombre in menus:
                    field_name = f'menu_{seccion}_{menu_id}'
                    if self.cleaned_data.get(field_name, False):
                        # Menú marcado: agregar grupo
                        group_name = f'{seccion}.{menu_id}'
                        group, created = Group.objects.get_or_create(name=group_name)
                        user.groups.add(group)
                        logger.debug(f"Agregado grupo {group_name} al usuario {user.username}")
                    else:
                        # Menú NO marcado: remover grupo si existe
                        group_name = f'{seccion}.{menu_id}'
                        try:
                            group = Group.objects.get(name=group_name)
                            if group in user.groups.all():
                                user.groups.remove(group)
                                logger.debug(f"Removido grupo {group_name} del usuario {user.username} (no marcado)")
                        except Group.DoesNotExist:
                            pass
        
        return user


class CambiarContrasenaForm(PasswordChangeForm):
    """Formulario para cambiar contraseña"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['old_password'].widget.attrs.update({'class': 'form-control'})
        self.fields['new_password1'].widget.attrs.update({'class': 'form-control'})
        self.fields['new_password2'].widget.attrs.update({'class': 'form-control'})

