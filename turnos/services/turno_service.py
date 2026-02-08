"""
Servicio para lógica de negocio relacionada con turnos.
"""
from datetime import date, datetime
from typing import Dict, Any, Optional, Tuple
from django.db import transaction
from django.core.exceptions import ValidationError
from turnos.models import Turno, Cupo, Agenda, Feriados
from pacientes.models import Paciente
from medicos.models import Medico


class TurnoService:
    """Servicio para operaciones con turnos."""
    
    @staticmethod
    def validar_disponibilidad(fecha: date, agenda: Agenda) -> Tuple[bool, str, int]:
        """
        Valida si hay disponibilidad para crear un turno.
        
        Args:
            fecha: Fecha del turno
            agenda: Agenda seleccionada
            
        Returns:
            Tupla (es_valido, mensaje_error, disponibles)
        """
        # Verificar feriado
        if Feriados.objects.filter(fecha=fecha).exists():
            feriado = Feriados.objects.get(fecha=fecha)
            return False, f"No se pueden asignar turnos en feriados: {feriado.descripcion}", 0
        
        # Obtener capacidad
        try:
            cupo = Cupo.objects.get(fecha=fecha, agenda=agenda)
            capacidad = cupo.cantidad_total
        except Cupo.DoesNotExist:
            capacidad = agenda.get_capacity_for_date(fecha)
        
        # Contar turnos usados
        usados = Turno.objects.filter(fecha=fecha, agenda=agenda).count()
        disponibles = max(capacidad - usados, 0)
        
        if capacidad <= 0:
            return False, "No hay disponibilidad para esta fecha y agenda.", 0
        
        if usados >= capacidad:
            return False, "La fecha está completa para esta agenda.", 0
        
        return True, "", disponibles
    
    @staticmethod
    def crear_turno(
        fecha: date,
        agenda: Agenda,
        dni: str,
        nombre: str,
        apellido: str,
        fecha_nacimiento: date,
        sexo: str,
        telefono: str = '',
        email: str = '',
        observaciones_paciente: str = '',
        medico_nombre: str = '',
        nota_interna: str = '',
        determinaciones: str = '',
        usuario: Any = None
    ) -> Tuple[bool, Optional[Turno], str]:
        """
        Crea un nuevo turno con validaciones.
        
        Returns:
            Tupla (exito, turno, mensaje_error)
        """
        try:
            with transaction.atomic():
                # Validar disponibilidad con lock
                es_valido, mensaje, _ = TurnoService.validar_disponibilidad(fecha, agenda)
                if not es_valido:
                    return False, None, mensaje
                
                # Obtener o crear paciente
                paciente_obj, _ = Paciente.objects.update_or_create(
                    iden=dni,
                    defaults={
                        'nombre': nombre,
                        'apellido': apellido,
                        'fecha_nacimiento': fecha_nacimiento,
                        'sexo': sexo,
                        'telefono': telefono or None,
                        'email': email or None,
                        'observaciones': observaciones_paciente or ''
                    }
                )
                
                # Obtener médico si se especificó
                medico_obj = None
                if medico_nombre:
                    try:
                        medico_obj = Medico.objects.get(nombre=medico_nombre)
                    except Medico.DoesNotExist:
                        medicos = Medico.objects.filter(nombre__icontains=medico_nombre)
                        if medicos.exists():
                            medico_obj = medicos.first()
                
                # Crear turno
                turno = Turno.objects.create(
                    fecha=fecha,
                    agenda=agenda,
                    dni=paciente_obj,
                    medico=medico_obj,
                    nota_interna=nota_interna,
                    determinaciones=determinaciones,
                    usuario=usuario
                )
                
                return True, turno, ""
                
        except Exception as e:
            return False, None, f"Error al crear turno: {str(e)}"
    
    @staticmethod
    def actualizar_turno(
        turno: Turno,
        agenda_id: int = None,
        fecha: date = None,
        determinaciones: str = None,
        medico_nombre: str = None,
        nota_interna: str = None,
        telefono: str = None,
        email: str = None,
        observaciones_paciente: str = None
    ) -> Tuple[bool, str]:
        """
        Actualiza un turno existente.
        
        Returns:
            Tupla (exito, mensaje_error)
        """
        try:
            # Actualizar turno
            if agenda_id is not None:
                turno.agenda_id = agenda_id
            if fecha is not None:
                turno.fecha = fecha
            if determinaciones is not None:
                turno.determinaciones = determinaciones
            if nota_interna is not None:
                turno.nota_interna = nota_interna
            
            # Actualizar médico
            if medico_nombre is not None:
                if medico_nombre:
                    try:
                        turno.medico = Medico.objects.get(nombre=medico_nombre)
                    except Medico.DoesNotExist:
                        medicos = Medico.objects.filter(nombre__icontains=medico_nombre)
                        if medicos.exists():
                            turno.medico = medicos.first()
                        else:
                            turno.medico = None
                else:
                    turno.medico = None
            
            turno.save()
            
            # Actualizar paciente si hay datos
            if turno.dni and any([telefono, email, observaciones_paciente]):
                if telefono is not None:
                    turno.dni.telefono = telefono or turno.dni.telefono
                if email is not None:
                    turno.dni.email = email or turno.dni.email
                if observaciones_paciente is not None:
                    turno.dni.observaciones = observaciones_paciente or turno.dni.observaciones
                turno.dni.save()
            
            return True, ""
            
        except Exception as e:
            return False, f"Error al actualizar turno: {str(e)}"
    
    @staticmethod
    def obtener_datos_paciente(turno: Turno) -> Optional[Dict[str, Any]]:
        """
        Obtiene datos formateados del paciente de un turno.
        
        Returns:
            Diccionario con datos del paciente o None
        """
        if not turno.dni:
            return None
        
        return {
            'nombre': turno.dni.nombre,
            'apellido': turno.dni.apellido,
            'dni': turno.dni.iden,
            'fecha_nacimiento': turno.dni.fecha_nacimiento,
            'sexo': turno.dni.sexo,
            'telefono': turno.dni.telefono,
            'email': turno.dni.email,
            'observaciones': turno.dni.observaciones or ''
        }
    
    @staticmethod
    def calcular_disponibilidad_fecha(fecha: date, agenda: Agenda) -> Dict[str, int]:
        """
        Calcula la disponibilidad para una fecha y agenda.
        
        Returns:
            Diccionario con capacidad, usados y disponibles
        """
        # Obtener capacidad
        try:
            cupo = Cupo.objects.get(fecha=fecha, agenda=agenda)
            capacidad = cupo.cantidad_total
        except Cupo.DoesNotExist:
            capacidad = agenda.get_capacity_for_date(fecha)
        
        # Contar usados
        usados = Turno.objects.filter(fecha=fecha, agenda=agenda).count()
        disponibles = max(capacidad - usados, 0)
        
        return {
            'capacidad': capacidad,
            'usados': usados,
            'disponibles': disponibles
        }
