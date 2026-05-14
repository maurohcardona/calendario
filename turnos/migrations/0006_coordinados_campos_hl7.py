"""
Migración: agrega campos HL7 al modelo Coordinados.

Agrega:
- mensaje_tipo: ASTM (legacy) o HL7
- mensaje_hl7: contenido ER7 del mensaje OML^O21 generado
- ack_recibido: contenido ER7 del ACK recibido del LIS
- ack_estado: AA (aceptado), AE (error de aplicación), AR (rechazado)
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("turnos", "0005_alter_agenda_options_alter_cupo_options_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="coordinados",
            name="mensaje_tipo",
            field=models.CharField(
                max_length=10,
                choices=[("ASTM", "ASTM (legacy)"), ("HL7", "HL7 v2.5")],
                default="HL7",
                verbose_name="Tipo de Mensaje",
                help_text="Protocolo de mensajería utilizado para la coordinación",
            ),
        ),
        migrations.AddField(
            model_name="coordinados",
            name="mensaje_hl7",
            field=models.TextField(
                blank=True,
                default="",
                verbose_name="Mensaje HL7",
                help_text="Contenido ER7 del mensaje OML^O21 generado",
            ),
        ),
        migrations.AddField(
            model_name="coordinados",
            name="ack_recibido",
            field=models.TextField(
                blank=True,
                default="",
                verbose_name="ACK Recibido",
                help_text="Contenido ER7 del ACK recibido del LIS",
            ),
        ),
        migrations.AddField(
            model_name="coordinados",
            name="ack_estado",
            field=models.CharField(
                max_length=2,
                blank=True,
                default="",
                choices=[
                    ("AA", "Aceptado (AA)"),
                    ("AE", "Error de Aplicación (AE)"),
                    ("AR", "Rechazado (AR)"),
                ],
                verbose_name="Estado ACK",
                help_text="Estado de la confirmación recibida del LIS",
            ),
        ),
    ]
