from django.db import models
from pacientes.models import Paciente
from turnos.models import Turno


class Informes(models.Model):
    """Modelo que representa informes médicos enviados por email y WhatsApp.

    Gestiona el control de envío de informes médicos a los pacientes,
    incluyendo seguimiento de intentos, errores y estado del envío.
    """

    # Opciones para el estado del informe
    ESTADO_CHOICES = [
        ("PENDIENTE", "Pendiente de envío"),
        ("ENVIADO", "Enviado"),
        ("ERROR", "Error en el envío"),
    ]

    # Relaciones
    id_turno = models.ForeignKey(
        Turno,
        on_delete=models.PROTECT,
        verbose_name="Turno",
        null=True,
        blank=True,
        help_text="Turno asociado al informe",
    )
    paciente = models.ForeignKey(
        Paciente,
        on_delete=models.PROTECT,
        verbose_name="Paciente",
        related_name="informes",
    )

    # Datos del archivo (formato: [Origen]_[DNI]_[N Peticion]_[Turno].pdf)
    # numero_orden → N Peticion, numero_protocolo → Turno
    numero_orden = models.IntegerField(
        verbose_name="Número de Orden", help_text="Número de petición del informe"
    )
    numero_protocolo = models.CharField(
        max_length=50,
        verbose_name="Número de Protocolo",
        help_text="Número de protocolo o turno",
    )
    nombre_archivo = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="Nombre del Archivo",
        help_text="Nombre del archivo PDF generado",
    )

    # Control de envío por email
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default="PENDIENTE",
        verbose_name="Estado del Informe",
        db_index=True,
    )
    fecha_creacion = models.DateTimeField(
        auto_now_add=True, verbose_name="Fecha de Creación"
    )
    fecha_envio = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha de Envío",
        help_text="Fecha y hora en que se envió el informe",
    )
    email_destino = models.EmailField(
        max_length=254,
        blank=True,
        default="",
        verbose_name="Email de Destino",
        help_text="Dirección de correo del paciente",
    )
    intentos_envio = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="Intentos de Envío",
        help_text="Número de veces que se intentó enviar el informe",
    )
    mensaje_error = models.TextField(
        blank=True,
        default="",
        verbose_name="Mensaje de Error",
        help_text="Detalle del error en caso de fallo",
    )

    # Control de envío WhatsApp
    whatsapp_enviado = models.BooleanField(
        default=False,
        verbose_name="WhatsApp Enviado",
        help_text="Indica si se envió por WhatsApp exitosamente",
    )
    whatsapp_telefono = models.CharField(
        max_length=30,
        blank=True,
        default="",
        verbose_name="Teléfono WhatsApp Destino",
        help_text="Número de teléfono para WhatsApp",
    )
    whatsapp_error = models.TextField(
        blank=True,
        default="",
        verbose_name="Error WhatsApp",
        help_text="Detalle del error en envío por WhatsApp",
    )

    class Meta:
        verbose_name = "Informe"
        verbose_name_plural = "Informes"
        ordering = ["-fecha_creacion"]
        unique_together = [["paciente", "numero_orden", "numero_protocolo"]]
        indexes = [
            models.Index(fields=["-fecha_creacion"]),
            models.Index(fields=["estado"]),
            models.Index(fields=["paciente", "numero_orden"]),
        ]

    def __str__(self) -> str:
        return f"{self.paciente.iden}-{self.numero_orden}-{self.numero_protocolo} - {self.estado}"

    def generar_nombre_archivo(self) -> str:
        """Genera el nombre del archivo basado en los datos del informe."""
        return f"{self.paciente.iden}-{self.numero_orden}-{self.numero_protocolo}.pdf"
