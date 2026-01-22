from django.db import models
from django.contrib.postgres.fields import ArrayField



# ======================
# DETERMINACIONES
# ======================
class Determinacion(models.Model):


    codigo = models.CharField(max_length=4, unique=True)
    nombre = models.CharField(max_length=50)
    tiempo = models.IntegerField(default=3)  # Tiempo en dias
    visible = models.BooleanField(default=True)
    activa = models.BooleanField(default=True)
    



class PerfilDeterminacion(models.Model):
    codigo = models.CharField(
        max_length=4,
        unique=True
    )

    determinaciones = ArrayField(
        models.CharField(max_length=4),
        default=list,
        help_text="Códigos de determinaciones incluidas en el perfil"
    )

    def __str__(self):
        return self.codigo