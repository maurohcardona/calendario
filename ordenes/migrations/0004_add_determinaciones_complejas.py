from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("determinaciones", "0001_initial"),
        ("ordenes", "0003_datos_servicios"),
    ]

    operations = [
        migrations.AddField(
            model_name="ordenlaboratorio",
            name="determinaciones_complejas",
            field=models.ManyToManyField(
                blank=True,
                related_name="ordenes",
                to="determinaciones.determinacioncompleja",
            ),
        ),
    ]
