from django import template

register = template.Library()

@register.filter
def dict_key(d, key):
    try:
        return d.get(key)
    except:
        return None

@register.filter
def get_item(dictionary, key):
    """Devuelve el valor de una clave en un diccionario o None si no existe."""
    return dictionary.get(key, 0)