from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('turnos', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE turnos_turno ALTER COLUMN dni_id DROP NOT NULL;",
            reverse_sql="ALTER TABLE turnos_turno ALTER COLUMN dni_id SET NOT NULL;",
        ),
    ]
