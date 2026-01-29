"""
Configuración de auditoría para los modelos de turnos.
Este archivo registra qué modelos deben ser auditados automáticamente.
"""
from auditlog.registry import auditlog
from .models import Agenda, Cupo, Turno, Coordinados

# Registrar modelos para auditoría
# Esto guardará automáticamente:
# - Quién hizo el cambio (usuario)
# - Qué cambió (campos modificados)
# - Cuándo se hizo (timestamp)
# - Tipo de acción (CREATE, UPDATE, DELETE)

auditlog.register(Agenda)
auditlog.register(Cupo)
auditlog.register(Turno)
# auditlog.register(CapacidadDia)
# auditlog.register(WeeklyAvailability)
# auditlog.register(TurnoMensual)
auditlog.register(Coordinados)
