"""
Utilidades para manipulación de colores.

Este módulo contiene funciones para convertir, modificar y analizar colores
en diferentes formatos (hex, RGB, RGBA), incluyendo cálculo de contraste WCAG.
"""

from typing import Tuple, Dict


def hex_to_rgb(color_hex: str) -> Tuple[int, int, int]:
    """
    Convierte un color hexadecimal a RGB.

    Args:
        color_hex: Color en formato hexadecimal (#RRGGBB o RRGGBB)

    Returns:
        Tupla con valores RGB (r, g, b) en rango 0-255

    Raises:
        ValueError: Si el formato hexadecimal es inválido

    Example:
        >>> hex_to_rgb("#ff5733")
        (255, 87, 51)
        >>> hex_to_rgb("007aff")
        (0, 122, 255)
    """
    color_hex = color_hex.lstrip("#")

    if len(color_hex) != 6:
        raise ValueError(
            f"Color hexadecimal inválido: {color_hex}. Debe tener 6 caracteres."
        )

    try:
        r = int(color_hex[0:2], 16)
        g = int(color_hex[2:4], 16)
        b = int(color_hex[4:6], 16)
        return (r, g, b)
    except ValueError as e:
        raise ValueError(f"Color hexadecimal inválido: {color_hex}. {str(e)}")


def rgb_to_hex(r: int, g: int, b: int) -> str:
    """
    Convierte valores RGB a formato hexadecimal.

    Args:
        r: Valor rojo (0-255)
        g: Valor verde (0-255)
        b: Valor azul (0-255)

    Returns:
        Color en formato hexadecimal (#RRGGBB)

    Example:
        >>> rgb_to_hex(255, 87, 51)
        '#ff5733'
        >>> rgb_to_hex(0, 122, 255)
        '#007aff'
    """
    # Asegurar que los valores estén en rango 0-255
    r = max(0, min(255, r))
    g = max(0, min(255, g))
    b = max(0, min(255, b))

    return f"#{r:02x}{g:02x}{b:02x}"


def lighten_color(color_hex: str, factor: float = 0.6) -> str:
    """
    Aclara un color hexadecimal.

    Interpola el color hacia el blanco según el factor especificado.
    Movido desde turnos.views.calendar_views para centralizar utilidades.

    Args:
        color_hex: Color en formato hexadecimal (#RRGGBB)
        factor: Factor de aclarado (0.0 = original, 1.0 = blanco). Default: 0.6

    Returns:
        Color aclarado en formato hexadecimal

    Example:
        >>> lighten_color("#007aff", 0.5)
        '#80bcff'
        >>> lighten_color("#ff0000", 0.3)
        '#ff4d4d'
    """
    if not color_hex or not color_hex.startswith("#"):
        return color_hex

    try:
        r, g, b = hex_to_rgb(color_hex)

        # Interpolar hacia blanco (255, 255, 255)
        r = int(r + (255 - r) * factor)
        g = int(g + (255 - g) * factor)
        b = int(b + (255 - b) * factor)

        return rgb_to_hex(r, g, b)
    except (ValueError, IndexError):
        return color_hex


def darken_color(color_hex: str, factor: float = 0.3) -> str:
    """
    Oscurece un color hexadecimal.

    Interpola el color hacia el negro según el factor especificado.

    Args:
        color_hex: Color en formato hexadecimal (#RRGGBB)
        factor: Factor de oscurecimiento (0.0 = original, 1.0 = negro). Default: 0.3

    Returns:
        Color oscurecido en formato hexadecimal

    Example:
        >>> darken_color("#007aff", 0.3)
        '#005ab3'
        >>> darken_color("#ff0000", 0.5)
        '#800000'
    """
    if not color_hex or not color_hex.startswith("#"):
        return color_hex

    try:
        r, g, b = hex_to_rgb(color_hex)

        # Interpolar hacia negro (0, 0, 0)
        r = int(r * (1 - factor))
        g = int(g * (1 - factor))
        b = int(b * (1 - factor))

        return rgb_to_hex(r, g, b)
    except (ValueError, IndexError):
        return color_hex


