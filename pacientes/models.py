from django.db import models
from datetime import date

# Create your models here.


class Paciente(models.Model):
    
    SEXO_CHOICES = [
        ('Masculino', 'Masculino'),
        ('Femenino', 'Femenino'),
        ('Sin asignar', 'Sin asignar'),
    ]
    

    iden = models.CharField(max_length=15, unique=True)
    nombre = models.CharField(max_length=30)
    apellido = models.CharField(max_length=30)
    fecha_nacimiento = models.DateField()
    sexo = models.CharField(
        max_length=15,
        choices=SEXO_CHOICES,
        default="Sin asignar"
    )
    telefono = models.CharField(max_length=10, null=True, blank=True)
    email = models.EmailField(null=True,blank=True)
    observaciones = models.CharField(max_length=50, null=True, blank=True)
    
    @property
    def edad(self):
        """Calcula la edad del paciente en años"""
        today = date.today()
        return today.year - self.fecha_nacimiento.year - (
            (today.month, today.day) < (self.fecha_nacimiento.month, self.fecha_nacimiento.day)
        )
    
    def __str__(self):
        return self.apellido + " " + self.nombre

# Create your models here.
