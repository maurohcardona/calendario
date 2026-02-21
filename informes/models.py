from django.db import models
from pacientes.models import Paciente
from turnos.models import Turno

# Create your models here.
class Informes(models.Model):
    """Registro de informes médicos enviados por email"""
    
    # Opciones para el estado del informe
    ESTADO_CHOICES = [
        ('PENDIENTE', 'Pendiente de envío'),
        ('ENVIADO', 'Enviado'),
        ('ERROR', 'Error en el envío'),
    ]
    
    # Relaciones
    id_turno = models.ForeignKey(Turno, on_delete=models.PROTECT, verbose_name='Turno', null=True, blank=True)
    paciente = models.ForeignKey(Paciente, on_delete=models.PROTECT, verbose_name='Paciente')
    
    # Datos del archivo (formato: DNI-ORDEN-PROTOCOLO.pdf)
    numero_orden = models.IntegerField(verbose_name='Número de Orden')
    numero_protocolo = models.CharField(max_length=50, verbose_name='Número de Protocolo')
    nombre_archivo = models.CharField(max_length=255, verbose_name='Nombre del Archivo', blank=True)
    
    # Control de envío
    estado = models.CharField(
        max_length=20, 
        choices=ESTADO_CHOICES, 
        default='PENDIENTE', 
        verbose_name='Estado del Informe'
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Creación')
    fecha_envio = models.DateTimeField(null=True, blank=True, verbose_name='Fecha de Envío')
    email_destino = models.EmailField(max_length=254, verbose_name='Email de Destino', blank=True)
    intentos_envio = models.IntegerField(default=0, verbose_name='Intentos de Envío')
    mensaje_error = models.TextField(blank=True, verbose_name='Mensaje de Error')

    class Meta:
        verbose_name = 'Informe'
        verbose_name_plural = 'Informes'
        ordering = ['-fecha_creacion']
        unique_together = [['paciente', 'numero_orden', 'numero_protocolo']]

    def __str__(self):
        return f"{self.paciente.iden}-{self.numero_orden}-{self.numero_protocolo} - {self.estado}"
    
    def generar_nombre_archivo(self):
        """Genera el nombre del archivo basado en los datos del informe"""
        return f"{self.paciente.iden}-{self.numero_orden}-{self.numero_protocolo}.pdf"

