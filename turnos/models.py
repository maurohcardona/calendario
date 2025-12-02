from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone

class Cupo(models.Model):
    fecha = models.DateField(unique=True)
    cantidad_total = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.fecha} - {self.cantidad_total}"

    def disponibles(self):
        usados = Turno.objects.filter(fecha=self.fecha).count()
        return max(self.cantidad_total - usados, 0)

class Turno(models.Model):
    dni = models.CharField(max_length=20)
    nombre = models.CharField(max_length=200)
    determinaciones = models.TextField(blank=True)
    fecha = models.DateField()
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['fecha', 'creado']

    def clean(self):
        # validación: no permitir más turnos que cupos
        try:
            cupo = Cupo.objects.get(fecha=self.fecha)
        except Cupo.DoesNotExist:
            raise ValidationError("No hay cupo configurado para esa fecha.")
        usados = Turno.objects.filter(fecha=self.fecha)
        if self.pk:
            usados = usados.exclude(pk=self.pk)
        if usados.count() >= cupo.cantidad_total:
            raise ValidationError("La fecha está completa.")

class CapacidadDia(models.Model):
    fecha = models.DateField(unique=True)
    capacidad = models.PositiveIntegerField(default=20)

    def __str__(self):
        return f"{self.fecha}: {self.capacidad} turnos"
# Create your models here.
