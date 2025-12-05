from django.db import migrations


def create_agendas(apps, schema_editor):
    Agenda = apps.get_model('turnos', 'Agenda')
    default = [
        ('Ambulatorio', 'ambulatorio', '#00d4ff'),
        ('Curvas', 'curvas', '#ffd54f'),
        ('Emergencia', 'emergencia', '#ff5252'),
    ]
    for name, slug, color in default:
        Agenda.objects.get_or_create(slug=slug, defaults={'name': name, 'color': color})


class Migration(migrations.Migration):

    dependencies = [
        ('turnos', '0005_agenda_alter_capacidaddia_fecha_alter_cupo_fecha_and_more'),
    ]

    operations = [
        migrations.RunPython(create_agendas, reverse_code=migrations.RunPython.noop),
    ]
