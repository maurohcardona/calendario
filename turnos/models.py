from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from medicos.models import Medico
from pacientes.models import Paciente


class Agenda(models.Model):
    """Representa una agenda/servicio (Ambulatorio, Curvas, Emergencia...).
    Cada agenda tiene su propio color y slug para identificarla."""
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)
    color = models.CharField(max_length=7, default="#00d4ff", help_text="Color HEX para el calendario (ej. #00d4ff)")
    usuario = models.CharField(max_length=150, blank=True, default='')

    class Meta:
        verbose_name = "Agenda"
        verbose_name_plural = "Agendas"

    def __str__(self):
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
    """Cupo por fecha y por agenda. Ahora la combinación (fecha, agenda) es única."""
    agenda = models.ForeignKey(Agenda, on_delete=models.CASCADE, related_name='cupos')
    fecha = models.DateField()
    cantidad_total = models.PositiveIntegerField()
    usuario = models.CharField(max_length=150, blank=True, default='')

    class Meta:
        unique_together = (('agenda', 'fecha'),)

    def __str__(self):
        return f"{self.agenda.name} - {self.fecha} - {self.cantidad_total}"

    def disponibles(self):
        usados = Turno.objects.filter(fecha=self.fecha, agenda=self.agenda).count()
        return max(self.cantidad_total - usados, 0)


class Turno(models.Model):
    agenda = models.ForeignKey(Agenda, on_delete=models.PROTECT, related_name='turnos')
    dni = models.ForeignKey(Paciente, on_delete=models.SET_NULL, null=True, blank=True, related_name='turnos')
    determinaciones = models.TextField(blank=True)
    fecha = models.DateField()
    medico = models.ForeignKey(Medico, on_delete=models.SET_NULL, null=True, blank=True, related_name='turnos')
    nota_interna = models.TextField(blank=True, default='')
    usuario = models.CharField(max_length=150, blank=True, default='')
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['fecha', 'creado']
    
    # Propiedades de compatibilidad para acceder a datos del paciente
    @property
    def nombre(self):
        return self.dni.nombre if self.dni else ''
    
    @property
    def apellido(self):
        return self.dni.apellido if self.dni else ''
    
    @property
    def paciente_dni(self):
        return self.dni.iden if self.dni else ''

    def clean(self):
        # Verificar si la fecha es un feriado
        if Feriados.objects.filter(fecha=self.fecha).exists():
            feriado = Feriados.objects.get(fecha=self.fecha)
            raise ValidationError(f"No se pueden asignar turnos en feriados: {feriado.descripcion}")
        
        # validación: no permitir más turnos que la capacidad para esa agenda en esa fecha
        capacidad = None
        try:
            capacidad = self.agenda.get_capacity_for_date(self.fecha)
        except Exception:
            capacidad = None

        if capacidad is None:
            raise ValidationError("No se pudo determinar la capacidad para esa fecha y agenda.")

        if capacidad <= 0:
            raise ValidationError("No hay cupo disponible para esa fecha y agenda.")

        usados = Turno.objects.filter(fecha=self.fecha, agenda=self.agenda)
        if self.pk:
            usados = usados.exclude(pk=self.pk)
        if usados.count() >= capacidad:
            raise ValidationError("La fecha está completa para esta agenda.")
        

class Feriados(models.Model):
    """Días feriados donde no se pueden asignar turnos."""
    fecha = models.DateField(unique=True)
    descripcion = models.CharField(max_length=200, blank=True, default='')
    usuario = models.CharField(max_length=150, blank=True, default='')

    class Meta:
        verbose_name = "Feriado"
        verbose_name_plural = "Feriados"
        ordering = ['-fecha']

    def __str__(self):
        return f"{self.fecha} - {self.descripcion}"


class Coordinados(models.Model):
    """Registro de turnos coordinados (enviados al equipo)"""
    id_turno = models.IntegerField(unique=True, verbose_name='ID del Turno')
    dni = models.ForeignKey(Paciente, on_delete=models.PROTECT, verbose_name='Paciente')
    fecha_coordinacion = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Coordinación')
    determinaciones = models.TextField(blank=True, verbose_name='Determinaciones')
    usuario = models.CharField(max_length=150, blank=True, default='')

    class Meta:
        verbose_name = 'Turno Coordinado'
        verbose_name_plural = 'Turnos Coordinados'
        ordering = ['-fecha_coordinacion']

    def __str__(self):
        if self.dni:
            return f"Turno #{self.id_turno} - {self.dni.apellido}, {self.dni.nombre} - {self.fecha_coordinacion.strftime('%Y-%m-%d %H:%M')}"
        return f"Turno #{self.id_turno} - {self.fecha_coordinacion.strftime('%Y-%m-%d %H:%M')}"

