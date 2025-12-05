from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('turnos', '0006_populate_existing_agenda'),
    ]

    operations = [
        migrations.AlterField(
            model_name='cupo',
            name='agenda',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cupos', to='turnos.agenda'),
        ),
        migrations.AlterField(
            model_name='turno',
            name='agenda',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='turnos', to='turnos.agenda'),
        ),
        migrations.AlterField(
            model_name='capacidaddia',
            name='agenda',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='capacidades', to='turnos.agenda'),
        ),
    ]
