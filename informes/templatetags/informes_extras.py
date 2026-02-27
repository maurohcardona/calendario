from django import template
from pathlib import Path

register = template.Library()


@register.filter
def pdf_label(nombre_archivo):
    """
    Dado un nombre de archivo como 'Ambulatorio_34922207_20001-101.pdf',
    devuelve 'DNI: 34922207 | Pet: 20001-101'.
    Si el formato no es reconocido devuelve el nombre tal cual.
    """
    try:
        stem = Path(nombre_archivo).stem          # 'Ambulatorio_34922207_20001-101'
        partes = stem.split('_')
        if len(partes) == 3:
            return f"DNI: {partes[1]}  |  Pet: {partes[2]}"
    except Exception:
        pass
    return nombre_archivo
