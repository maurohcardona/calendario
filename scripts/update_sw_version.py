#!/usr/bin/env python3
"""
Reemplaza CACHE_VERSION_PLACEHOLDER con timestamp en sw.js.
Ejecutar antes de collectstatic cuando haya cambios importantes.

Uso:
    python scripts/update_sw_version.py
"""
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SW_SOURCE = BASE_DIR / "static" / "sw.js"
PLACEHOLDER = "CACHE_VERSION_PLACEHOLDER"


def update_version() -> bool:
    """Actualiza la versión del Service Worker con timestamp actual."""
    if not SW_SOURCE.exists():
        print(f"❌ No se encuentra {SW_SOURCE}")
        return False

    content = SW_SOURCE.read_text(encoding="utf-8")

    if PLACEHOLDER not in content:
        print("⚠️  Placeholder no encontrado en sw.js")
        print("   El SW puede tener una versión ya fijada.")
        print("   Para resetear: restaurar CACHE_VERSION_PLACEHOLDER en static/sw.js")
        return False

    version = datetime.now().strftime("%Y%m%d-%H%M%S")
    updated = content.replace(PLACEHOLDER, version)
    SW_SOURCE.write_text(updated, encoding="utf-8")

    print(f"✅ Service Worker actualizado: lab-balestrini-{version}")
    print(f"   Archivo: {SW_SOURCE}")
    print()
    print("📋 Próximos pasos:")
    print("   python manage.py collectstatic --noinput")
    print("   Reiniciar servidor (python start_waitress.py)")
    return True


if __name__ == "__main__":
    update_version()
