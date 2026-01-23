# Generated migration for Medico model simplification

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('medicos', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='medico',
            name='apellido',
        ),
        migrations.RemoveField(
            model_name='medico',
            name='dni',
        ),
        migrations.RemoveField(
            model_name='medico',
            name='email',
        ),
        migrations.RemoveField(
            model_name='medico',
            name='telefono',
        ),
        migrations.RemoveField(
            model_name='medico',
            name='especialidad',
        ),
        migrations.RemoveField(
            model_name='medico',
            name='activo',
        ),
        migrations.RemoveField(
            model_name='medico',
            name='usuario',
        ),
        migrations.RemoveField(
            model_name='medico',
            name='creado',
        ),
        migrations.RemoveField(
            model_name='medico',
            name='actualizado',
        ),
        migrations.AddField(
            model_name='medico',
            name='matricula',
            field=models.CharField(max_length=100, unique=True, default=''),
            preserve_default=False,
        ),
        migrations.AlterModelOptions(
            name='medico',
            options={'ordering': ['nombre'], 'verbose_name': 'Médico', 'verbose_name_plural': 'Médicos'},
        ),
    ]
