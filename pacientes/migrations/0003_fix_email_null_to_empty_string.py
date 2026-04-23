from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Corrige registros con email=NULL en produccion.
    La migracion 0002 elimino null=True del campo email, pero habia registros
    existentes con NULL. Esta migracion convierte esos NULLs a string vacio
    antes de que PostgreSQL rechace el NOT NULL constraint al actualizar.
    """

    dependencies = [
        ("pacientes", "0002_alter_paciente_options_alter_paciente_apellido_and_more"),
    ]

    operations = [
        migrations.RunSQL(
            sql="UPDATE pacientes_paciente SET email = '' WHERE email IS NULL;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="UPDATE pacientes_paciente SET observaciones = '' WHERE observaciones IS NULL;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="UPDATE pacientes_paciente SET telefono = '' WHERE telefono IS NULL;",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
