# Generated manually to update Pediatricos agenda color

from django.db import migrations


def update_pediatricos_color(apps, schema_editor):
    """Actualizar el color de la agenda Pediatricos a #248F8D (teal oscuro)"""
    Agenda = apps.get_model("turnos", "Agenda")

    try:
        pediatricos = Agenda.objects.get(slug="pediatricos")
        pediatricos.color = "#248F8D"
        pediatricos.save()
        print(f"✓ Agenda 'Pediatricos' actualizada con color #248F8D")
    except Agenda.DoesNotExist:
        print("⚠ Agenda 'Pediatricos' no encontrada, omitiendo actualización")


def reverse_pediatricos_color(apps, schema_editor):
    """Revertir el color de la agenda Pediatricos a su valor anterior"""
    Agenda = apps.get_model("turnos", "Agenda")

    try:
        pediatricos = Agenda.objects.get(slug="pediatricos")
        pediatricos.color = "#66FF66"
        pediatricos.save()
        print(f"✓ Agenda 'Pediatricos' revertida a color #66FF66")
    except Agenda.DoesNotExist:
        print("⚠ Agenda 'Pediatricos' no encontrada, omitiendo reversión")


class Migration(migrations.Migration):
    dependencies = [
        ("turnos", "0003_actualizar_colores_agendas"),
    ]

    operations = [
        migrations.RunPython(update_pediatricos_color, reverse_pediatricos_color),
    ]
