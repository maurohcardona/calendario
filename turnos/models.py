from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from medicos.models import Medico


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
    dni = models.CharField(max_length=20)
    apellido = models.CharField(max_length=200, default='')
    nombre = models.CharField(max_length=200)
    determinaciones = models.TextField(blank=True)
    fecha = models.DateField()
    medico = models.ForeignKey(Medico, on_delete=models.SET_NULL, null=True, blank=True, related_name='turnos')
    nota_interna = models.TextField(blank=True, default='')
    usuario = models.CharField(max_length=150, blank=True, default='')
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['fecha', 'creado']

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


# class CapacidadDia(models.Model):
#     """(Opcional) capacidad por día y agenda si se usa aparte de Cupo."""
#     agenda = models.ForeignKey(Agenda, on_delete=models.CASCADE, related_name='capacidades')
#     fecha = models.DateField()
#     capacidad = models.PositiveIntegerField(default=20)
#     usuario = models.CharField(max_length=150, blank=True, default='')

#     class Meta:
#         unique_together = (('agenda', 'fecha'),)

#     def __str__(self):
#         return f"{self.agenda.name} - {self.fecha}: {self.capacidad} turnos"


# class WeeklyAvailability(models.Model):
#     """Define la capacidad recurrente por día de la semana para una agenda.
#     weekday: 0=Lunes .. 4=Viernes (coincide con date.weekday()).
#     active: si False, significa que ese día no se trabaja.
#     desde_fecha y hasta_fecha: rango opcional para aplicar esta disponibilidad."""
#     WEEKDAY_CHOICES = (
#         (0, 'Lunes'),
#         (1, 'Martes'),
#         (2, 'Miércoles'),
#         (3, 'Jueves'),
#         (4, 'Viernes'),
#     )

#     agenda = models.ForeignKey(Agenda, on_delete=models.CASCADE, related_name='weekly_availability')
#     weekday = models.IntegerField(choices=WEEKDAY_CHOICES)
#     capacidad = models.PositiveIntegerField(default=0)
#     active = models.BooleanField(default=True)
#     desde_fecha = models.DateField(null=True, blank=True, help_text="Fecha desde la cual aplicar esta disponibilidad (opcional)")
#     hasta_fecha = models.DateField(null=True, blank=True, help_text="Fecha hasta la cual aplicar esta disponibilidad (opcional)")
#     usuario = models.CharField(max_length=150, blank=True, default='')

#     class Meta:
#         unique_together = (('agenda', 'weekday'),)

#     def __str__(self):
#         rango = ""
#         if self.desde_fecha or self.hasta_fecha:
#             rango = f" ({self.desde_fecha or 'inicio'} a {self.hasta_fecha or 'fin'})"
#         return f"{self.agenda.name} - {self.get_weekday_display()}: {self.capacidad} ({'activo' if self.active else 'inactivo'}){rango}"


# class TurnoMensual(models.Model):
#     """Define cupos mensuales: aplicar una cantidad específica de cupos 
#     de lunes a viernes en un rango de fechas determinado."""
#     agenda = models.ForeignKey(Agenda, on_delete=models.CASCADE, related_name='turnos_mensuales')
#     desde_fecha = models.DateField(help_text="Fecha de inicio del rango")
#     hasta_fecha = models.DateField(help_text="Fecha de fin del rango")
#     cantidad = models.PositiveIntegerField(default=5, help_text="Cantidad de cupos para cada día de lunes a viernes")
#     aplicado = models.BooleanField(default=False, help_text="Si está aplicado, los cupos ya fueron creados")
#     usuario = models.CharField(max_length=150, blank=True, default='')
#     creado = models.DateTimeField(auto_now_add=True)

#     class Meta:
#         verbose_name = "Turno Mensual"
#         verbose_name_plural = "Turnos Mensuales"
#         ordering = ['-creado']

#     def __str__(self):
#         estado = "✅ Aplicado" if self.aplicado else "⏳ Pendiente"
#         return f"{self.agenda.name} - {self.desde_fecha} a {self.hasta_fecha} ({self.cantidad} cupos) {estado}"

#     def aplicar(self):
#         """Crear cupos para todas las fechas en el rango (solo lunes a viernes)."""
#         from datetime import timedelta
        
#         cur = self.desde_fecha
#         count = 0
#         while cur <= self.hasta_fecha:
#             if cur.weekday() < 5:  # Lunes a viernes
#                 Cupo.objects.get_or_create(
#                     agenda=self.agenda,
#                     fecha=cur,
#                     defaults={'cantidad_total': self.cantidad}
#                 )
#                 count += 1
#             cur += timedelta(days=1)
        
#         self.aplicado = True
#         self.save()
#         return count


# def agenda_get_capacity_for_date(agenda, fecha):
#     """Helper: devuelve la capacidad para una agenda en una fecha concreta.
#     Prioriza un Cupo explícito (objeto Cupo) si existe; si no existe, consulta WeeklyAvailability; si nada, devuelve 0.
#     Respeta los rangos desde_fecha y hasta_fecha de WeeklyAvailability."""
#     try:
#         cupo = Cupo.objects.get(agenda=agenda, fecha=fecha)
#         return cupo.cantidad_total
#     except Cupo.DoesNotExist:
#         # buscar disponibilidad semanal
#         try:
#             wa = WeeklyAvailability.objects.get(agenda=agenda, weekday=fecha.weekday())
#             if not wa.active:
#                 return 0
#             # Verificar si la fecha está dentro del rango
#             if wa.desde_fecha and fecha < wa.desde_fecha:
#                 return 0
#             if wa.hasta_fecha and fecha > wa.hasta_fecha:
#                 return 0
#             return wa.capacidad
#         except WeeklyAvailability.DoesNotExist:
#             return 0


# # Attach method to Agenda dynamically for convenience
# def _agenda_get_capacity(self, fecha):
#     return agenda_get_capacity_for_date(self, fecha)

# Agenda.get_capacity_for_date = _agenda_get_capacity


class Coordinados(models.Model):
    """Registro de turnos coordinados (enviados al equipo)"""
    id_turno = models.IntegerField(unique=True, verbose_name='ID del Turno')
    nombre = models.CharField(max_length=200, verbose_name='Nombre')
    apellido = models.CharField(max_length=200, verbose_name='Apellido')
    dni = models.CharField(max_length=20, verbose_name='DNI')
    fecha_coordinacion = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Coordinación')
    determinaciones = models.TextField(blank=True, verbose_name='Determinaciones')
    usuario = models.CharField(max_length=150, blank=True, default='')

    class Meta:
        verbose_name = 'Turno Coordinado'
        verbose_name_plural = 'Turnos Coordinados'
        ordering = ['-fecha_coordinacion']

    def __str__(self):
        return f"Turno #{self.id_turno} - {self.apellido}, {self.nombre} - {self.fecha_coordinacion.strftime('%Y-%m-%d %H:%M')}"

