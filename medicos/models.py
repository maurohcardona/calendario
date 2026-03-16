from django.db import models


class Medico(models.Model):
    """Modelo que representa un médico profesional del sistema."""

    nombre = models.CharField(
        max_length=200, verbose_name="Nombre", help_text="Nombre completo del médico"
    )
    matricula = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Matrícula",
        help_text="Número de matrícula profesional",
    )

    class Meta:
        verbose_name = "Médico"
        verbose_name_plural = "Médicos"
        ordering = ["nombre"]
        indexes = [
            models.Index(fields=["matricula"]),
            models.Index(fields=["nombre"]),
        ]

    def __str__(self) -> str:
        return f"{self.nombre} (Mat: {self.matricula})"
