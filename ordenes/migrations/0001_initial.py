from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("determinaciones", "0001_initial"),
        ("medicos", "0001_initial"),
        ("pacientes", "0001_initial"),
        ("turnos", "0001_initial"),
        ("auth", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Servicio",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "origen",
                    models.CharField(
                        choices=[
                            ("AMBULATORIO", "Ambulatorio"),
                            ("GUARDIA", "Guardia"),
                            ("INTERNACION", "Internación"),
                        ],
                        max_length=20,
                    ),
                ),
                ("nombre", models.CharField(max_length=100)),
                ("activo", models.BooleanField(default=True)),
            ],
            options={
                "verbose_name": "Servicio",
                "verbose_name_plural": "Servicios",
                "ordering": ["origen", "nombre"],
            },
        ),
        migrations.CreateModel(
            name="OrdenLaboratorio",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "tipo_origen",
                    models.CharField(
                        choices=[
                            ("AMBULATORIO", "Ambulatorio"),
                            ("GUARDIA", "Guardia"),
                            ("INTERNACION", "Internación"),
                        ],
                        max_length=20,
                    ),
                ),
                ("sala", models.CharField(blank=True, default="", max_length=50)),
                (
                    "estado",
                    models.CharField(
                        choices=[
                            ("PENDIENTE", "Pendiente"),
                            ("INGRESADA", "Ingresada"),
                            ("COMPLETADA", "Completada"),
                            ("CANCELADA", "Cancelada"),
                        ],
                        default="PENDIENTE",
                        max_length=20,
                    ),
                ),
                ("observaciones", models.TextField(blank=True, default="")),
                ("urgente", models.BooleanField(default=False)),
                ("fecha_creacion", models.DateTimeField(auto_now_add=True)),
                ("fecha_actualizacion", models.DateTimeField(auto_now=True)),
                ("numero_orden_lab", models.CharField(blank=True, default="", max_length=50)),
                ("observaciones_lab", models.TextField(blank=True, default="")),
                (
                    "creado_por",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="ordenes_creadas",
                        to="auth.user",
                    ),
                ),
                (
                    "determinaciones",
                    models.ManyToManyField(
                        blank=True,
                        related_name="ordenes",
                        to="determinaciones.determinacion",
                    ),
                ),
                (
                    "medico",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="ordenes",
                        to="medicos.medico",
                    ),
                ),
                (
                    "paciente",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="ordenes",
                        to="pacientes.paciente",
                    ),
                ),
                (
                    "turno",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="ordenes",
                        to="turnos.turno",
                    ),
                ),
            ],
            options={
                "verbose_name": "Orden de Laboratorio",
                "verbose_name_plural": "Órdenes de Laboratorio",
                "ordering": ["-fecha_creacion"],
            },
        ),
    ]