def adjust_opacity(color_hex: str, opacity: float = 0.8) -> str:
    """
    Convierte un color hexadecimal a formato rgba con opacidad.

    Args:
        color_hex: Color en formato hexadecimal (#RRGGBB)
        opacity: Nivel de opacidad (0.0 = transparente, 1.0 = opaco). Default: 0.8

    Returns:
        Color en formato rgba(r, g, b, opacity)

    Example:
        >>> adjust_opacity("#007aff", 0.5)
        'rgba(0, 122, 255, 0.5)'
        >>> adjust_opacity("#ff0000", 0.8)
        'rgba(255, 0, 0, 0.8)'
    """
    if not color_hex or not color_hex.startswith("#"):
        return color_hex

    try:
        r, g, b = hex_to_rgb(color_hex)
        opacity = max(0.0, min(1.0, opacity))  # Limitar entre 0 y 1

        return f"rgba({r}, {g}, {b}, {opacity})"
    except (ValueError, IndexError):
        return color_hex


def get_contrast_text_color(bg_color_hex: str) -> str:
    """
    Calcula el color de texto óptimo (blanco o negro) para un fondo dado.

    Utiliza la fórmula de luminancia relativa según WCAG 2.0 para determinar
    si el texto debe ser oscuro o claro según el color de fondo.

    Args:
        bg_color_hex: Color de fondo en formato hexadecimal (#RRGGBB)

    Returns:
        '#ffffff' (blanco) o '#1d1d1f' (negro Apple) según el contraste óptimo

    Example:
        >>> get_contrast_text_color("#007aff")  # Azul Apple
        '#ffffff'
        >>> get_contrast_text_color("#f5f5f7")  # Gris muy claro
        '#1d1d1f'

    References:
        https://www.w3.org/WAI/WCAG21/Understanding/contrast-minimum.html
    """
    if not bg_color_hex or not bg_color_hex.startswith("#"):
        return "#1d1d1f"  # Negro por defecto

    try:
        r, g, b = hex_to_rgb(bg_color_hex)

        # Normalizar valores RGB a rango 0-1
        r_norm = r / 255.0
        g_norm = g / 255.0
        b_norm = b / 255.0

        # Aplicar corrección gamma según WCAG
        def gamma_correct(channel: float) -> float:
            if channel <= 0.03928:
                return channel / 12.92
            else:
                return ((channel + 0.055) / 1.055) ** 2.4

        r_linear = gamma_correct(r_norm)
        g_linear = gamma_correct(g_norm)
        b_linear = gamma_correct(b_norm)

        # Calcular luminancia relativa (WCAG formula)
        luminance = 0.2126 * r_linear + 0.7152 * g_linear + 0.0722 * b_linear

        # Si luminancia > 0.5, usar texto oscuro; caso contrario, texto claro
        # Threshold ajustado para estética Apple (más conservador)
        return "#1d1d1f" if luminance > 0.4 else "#ffffff"

    except (ValueError, IndexError):
        return "#1d1d1f"  # Negro por defecto en caso de error


def generate_color_palette(base_color_hex: str) -> Dict[str, str]:
    """
    Genera una paleta completa de colores a partir de un color base.

    Crea variantes claras, oscuras y con opacidad del color base, útil para
    mantener consistencia visual en toda la interfaz.

    Args:
        base_color_hex: Color base en formato hexadecimal (#RRGGBB)

    Returns:
        Diccionario con las siguientes claves:
        - base: Color original
        - light: Versión aclarada (30%)
        - lighter: Versión muy aclarada (60%)
        - dark: Versión oscurecida (20%)
        - darker: Versión muy oscurecida (40%)
        - opacity_80: Color con 80% opacidad
        - opacity_50: Color con 50% opacidad
        - opacity_20: Color con 20% opacidad
        - text_color: Color de texto recomendado sobre el color base

    Example:
        >>> palette = generate_color_palette("#007aff")
        >>> palette['base']
        '#007aff'
        >>> palette['light']
        '#4d9fff'
        >>> palette['text_color']
        '#ffffff'
    """
    return {
        "base": base_color_hex,
        "light": lighten_color(base_color_hex, 0.3),
        "lighter": lighten_color(base_color_hex, 0.6),
        "dark": darken_color(base_color_hex, 0.2),
        "darker": darken_color(base_color_hex, 0.4),
        "opacity_80": adjust_opacity(base_color_hex, 0.8),
        "opacity_50": adjust_opacity(base_color_hex, 0.5),
        "opacity_20": adjust_opacity(base_color_hex, 0.2),
        "text_color": get_contrast_text_color(base_color_hex),
    }
