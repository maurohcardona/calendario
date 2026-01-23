# Generated migration for Turno model - Change medico from CharField to ForeignKey

from django.db import migrations, models
import django.db.models.deletion


def migrate_medicos_forward(apps, schema_editor):
    """Migra los médicos existentes de texto a objetos Medico."""
    Turno = apps.get_model('turnos', 'Turno')
    Medico = apps.get_model('medicos', 'Medico')
    
    medicos_unicos = set()
    for turno in Turno.objects.filter(medico__isnull=False).exclude(medico=''):
        if turno.medico and turno.medico.strip():
            medicos_unicos.add(turno.medico.strip())
    
    # Crear médicos nuevos para cada nombre único encontrado
    for nombre_medico in medicos_unicos:
        if nombre_medico:
            # Dividir en apellido y nombre si es posible
            partes = nombre_medico.rsplit(' ', 1)
            if len(partes) == 2:
                apellido, nombre = partes
            else:
                apellido = nombre_medico
                nombre = ''
            
            Medico.objects.get_or_create(
                nombre=nombre,
                apellido=apellido,
                defaults={
                    'dni': '',
                    'email': '',
                    'telefono': '',
                    'especialidad': '',
                    'activo': True,
                }
            )
    
    # Actualizar los turnos con referencias a los objetos Medico
    for turno in Turno.objects.filter(medico__isnull=False).exclude(medico=''):
        if turno.medico and turno.medico.strip():
            nombre_medico = turno.medico.strip()
            partes = nombre_medico.rsplit(' ', 1)
            if len(partes) == 2:
                apellido, nombre = partes
            else:
                apellido = nombre_medico
                nombre = ''
            
            try:
                medico_obj = Medico.objects.get(nombre=nombre, apellido=apellido)
                turno.medico_fk = medico_obj
                turno.save()
            except Medico.DoesNotExist:
                pass


def migrate_medicos_reverse(apps, schema_editor):
    """Revertir la migración no es necesario."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('medicos', '0001_initial'),
        ('turnos', '0015_feriados_remove_turnomensual_agenda_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='turno',
            name='medico_fk',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='turnos', to='medicos.medico'),
        ),
        migrations.RunPython(
            code=migrate_medicos_forward,
            reverse_code=migrate_medicos_reverse,
        ),
        migrations.RemoveField(
            model_name='turno',
            name='medico',
        ),
        migrations.RenameField(
            model_name='turno',
            old_name='medico_fk',
            new_name='medico',
        ),
    ]
