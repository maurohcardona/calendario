#!/usr/bin/env python3
"""
Genera iconos PWA en múltiples tamaños usando Pillow (sin CairoSVG).
Requiere: python3-pil (apt) o pip install Pillow
"""
import io
import os
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# Configuración
BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "static" / "icons"

# Colores del sistema (apple-design.css)
PRIMARY = (36, 143, 141)       # #248f8d turquesa
PRIMARY_DARK = (26, 114, 112)  # #1a7270
WHITE = (255, 255, 255)

# Tamaños requeridos para PWA
SIZES = {
    "icon-192x192.png": 192,
    "icon-512x512.png": 512,
    "apple-touch-icon.png": 180,
    "favicon.png": 32,
}

# Fuentes a intentar (en orden de preferencia)
BOLD_FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",  # macOS
]
REGULAR_FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    "/System/Library/Fonts/Helvetica.ttc",  # macOS
]


def get_font(candidates: list[str], size: int) -> ImageFont.FreeTypeFont:
    """Carga la primera fuente disponible de la lista."""
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def generate_icon(size: int) -> Image.Image:
    """Genera un ícono cuadrado con fondo blanco y texto LHB turquesa."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    radius = int(size * 0.156)
    border_w = max(2, int(size * 0.012))

    # Fondo blanco redondeado
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=WHITE)

    # Borde turquesa
    draw.rounded_rectangle(
        [border_w // 2, border_w // 2, size - 1 - border_w // 2, size - 1 - border_w // 2],
        radius=radius,
        fill=None,
        outline=PRIMARY,
        width=border_w,
    )

    # Texto "LBH"
    font = get_font(BOLD_FONTS, int(size * 0.35))
    text = "LHB"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (size - tw) // 2 - bbox[0]
    y = int(size * 0.35) - bbox[1]
    draw.text((x, y), text, font=font, fill=PRIMARY)

    # Subtítulo "LABORATORIO" (solo iconos >= 180px)
    if size >= 180:
        sub_font = get_font(REGULAR_FONTS, max(10, int(size * 0.07)))
        sub_text = "LABORATORIO"
        sub_bbox = draw.textbbox((0, 0), sub_text, font=sub_font)
        sw = sub_bbox[2] - sub_bbox[0]
        sx = (size - sw) // 2 - sub_bbox[0]
        sy = int(size * 0.78) - sub_bbox[1]
        draw.text((sx, sy), sub_text, font=sub_font, fill=PRIMARY_DARK)

    return img


def generate_icons() -> bool:
    """Genera todos los iconos PNG y el favicon.ico."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for filename, size in SIZES.items():
        output_path = OUTPUT_DIR / filename
        try:
            img = generate_icon(size)
            img.save(output_path, "PNG", optimize=True)
            kb = output_path.stat().st_size / 1024
            print(f"✅ {filename:25} ({size}x{size}px, {kb:.1f} KB)")
        except Exception as e:
            print(f"❌ Error generando {filename}: {e}")
            return False

    # Generar favicon.ico
    try:
        img32 = generate_icon(32)
        ico_path = OUTPUT_DIR / "favicon.ico"
        img32.save(ico_path, format="ICO", sizes=[(32, 32)])
        print("✅ favicon.ico              (32x32px)")
    except Exception as e:
        print(f"❌ Error generando favicon.ico: {e}")
        return False

    print(f"\n🎉 Iconos generados exitosamente en {OUTPUT_DIR}")
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("  GENERADOR DE ICONOS PWA - Laboratorio Balestrini")
    print("=" * 60)
    print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    success = generate_icons()

    if not success:
        print("\n⚠️  Verifica que tengas instalado:")
        print("   sudo apt install python3-pil")
        print("   o: pip install Pillow")
        raise SystemExit(1)

    print("\n📋 Próximos pasos:")
    print("   1. Verificar iconos: ls -lh static/icons/")
    print("   2. Ejecutar collectstatic: python manage.py collectstatic")
    print("   3. Verificar en navegador: DevTools → Application → Manifest")
