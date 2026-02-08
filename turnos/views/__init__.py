"""
Módulo de vistas de la aplicación turnos.
Agrupa todas las vistas organizadas por funcionalidad.
"""

# Vistas de calendario y cupos
from .calendar_views import (
    calendario,
    nuevo_cupo,
    generar_cupos_masivo,
    borrar_cupos_masivo,
    lighten_color,
)

# Vistas de turnos (CRUD)
from .turno_views import (
    dia,
    buscar,
    editar_turno,
    eliminar_turno,
)

# Vistas de coordinación
from .coordinacion_views import (
    precoordinacion_turno,
    ver_coordinacion,
    coordinar_turno,
    generar_ticket_turno,
    generar_ticket_retiro,
    control_ordenes,
)

# Vistas API
from .api_views import (
    eventos_calendario,
    turnos_historicos_api,
    listar_medicos_api,
)

# Vistas administrativas
from .admin_views import (
    administrar_tablas,
    administrar_tabla_detalle,
    crear_registro,
    editar_registro,
    eliminar_registro,
    aplicar_feriados,
    audit_log,
    crear_medico_api,
)

# Vista de logout
from .auth_views import logout_view

__all__ = [
    # Calendario y cupos
    'calendario',
    'nuevo_cupo',
    'generar_cupos_masivo',
    'borrar_cupos_masivo',
    'lighten_color',
    
    # Turnos
    'dia',
    'buscar',
    'editar_turno',
    'eliminar_turno',
    
    # Coordinación
    'precoordinacion_turno',
    'ver_coordinacion',
    'coordinar_turno',
    'generar_ticket_turno',
    'generar_ticket_retiro',
    'control_ordenes',
    
    # API
    'eventos_calendario',
    'turnos_historicos_api',
    'listar_medicos_api',
    
    # Admin
    'administrar_tablas',
    'administrar_tabla_detalle',
    'crear_registro',
    'editar_registro',
    'eliminar_registro',
    'aplicar_feriados',
    'audit_log',
    'crear_medico_api',
    
    # Auth
    'logout_view',
]
