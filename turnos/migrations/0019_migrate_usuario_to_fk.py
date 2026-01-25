# Generated manually to migrate usuario from CharField to ForeignKey

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def convert_usuario_strings_to_fk(apps, schema_editor):
    """Convierte los valores string del campo usuario a ForeignKeys"""
    User = apps.get_model('auth', 'User')
    Turno = apps.get_model('turnos', 'Turno')
    Coordinados = apps.get_model('turnos', 'Coordinados')
    
    # Crear un diccionario de username -> user_id
    user_map = {}
    for user in User.objects.all():
        user_map[user.username] = user.id
    
    # Actualizar Turnos - primero necesitamos agregar un campo temporal
    # Nota: Como el campo ya existe como CharField, necesitamos manejarlo diferente
    pass


def reverse_usuario_fk_to_strings(apps, schema_editor):
    """Revierte la conversión (para rollback)"""
    pass


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('turnos', '0018_remove_coordinados_apellido_and_more'),
    ]

    operations = [
        # Paso 1: Agregar campo temporal para la FK
        migrations.AddField(
            model_name='turno',
            name='usuario_fk_temp',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='turnos_temp',
                to=settings.AUTH_USER_MODEL
            ),
        ),
        migrations.AddField(
            model_name='coordinados',
            name='usuario_fk_temp',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to=settings.AUTH_USER_MODEL,
                verbose_name='Usuario que coordinó'
            ),
        ),
        # Paso 2: Migrar datos del campo string al campo FK
        migrations.RunPython(
            lambda apps, schema_editor: migrate_usuario_data(apps, schema_editor),
            reverse_code=migrations.RunPython.noop,
        ),
        # Paso 3: Eliminar el campo antiguo
        migrations.RemoveField(
            model_name='turno',
            name='usuario',
        ),
        migrations.RemoveField(
            model_name='coordinados',
            name='usuario',
        ),
        # Paso 4: Renombrar el campo temporal al nombre correcto
        migrations.RenameField(
            model_name='turno',
            old_name='usuario_fk_temp',
            new_name='usuario',
        ),
        migrations.RenameField(
            model_name='coordinados',
            old_name='usuario_fk_temp',
            new_name='usuario',
        ),
    ]


def migrate_usuario_data(apps, schema_editor):
    """Migra los datos del campo usuario (CharField) a usuario_fk_temp (ForeignKey)"""
    User = apps.get_model('auth', 'User')
    Turno = apps.get_model('turnos', 'Turno')
    Coordinados = apps.get_model('turnos', 'Coordinados')
    
    # Crear un diccionario de username -> User object
    user_map = {user.username: user for user in User.objects.all()}
    
    # Migrar Turnos
    for turno in Turno.objects.all():
        if turno.usuario:
            user = user_map.get(turno.usuario)
            if user:
                turno.usuario_fk_temp = user
                turno.save()
    
    # Migrar Coordinados
    for coordinado in Coordinados.objects.all():
        if coordinado.usuario:
            user = user_map.get(coordinado.usuario)
            if user:
                coordinado.usuario_fk_temp = user
                coordinado.save()
