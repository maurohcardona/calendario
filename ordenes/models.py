from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from determinaciones.models import Determinacion, DeterminacionCompleja
from pacientes.models import Paciente


class Servicio(models.Model):
    ORIGEN_CHOICES = [
        ("AMBULATORIO", "Ambulatorio"),
        ("GUARDIA", "Guardia"),
        ("INTERNACION", "Internación"),
    ]
    origen = models.CharField(max_length=20, choices=ORIGEN_CHOICES)
    nombre = models.CharField(max_length=100)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Servicio"
        verbose_name_plural = "Servicios"
        ordering = ["origen", "nombre"]

    def __str__(self):
        return f"{self.get_origen_display()} — {self.nombre}"


class OrdenLaboratorio(models.Model):
    TIPO_ORIGEN_CHOICES = [
        ("AMBULATORIO", "Ambulatorio"),
        ("GUARDIA", "Guardia"),
        ("INTERNACION", "Internación"),
    ]
    ESTADO_CHOICES = [
        ("PENDIENTE", "Pendiente"),
        ("TURNO", "Turno Asignado"),
        ("INGRESADA", "Ingresada"),
        ("COMPLETADA", "Completada"),
        ("CANCELADA", "Cancelada"),
    ]

    paciente = models.ForeignKey(Paciente, on_delete=models.PROTECT, related_name="ordenes")
    medico = models.ForeignKey("medicos.Medico", on_delete=models.PROTECT, related_name="ordenes")
    tipo_origen = models.CharField(max_length=20, choices=TIPO_ORIGEN_CHOICES)
    servicio = models.ForeignKey(Servicio, on_delete=models.SET_NULL, null=True, blank=True)
    sala = models.CharField(max_length=50, blank=True, default="")
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default="PENDIENTE")
    observaciones = models.TextField(blank=True, default="")
    urgente = models.BooleanField(default=False)
    determinaciones = models.ManyToManyField(Determinacion, blank=True, related_name="ordenes")
    determinaciones_complejas = models.ManyToManyField(DeterminacionCompleja, blank=True, related_name="ordenes")
    turno = models.ForeignKey("turnos.Turno", on_delete=models.SET_NULL, null=True, blank=True, related_name="orden")
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="ordenes_creadas")
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    numero_orden_lab = models.CharField(max_length=50, blank=True, default="")
    observaciones_lab = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Orden de Laboratorio"
        verbose_name_plural = "Órdenes de Laboratorio"
        ordering = ["-fecha_creacion"]

    def __str__(self):
        return f"Orden #{self.pk} — {self.paciente} ({self.get_estado_display()})"

    @property
    def puede_ingresar(self):
        return self.estado in ("PENDIENTE", "TURNO")

    @property
    def puede_completar(self):
        return self.estado == "INGRESADA"

    @property
    def puede_cancelar(self):
        return self.estado in ("PENDIENTE", "TURNO", "INGRESADA")

    @property
    def puede_vincular_turno(self):
        return self.estado in ("PENDIENTE", "INGRESADA")

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Generar numero_orden_lab la primera vez (único, basado en pk)
        if not self.numero_orden_lab:
            self.numero_orden_lab = f"LAB-{self.pk:06d}"
            super().save(update_fields=["numero_orden_lab"])

    def ingresar(self, observaciones_lab=""):
        self.estado = "INGRESADA"
        self.observaciones_lab = observaciones_lab
        self.save()

    def completar(self):
        self.estado = "COMPLETADA"
        self.save()

    def cancelar(self, motivo=""):
        self.estado = "CANCELADA"
        if motivo:
            self.observaciones_lab = motivo
        self.save()
