from django import template
register = template.Library()

@register.filter
def dict_get(dict_data, key):
    return dict_data.get(key)
