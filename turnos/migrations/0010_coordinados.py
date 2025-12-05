# Generated migration for Coordinados model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('turnos', '0009_turnomensual'),
    ]

    operations = [
        migrations.CreateModel(
            name='Coordinados',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('id_turno', models.IntegerField(unique=True, verbose_name='ID del Turno')),
                ('nombre', models.CharField(max_length=200, verbose_name='Nombre')),
                ('apellido', models.CharField(max_length=200, verbose_name='Apellido')),
                ('dni', models.CharField(max_length=20, verbose_name='DNI')),
                ('fecha_coordinacion', models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Coordinación')),
                ('determinaciones', models.TextField(blank=True, verbose_name='Determinaciones')),
            ],
            options={
                'verbose_name': 'Turno Coordinado',
                'verbose_name_plural': 'Turnos Coordinados',
                'ordering': ['-fecha_coordinacion'],
            },
        ),
    ]
