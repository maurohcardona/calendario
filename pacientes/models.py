from django.db import models
from datetime import date


class Paciente(models.Model):
    """Modelo que representa un paciente del sistema de salud."""

    TIPO_IDEN_CHOICES = [
        ("DNI", "DNI"),
        ("CI", "Ci"),
        ("LC", "LC"),
        ("LE", "LE"),
        ("Pasaporte", "Pasaporte"),
        ("Otro", "Otro"),
        ("PRO", "PRO"),
        ("NEO", "NEO"),
        ("NN", "NN"),
    ]

    SEXO_CHOICES = [
        ("Masculino", "Masculino"),
        ("Femenino", "Femenino"),
        ("Sin asignar", "Sin asignar"),
    ]

    tipo_iden = models.CharField(
        max_length=15,
        choices=TIPO_IDEN_CHOICES,
        default="DNI",
        blank=False,
        null=False,
        verbose_name="Tipo de Identificación",
        help_text="Tipo de documento de identidad del paciente",
    )

    iden = models.CharField(
        max_length=25,
        verbose_name="Identificación",
        help_text="Número de documento de identidad del paciente",
    )
    nombre = models.CharField(max_length=30, verbose_name="Nombre")
    apellido = models.CharField(max_length=30, verbose_name="Apellido")
    fecha_nacimiento = models.DateField(verbose_name="Fecha de Nacimiento")
    sexo = models.CharField(
        max_length=15, choices=SEXO_CHOICES, default="Sin asignar", verbose_name="Sexo"
    )
    telefono = models.CharField(
        max_length=50,
        blank=True,
        default="",
        verbose_name="Teléfono",
        help_text="Número de teléfono de contacto",
    )
    email = models.EmailField(
        blank=True,
        default="",
        verbose_name="Email",
        help_text="Correo electrónico del paciente",
    )
    observaciones = models.TextField(
        blank=True,
        default="",
        verbose_name="Observaciones",
        help_text="Notas adicionales sobre el paciente",
    )

    class Meta:
        verbose_name = "Paciente"
        verbose_name_plural = "Pacientes"
        ordering = ["apellido", "nombre"]
        unique_together = [("tipo_iden", "iden")]
        indexes = [
            models.Index(fields=["tipo_iden", "iden"]),
            models.Index(fields=["iden"]),
            models.Index(fields=["apellido", "nombre"]),
        ]

    @property
    def edad(self) -> int:
        """Calcula la edad del paciente en años."""
        today = date.today()
        return (
            today.year
            - self.fecha_nacimiento.year
            - (
                (today.month, today.day)
                < (self.fecha_nacimiento.month, self.fecha_nacimiento.day)
            )
        )

    @property
    def nombre_completo(self) -> str:
        """Retorna el nombre completo del paciente."""
        return f"{self.apellido}, {self.nombre}"

    def __str__(self) -> str:
        return self.nombre_completo
