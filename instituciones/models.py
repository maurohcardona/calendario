from django.db import models


class Institucion(models.Model):
    """Modelo que representa una institucion de origen de ordenes medicas.

    Ejemplos: Hospital Balestrini, Hospital Paroissien, Hospital Germani.
    """

    nombre = models.CharField(
        max_length=200,
        unique=True,
        verbose_name="Nombre",
        help_text="Nombre de la institucion de origen",
    )
    activa = models.BooleanField(
        default=True,
        verbose_name="Activa",
        help_text="Desmarcar para desactivar sin eliminar",
    )

    class Meta:
        verbose_name = "Institucion"
        verbose_name_plural = "Instituciones"
        ordering = ["nombre"]

    def __str__(self) -> str:
        return self.nombre
