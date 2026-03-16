from django.db import models
from django.contrib.postgres.fields import ArrayField


class Determinacion(models.Model):
    """Modelo que representa una determinación o análisis de laboratorio."""

    codigo = models.CharField(
        max_length=4,
        unique=True,
        verbose_name="Código",
        help_text="Código único de la determinación",
    )
    nombre = models.CharField(
        max_length=50,
        verbose_name="Nombre",
        help_text="Nombre descriptivo de la determinación",
    )
    tiempo = models.PositiveIntegerField(
        default=3,
        verbose_name="Tiempo de Entrega",
        help_text="Tiempo de entrega en días",
    )
    visible = models.BooleanField(
        default=True,
        verbose_name="Visible",
        help_text="Determina si la determinación es visible en el sistema",
    )
    activa = models.BooleanField(
        default=True,
        verbose_name="Activa",
        help_text="Determina si la determinación está activa",
    )
    stock = models.BooleanField(
        default=True,
        verbose_name="Stock Disponible",
        help_text="Indica si hay stock disponible para esta determinación",
    )

    class Meta:
        verbose_name = "Determinación"
        verbose_name_plural = "Determinaciones"
        ordering = ["codigo"]
        indexes = [
            models.Index(fields=["codigo"]),
            models.Index(fields=["activa", "visible"]),
        ]

    def __str__(self) -> str:
        return f"{self.codigo} - {self.nombre}"


class PerfilDeterminacion(models.Model):
    """Modelo que representa un perfil con múltiples determinaciones agrupadas."""

    codigo = models.CharField(
        max_length=4,
        unique=True,
        verbose_name="Código",
        help_text="Código único del perfil",
    )
    nombre = models.CharField(
        max_length=50,
        verbose_name="Nombre",
        help_text="Nombre descriptivo del perfil de determinación",
        default="Perfil de determinación",
    )
    determinaciones = ArrayField(
        models.CharField(max_length=4),
        default=list,
        verbose_name="Determinaciones",
        help_text="Códigos de determinaciones incluidas en el perfil",
    )

    class Meta:
        verbose_name = "Perfil de Determinación"
        verbose_name_plural = "Perfiles de Determinación"
        ordering = ["codigo"]

    def __str__(self) -> str:
        return f"{self.codigo} - {self.nombre}"


class DeterminacionCompleja(models.Model):
    """Modelo que representa una determinación compleja con múltiples análisis."""

    codigo = models.CharField(
        max_length=4,
        unique=True,
        verbose_name="Código",
        help_text="Código único de la determinación compleja",
    )
    tiempo = models.PositiveIntegerField(
        default=3,
        verbose_name="Tiempo de Entrega",
        help_text="Tiempo de entrega en días",
    )
    nombre = models.CharField(
        max_length=50,
        verbose_name="Nombre",
        help_text="Nombre descriptivo de la determinación compleja",
        default="Determinación Compleja",
    )
    determinaciones = ArrayField(
        models.CharField(max_length=4),
        default=list,
        verbose_name="Determinaciones",
        help_text="Códigos de determinaciones complejas incluidas",
    )
    visible = models.BooleanField(
        default=True,
        verbose_name="Visible",
        help_text="Determina si la determinación es visible en el sistema",
    )
    activa = models.BooleanField(
        default=True,
        verbose_name="Activa",
        help_text="Determina si la determinación está activa",
    )
    stock = models.BooleanField(
        default=True,
        verbose_name="Stock Disponible",
        help_text="Indica si hay stock disponible para esta determinación",
    )

    class Meta:
        verbose_name = "Determinación Compleja"
        verbose_name_plural = "Determinaciones Complejas"
        ordering = ["codigo"]
        indexes = [
            models.Index(fields=["codigo"]),
            models.Index(fields=["activa", "visible"]),
        ]

    def __str__(self) -> str:
        return f"{self.codigo} - {self.nombre}"
