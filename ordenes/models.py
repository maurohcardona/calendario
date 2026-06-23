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
        ("ORDENES_PROGRAMADAS", "Órdenes Programadas"),
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
    fecha_programada = models.DateField(null=True, blank=True, verbose_name="Fecha programada")
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

    @property
    def informe_pdf(self) -> dict | None:
        """
        Retorna la información del informe PDF si hay uno disponible.

        Busca primero en las CoordinadosOrden de la orden (órdenes directas),
        luego en Coordinados vía el turno vinculado (turnos ambulatorios).

        Returns:
            Dict con claves 'estado', 'nombre_archivo', 'ruta', 'pk', 'tipo'
            — o None si no hay informe PDF registrado.
        """
        # Buscar en coordinaciones directas de la orden
        ultima = (
            self.coordinaciones
            .filter(estado_informe__in=["PENDIENTE", "CON_RESULTADOS", "FINALIZADO"])
            .order_by("-fecha_coordinacion")
            .first()
        )
        if ultima:
            return {
                "estado": ultima.estado_informe,
                "nombre_archivo": ultima.nombre_archivo_pdf,
                "ruta": ultima.ruta_archivo_pdf,
                "pk": ultima.pk,
                "tipo": "orden",
            }

        # Fallback: buscar en Coordinados del turno vinculado
        if self.turno_id:
            from turnos.models import Coordinados
            coord = (
                Coordinados.objects
                .filter(
                    id_turno=self.turno_id,
                    estado_informe__in=["PENDIENTE", "CON_RESULTADOS", "FINALIZADO"],
                )
                .first()
            )
            if coord:
                return {
                    "estado": coord.estado_informe,
                    "nombre_archivo": coord.nombre_archivo_pdf,
                    "ruta": coord.ruta_archivo_pdf,
                    "pk": coord.pk,
                    "tipo": "turno",
                }

        return None

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


class CoordinadosOrden(models.Model):
    """
    Registro de coordinación de órdenes de laboratorio vía HL7/ASTM.

    Análogo al modelo Coordinados de turnos, pero para OrdenLaboratorio.
    A diferencia de Coordinados, no valida duplicados: una orden puede
    registrar múltiples coordinaciones (reintentos, re-ingresos).
    """

    orden = models.ForeignKey(
        OrdenLaboratorio,
        on_delete=models.CASCADE,
        related_name="coordinaciones",
        verbose_name="Orden de laboratorio",
    )
    fecha_coordinacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de coordinación",
    )
    usuario = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Usuario coordinador",
    )
    determinaciones = models.TextField(
        blank=True,
        verbose_name="Determinaciones (CSV)",
        help_text="Códigos de determinaciones enviadas separados por coma",
    )
    mensaje_tipo = models.CharField(
        max_length=10,
        choices=[("ASTM", "ASTM (legacy)"), ("HL7", "HL7 v2.5")],
        default="HL7",
        verbose_name="Tipo de mensaje",
        help_text="HL7 o ASTM según el protocolo utilizado",
    )
    mensaje_hl7 = models.TextField(
        blank=True,
        verbose_name="Mensaje HL7 enviado",
    )
    ack_recibido = models.TextField(
        blank=True,
        verbose_name="ACK recibido del LIS",
    )
    ack_estado = models.CharField(
        max_length=10,
        blank=True,
        choices=[
            ("AA", "Aceptado"),
            ("AE", "Error"),
            ("AR", "Rechazado"),
        ],
        verbose_name="Estado del ACK",
        help_text="AA=aceptado, AE=error, AR=rechazado",
    )

    # ── Campos para monitoreo de PDF ──────────────────────────────────────────
    numero_protocolo_lis = models.CharField(
        max_length=100,
        blank=True,
        default="",
        db_index=True,
        verbose_name="Número de protocolo LIS",
        help_text="Filler Order Number asignado por el LIS (Navify) en el ORU^R01",
    )
    nombre_archivo_pdf = models.CharField(
        max_length=255,
        blank=True,
        default="",
        db_index=True,
        verbose_name="Nombre del archivo PDF",
        help_text="Nombre del archivo PDF generado por Navify",
    )
    estado_informe = models.CharField(
        max_length=20,
        choices=[
            ("PENDIENTE", "Pendiente"),
            ("CON_RESULTADOS", "Con Resultados"),
            ("FINALIZADO", "Finalizado"),
        ],
        blank=True,
        default="",
        db_index=True,
        verbose_name="Estado del Informe PDF",
        help_text="Estado del informe PDF generado por Navify",
    )
    ruta_archivo_pdf = models.CharField(
        max_length=512,
        blank=True,
        default="",
        verbose_name="Ruta del archivo PDF",
        help_text="Ruta relativa del archivo para ser servido desde la UI",
    )

    class Meta:
        verbose_name = "Coordinación de orden"
        verbose_name_plural = "Coordinaciones de órdenes"
        ordering = ["-fecha_coordinacion"]
        indexes = [
            models.Index(fields=["orden"]),
            models.Index(fields=["-fecha_coordinacion"]),
            models.Index(fields=["mensaje_tipo"]),
            models.Index(fields=["nombre_archivo_pdf"]),
        ]

    def __str__(self) -> str:
        return (
            f"Orden {self.orden.numero_orden_lab} — "
            f"{self.fecha_coordinacion.strftime('%Y-%m-%d %H:%M')}"
        )
