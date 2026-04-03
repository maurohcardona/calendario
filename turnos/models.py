from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from medicos.models import Medico
from pacientes.models import Paciente
from django.contrib.auth.models import User


class Agenda(models.Model):
    """Modelo que representa una agenda/servicio médico.

    Ejemplos: Ambulatorio, Curvas de Glucosa, Emergencia, etc.
    Cada agenda tiene su propio color y slug para identificarla en el calendario.
    """

    name = models.CharField(
        max_length=100,
        verbose_name="Nombre",
        help_text="Nombre de la agenda o servicio",
    )
    slug = models.SlugField(
        max_length=100,
        unique=True,
        verbose_name="Slug",
        help_text="Identificador único para URLs (ej: ambulatorio, curvas)",
    )
    color = models.CharField(
        max_length=7,
        default="#00d4ff",
        verbose_name="Color",
        help_text="Color HEX para el calendario (ej. #00d4ff)",
    )
    usuario = models.CharField(
        max_length=150,
        blank=True,
        default="",
        verbose_name="Usuario",
        help_text="Usuario que creó o gestiona esta agenda",
    )

    class Meta:
        verbose_name = "Agenda"
        verbose_name_plural = "Agendas"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def get_capacity_for_date(self, fecha):
        """Devuelve la capacidad para esta agenda en una fecha concreta.
        Prioriza un Cupo explícito si existe; si no, devuelve 0."""
        try:
            cupo = Cupo.objects.get(agenda=self, fecha=fecha)
            return cupo.cantidad_total
        except Cupo.DoesNotExist:
            return 0


class Cupo(models.Model):
    """Modelo que representa el cupo disponible para una agenda en una fecha específica.

    La combinación (fecha, agenda) es única para evitar duplicados.
    """

    agenda = models.ForeignKey(
        Agenda, on_delete=models.CASCADE, related_name="cupos", verbose_name="Agenda"
    )
    fecha = models.DateField(verbose_name="Fecha")
    cantidad_total = models.PositiveIntegerField(
        verbose_name="Cantidad Total",
        help_text="Número total de turnos disponibles para esta fecha",
    )
    usuario = models.CharField(
        max_length=150,
        blank=True,
        default="",
        verbose_name="Usuario",
        help_text="Usuario que creó este cupo",
    )

    class Meta:
        unique_together = (("agenda", "fecha"),)
        verbose_name = "Cupo"
        verbose_name_plural = "Cupos"
        ordering = ["fecha", "agenda"]
        indexes = [
            models.Index(fields=["fecha", "agenda"]),
        ]

    def __str__(self) -> str:
        return f"{self.agenda.name} - {self.fecha} - {self.cantidad_total}"

    def disponibles(self) -> int:
        """Retorna la cantidad de cupos disponibles para esta agenda y fecha."""
        usados = Turno.objects.filter(fecha=self.fecha, agenda=self.agenda).count()
        return max(self.cantidad_total - usados, 0)


