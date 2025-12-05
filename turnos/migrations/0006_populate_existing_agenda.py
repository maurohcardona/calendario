from django.db import migrations


def set_existing_agenda(apps, schema_editor):
    Agenda = apps.get_model('turnos', 'Agenda')
    Cupo = apps.get_model('turnos', 'Cupo')
    Turno = apps.get_model('turnos', 'Turno')
    CapacidadDia = apps.get_model('turnos', 'CapacidadDia')

    try:
        amb = Agenda.objects.get(slug='ambulatorio')
    except Agenda.DoesNotExist:
        # If Ambulatorio doesn't exist, pick any agenda or do nothing
        amb = Agenda.objects.first()
        if amb is None:
            return

    Cupo.objects.filter(agenda__isnull=True).update(agenda=amb)
    Turno.objects.filter(agenda__isnull=True).update(agenda=amb)
    CapacidadDia.objects.filter(agenda__isnull=True).update(agenda=amb)


class Migration(migrations.Migration):

    dependencies = [
        ('turnos', '0005_merge_20251204_1227'),
    ]

    operations = [
        migrations.RunPython(set_existing_agenda, reverse_code=migrations.RunPython.noop),
    ]
