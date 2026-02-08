"""
Template tags y filtros personalizados para la aplicación turnos.
"""
from django import template
from django.utils.safestring import mark_safe
from datetime import date, datetime
from turnos.services import DeterminacionService

register = template.Library()


@register.filter(name='formato_fecha')
def formato_fecha(fecha_obj, formato='%d/%m/%Y'):
    """
    Formatea una fecha con el formato especificado.
    Uso: {{ fecha|formato_fecha:"%d/%m/%Y" }}
    """
    if not fecha_obj:
        return ''
    if isinstance(fecha_obj, str):
        try:
            fecha_obj = datetime.strptime(fecha_obj, '%Y-%m-%d').date()
        except:
            return fecha_obj
    try:
        return fecha_obj.strftime(formato)
    except:
        return str(fecha_obj)


@register.filter(name='calcular_edad')
def calcular_edad(fecha_nacimiento, fecha_referencia=None):
    """
    Calcula la edad a partir de una fecha de nacimiento.
    Uso: {{ fecha_nacimiento|calcular_edad }}
    """
    if not fecha_nacimiento:
        return None
    
    if fecha_referencia is None:
        fecha_referencia = date.today()
    elif isinstance(fecha_referencia, str):
        try:
            fecha_referencia = datetime.strptime(fecha_referencia, '%Y-%m-%d').date()
        except:
            fecha_referencia = date.today()
    
    if isinstance(fecha_nacimiento, str):
        try:
            fecha_nacimiento = datetime.strptime(fecha_nacimiento, '%Y-%m-%d').date()
        except:
            return None
    
    edad = fecha_referencia.year - fecha_nacimiento.year
    if (fecha_referencia.month, fecha_referencia.day) < (fecha_nacimiento.month, fecha_nacimiento.day):
        edad -= 1
    return edad


@register.filter(name='nombres_determinaciones')
def nombres_determinaciones(codigos_texto):
    """
    Convierte códigos de determinaciones a nombres legibles.
    Uso: {{ turno.determinaciones|nombres_determinaciones }}
    """
    if not codigos_texto:
        return ''
    
    nombres = DeterminacionService.obtener_nombres_determinaciones(codigos_texto)
    return ', '.join(nombres) if nombres else codigos_texto


@register.filter(name='capitalize_nombre')
def capitalize_nombre(texto):
    """
    Capitaliza un nombre (primera letra mayúscula, resto minúscula).
    Uso: {{ nombre|capitalize_nombre }}
    """
    if not texto:
        return ''
    return texto.strip().capitalize()


@register.filter(name='formato_nombre_completo')
def formato_nombre_completo(apellido, nombre):
    """
    Formatea nombre completo como "Apellido, Nombre".
    Uso: {{ apellido|formato_nombre_completo:nombre }}
    """
    apellido_fmt = apellido.strip().capitalize() if apellido else ''
    nombre_fmt = nombre.strip().capitalize() if nombre else ''
    if apellido_fmt and nombre_fmt:
        return f"{apellido_fmt}, {nombre_fmt}"
    return apellido_fmt or nombre_fmt


@register.simple_tag
def input_field(label, name, value='', tipo='text', required=False, readonly=False, **kwargs):
    """
    Genera un campo de formulario con estilo consistente.
    Uso: {% input_field "DNI" "dni" value=paciente.dni required=True %}
    """
    required_attr = 'required' if required else ''
    readonly_attr = 'readonly' if readonly else ''
    value_attr = f'value="{value}"' if value else ''
    
    extra_attrs = ' '.join([f'{k}="{v}"' for k, v in kwargs.items()])
    
    input_html = f'''
    <div style="margin-bottom: 1.2rem;">
        <label style="color: var(--text-light); font-weight: 600; display: block; margin-bottom: 0.5rem; font-size: 0.95rem;">
            {label}
        </label>
        <input 
            type="{tipo}" 
            name="{name}" 
            {value_attr}
            {required_attr}
            {readonly_attr}
            {extra_attrs}
            style="width: 100%; background: #fff; border: 2px solid var(--accent); color: var(--text-light); padding: 0.75rem; border-radius: 8px; font-family: inherit; font-size: 1.1rem; font-weight: 700;"
        />
    </div>
    '''
    return mark_safe(input_html)


@register.simple_tag
def badge_estado(estado):
    """
    Genera un badge con color según el estado.
    Uso: {% badge_estado "coordinado" %}
    """
    colores = {
        'coordinado': 'background: #8fb88f; color: white;',
        'pendiente': 'background: #e8b88f; color: white;',
        'completo': 'background: #d89090; color: white;',
        'disponible': 'background: #8fb88f; color: white;',
    }
    
    estilo = colores.get(estado.lower(), 'background: #9e9e9e; color: white;')
    
    return mark_safe(f'<span style="padding: 0.25rem 0.75rem; border-radius: 12px; font-size: 0.85rem; font-weight: 600; {estilo}">{estado.upper()}</span>')


@register.filter(name='es_fecha_pasada')
def es_fecha_pasada(fecha_obj):
    """
    Verifica si una fecha es pasada.
    Uso: {% if fecha|es_fecha_pasada %}...{% endif %}
    """
    if not fecha_obj:
        return False
    
    if isinstance(fecha_obj, str):
        try:
            fecha_obj = datetime.strptime(fecha_obj, '%Y-%m-%d').date()
        except:
            return False
    
    return fecha_obj < date.today()


@register.filter(name='icono_sexo')
def icono_sexo(sexo):
    """
    Retorna un icono según el sexo.
    Uso: {{ paciente.sexo|icono_sexo }}
    """
    iconos = {
        'Masculino': '♂',
        'Femenino': '♀',
        'Sin asignar': '⚲',
        'Desconocido': '?',
    }
    return iconos.get(sexo, '?')


@register.inclusion_tag('turnos/components/banner_feriado.html')
def banner_feriado(descripcion=''):
    """
    Genera un banner de advertencia para feriados.
    Uso: {% banner_feriado descripcion="Día de la Independencia" %}
    """
    return {
        'es_feriado': True,
        'descripcion': descripcion,
    }


@register.inclusion_tag('turnos/components/card_info.html')
def card_info(titulo, valor, icono='', color='var(--accent)'):
    """
    Genera una tarjeta de información.
    Uso: {% card_info "Cupo total" cupo.cantidad_total icono="📊" %}
    """
    return {
        'titulo': titulo,
        'valor': valor,
        'icono': icono,
        'color': color,
    }


@register.filter(name='dividir_texto_largo')
def dividir_texto_largo(texto, max_length=40):
    """
    Divide un texto largo en múltiples líneas.
    Uso: {{ texto|dividir_texto_largo:40 }}
    """
    if not texto or len(texto) <= max_length:
        return [texto]
    
    lineas = []
    palabras = texto.split()
    linea_actual = ""
    
    for palabra in palabras:
        if len(linea_actual) + len(palabra) + 1 <= max_length:
            linea_actual += (" " if linea_actual else "") + palabra
        else:
            if linea_actual:
                lineas.append(linea_actual)
            linea_actual = palabra
    
    if linea_actual:
        lineas.append(linea_actual)
    
    return lineas


@register.filter(name='color_disponibilidad')
def color_disponibilidad(disponibles):
    """
    Retorna un color según la disponibilidad.
    Uso: style="color: {{ disponibles|color_disponibilidad }};"
    """
    if disponibles == 0:
        return '#d89090'  # Rojo
    elif disponibles <= 5:
        return '#e8b88f'  # Naranja
    else:
        return '#8fb88f'  # Verde
