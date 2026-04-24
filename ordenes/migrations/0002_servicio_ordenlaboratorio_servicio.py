from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("ordenes", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="ordenlaboratorio",
            name="servicio",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="ordenes.servicio",
            ),
        ),
    ]
