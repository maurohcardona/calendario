from django.db import models


class Medico(models.Model):
    """Representa un médico en el sistema."""
    nombre = models.CharField(max_length=200)
    matricula = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name = 'Médico'
        verbose_name_plural = 'Médicos'
        ordering = ['nombre']

    def __str__(self):
        return f"{self.nombre} ({self.matricula})"