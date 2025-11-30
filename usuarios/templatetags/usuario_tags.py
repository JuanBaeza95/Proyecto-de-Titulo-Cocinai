from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Obtiene un item de un diccionario usando el key"""
    if dictionary is None:
        return None
    return dictionary.get(key)

@register.filter
def get_field(form, field_name):
    """Obtiene y renderiza un campo del formulario por nombre"""
    if form is None or field_name not in form.fields:
        return ""
    # Retornar el campo renderizado del formulario
    return form[field_name]

