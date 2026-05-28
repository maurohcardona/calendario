from django.db import migrations


SERVICIOS = [
    ("AMBULATORIO", "Consultorio externo"),
    ("GUARDIA", "Adultos"),
    ("GUARDIA", "Pediatría"),
    ("GUARDIA", "Ginecología"),
    ("INTERNACION", "Terapia intensiva"),
    ("INTERNACION", "Unidad Coronaria"),
    ("INTERNACION", "Observación"),
    ("INTERNACION", "Peine 5"),
    ("INTERNACION", "Peine 3"),
    ("INTERNACION", "Neonatología"),
    ("INTERNACION", "Peine 4"),
    ("INTERNACION", "Quirófano"),
    ("INTERNACION", "Pediatría"),
]


def cargar_servicios(apps, schema_editor):
    Servicio = apps.get_model("ordenes", "Servicio")
    for origen, nombre in SERVICIOS:
        Servicio.objects.get_or_create(origen=origen, nombre=nombre)


def eliminar_servicios(apps, schema_editor):
    Servicio = apps.get_model("ordenes", "Servicio")
    for origen, nombre in SERVICIOS:
        Servicio.objects.filter(origen=origen, nombre=nombre).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("ordenes", "0002_servicio_ordenlaboratorio_servicio"),
    ]

    operations = [
        migrations.RunPython(cargar_servicios, eliminar_servicios),
    ]