class Turno(models.Model):
    """Modelo que representa un turno médico asignado a un paciente."""

    agenda = models.ForeignKey(
        Agenda, on_delete=models.PROTECT, related_name="turnos", verbose_name="Agenda"
    )
    dni = models.ForeignKey(
        Paciente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="turnos",
        verbose_name="Paciente",
    )
    determinaciones = models.TextField(
        blank=True,
        default="",
        verbose_name="Determinaciones",
        help_text="Lista de análisis o estudios solicitados",
    )
    fecha = models.DateField(verbose_name="Fecha del Turno")
    medico = models.ForeignKey(
        Medico,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="turnos",
        verbose_name="Médico Solicitante",
    )
    nota_interna = models.TextField(
        blank=True,
        default="",
        verbose_name="Nota Interna",
        help_text="Observaciones internas del turno",
    )
    usuario = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="turnos",
        verbose_name="Usuario que Creó el Turno",
    )
    creado = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")

    class Meta:
        ordering = ["fecha", "creado"]
        verbose_name = "Turno"
        verbose_name_plural = "Turnos"
        indexes = [
            models.Index(fields=["fecha", "agenda"]),
            models.Index(fields=["dni"]),
            models.Index(fields=["creado"]),
        ]

    # Propiedades de compatibilidad para acceder a datos del paciente
    @property
    def nombre(self) -> str:
        """Retorna el nombre del paciente."""
        return self.dni.nombre if self.dni else ""

    @property
    def apellido(self) -> str:
        """Retorna el apellido del paciente."""
        return self.dni.apellido if self.dni else ""

    @property
    def paciente_dni(self) -> str:
        """Retorna el DNI del paciente."""
        return self.dni.iden if self.dni else ""

    def __str__(self) -> str:
        paciente_info = (
            f"{self.apellido}, {self.nombre}" if self.dni else "Sin paciente"
        )
        return f"Turno #{self.pk} - {paciente_info} - {self.fecha}"

    def clean(self) -> None:
        """Validaciones del modelo antes de guardar."""
        super().clean()

        # Verificar si la fecha es un feriado
        if Feriados.objects.filter(fecha=self.fecha).exists():
            feriado = Feriados.objects.get(fecha=self.fecha)
            raise ValidationError(
                f"No se pueden asignar turnos en feriados: {feriado.descripcion}"
            )

        # Validación: no permitir más turnos que la capacidad para esa agenda en esa fecha
        try:
            capacidad = self.agenda.get_capacity_for_date(self.fecha)
        except Exception as e:
            raise ValidationError(
                f"No se pudo determinar la capacidad para esa fecha y agenda: {str(e)}"
            )

        if capacidad is None or capacidad <= 0:
            raise ValidationError("No hay cupo disponible para esa fecha y agenda.")

        usados = Turno.objects.filter(fecha=self.fecha, agenda=self.agenda)
        if self.pk:
            usados = usados.exclude(pk=self.pk)

        if usados.count() >= capacidad:
            raise ValidationError(
                "La fecha está completa para esta agenda. No hay turnos disponibles."
            )


class Feriados(models.Model):
    """Modelo que representa días feriados donde no se pueden asignar turnos."""

    fecha = models.DateField(
        unique=True, verbose_name="Fecha", help_text="Fecha del feriado"
    )
    descripcion = models.CharField(
        max_length=200,
        blank=True,
        default="",
        verbose_name="Descripción",
        help_text="Descripción del feriado (ej: Día de la Independencia)",
    )
    usuario = models.CharField(
        max_length=150,
        blank=True,
        default="",
        verbose_name="Usuario",
        help_text="Usuario que registró el feriado",
    )

    class Meta:
        verbose_name = "Feriado"
        verbose_name_plural = "Feriados"
        ordering = ["-fecha"]
        indexes = [
            models.Index(fields=["fecha"]),
        ]

    def __str__(self) -> str:
        return (
            f"{self.fecha} - {self.descripcion}"
            if self.descripcion
            else str(self.fecha)
        )


class Coordinados(models.Model):
    """Modelo que registra turnos coordinados (enviados al equipo médico)."""

    id_turno = models.IntegerField(unique=True, verbose_name="ID del Turno")
    dni = models.ForeignKey(Paciente, on_delete=models.PROTECT, verbose_name="Paciente")
    fecha_coordinacion = models.DateTimeField(
        auto_now_add=True, verbose_name="Fecha de Coordinación"
    )
    determinaciones = models.TextField(
        blank=True,
        default="",
        verbose_name="Determinaciones",
        help_text="Lista de estudios coordinados",
    )
    usuario = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Usuario que Coordinó",
    )

    class Meta:
        verbose_name = "Turno Coordinado"
        verbose_name_plural = "Turnos Coordinados"
        ordering = ["-fecha_coordinacion"]
        indexes = [
            models.Index(fields=["id_turno"]),
            models.Index(fields=["-fecha_coordinacion"]),
        ]

    def __str__(self) -> str:
        if self.dni:
            return (
                f"Turno #{self.id_turno} - {self.dni.apellido}, {self.dni.nombre} - "
                f"{self.fecha_coordinacion.strftime('%Y-%m-%d %H:%M')}"
            )
        return f"Turno #{self.id_turno} - {self.fecha_coordinacion.strftime('%Y-%m-%d %H:%M')}"
