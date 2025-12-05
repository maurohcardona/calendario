from django.db import migrations


def create_weekly_availability(apps, schema_editor):
    Agenda = apps.get_model('turnos', 'Agenda')
    WeeklyAvailability = apps.get_model('turnos', 'WeeklyAvailability')

    # Capacidades por defecto para Lunes(0)-Viernes(4). Sábado(5) y Domingo(6) inactivos.
    defaults = {
        'ambulatorio': {0: 10, 1: 10, 2: 10, 3: 10, 4: 8},
        'curvas': {0: 6, 1: 8, 2: 6, 3: 8, 4: 6},
        'emergencia': {0: 20, 1: 20, 2: 20, 3: 20, 4: 20},
    }

    for slug, schedule in defaults.items():
        try:
            ag = Agenda.objects.get(slug=slug)
        except Agenda.DoesNotExist:
            # Si no existe la agenda, saltar
            continue

        for weekday in range(7):
            if weekday <= 4:
                capacidad = schedule.get(weekday, 0)
                active = capacidad > 0
            else:
                capacidad = 0
                active = False

            WeeklyAvailability.objects.get_or_create(
                agenda=ag,
                weekday=weekday,
                defaults={
                    'capacidad': capacidad,
                    'active': active,
                }
            )


class Migration(migrations.Migration):

    dependencies = [
        ('turnos', '0005_agenda_alter_capacidaddia_fecha_alter_cupo_fecha_and_more'),
    ]

    operations = [
        migrations.RunPython(create_weekly_availability, reverse_code=migrations.RunPython.noop),
    ]
