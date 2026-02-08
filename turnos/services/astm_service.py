"""
Servicio para generación de archivos ASTM de coordinación.
"""
import os
from datetime import datetime
from typing import Optional
from django.conf import settings
from django.contrib.auth.models import User
from turnos.models import Turno, Coordinados
from pacientes.models import Paciente
from .determinacion_service import DeterminacionService


class ASTMService:
    """Servicio para generar archivos ASTM de coordinación."""
    
    @staticmethod
    def generar_archivo_astm(turno: Turno, nombre_impresora: str, usuario: str) -> tuple[bool, str, str]:
        """
        Genera un archivo ASTM para coordinación de turno.
        
        Args:
            turno: Instancia del turno a coordinar
            nombre_impresora: Nombre de la impresora de destino
            usuario: Usuario que genera el archivo
            
        Returns:
            Tupla (exito, ruta_archivo, mensaje_error)
        """
        try:
            # Verificar si ya fue coordinado
            if Coordinados.objects.filter(id_turno=turno.id).exists():
                return False, "", "Este turno ya fue coordinado anteriormente"
            
            # Obtener datos del paciente
            paciente_obj = turno.dni
            if not paciente_obj:
                return False, "", "Paciente no encontrado"
            
            # Preparar datos del paciente
            nombre = paciente_obj.nombre
            apellido = paciente_obj.apellido
            dni = paciente_obj.iden
            fecha_nacimiento = paciente_obj.fecha_nacimiento
            sexo = paciente_obj.sexo
            telefono = paciente_obj.telefono or ''
            email = paciente_obj.email or ''
            
            # Convertir sexo al formato ASTM (M/F/U)
            sexo_astm = 'M' if sexo == 'Masculino' else ('F' if sexo == 'Femenino' else 'U')
            
            # Formatear fechas
            ahora = datetime.now()
            timestamp = ahora.strftime('%Y%m%d%H%M%S')
            fecha_nac = fecha_nacimiento.strftime('%Y%m%d')
            
            # Obtener determinaciones en formato ASTM
            determinaciones_astm = DeterminacionService.expandir_determinaciones_para_astm(
                turno.determinaciones or ''
            )
            determinaciones_concatenadas = ''.join(determinaciones_astm)
            
            # Datos adicionales
            nota_interna = turno.nota_interna or ''
            observaciones_paciente = paciente_obj.observaciones or ''
            nombre_medico = turno.medico.nombre if turno.medico else ''
            matricula_medico = turno.medico.matricula if turno.medico else ''
            
            # Construir líneas ASTM
            lineas = []
            lineas.append(f'H|\\^&|||Balestrini|||||||P||{timestamp}')
            lineas.append(
                f'P|1||{dni}||{apellido}^{nombre}^||{fecha_nac}|{sexo_astm}|{email}|'
                f'{telefono}|{nota_interna}|{observaciones_paciente}|||||| |||||{timestamp}||||||||||'
            )
            lineas.append(
                f'O|1|{turno.id}||{determinaciones_concatenadas}|||{nombre_impresora}|'
                f'{nombre_medico}|{matricula_medico}|{usuario}|A||||||||||||||O'
            )
            lineas.append('L|1|F')
            
            # Guardar archivo
            nombre_archivo = f"mensaje_{turno.id}_{ahora.strftime('%Y%m%d_%H%M%S')}.pet"
            ruta_mensajes = os.path.join(settings.BASE_DIR, 'mensajes')
            
            # Asegurar que existe el directorio
            os.makedirs(ruta_mensajes, exist_ok=True)
            
            ruta_completa = os.path.join(ruta_mensajes, nombre_archivo)
            
            # Escribir archivo
            with open(ruta_completa, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lineas))
            
            # Obtener instancia de User
            usuario_obj = None
            if usuario:
                try:
                    usuario_obj = User.objects.get(username=usuario)
                except User.DoesNotExist:
                    pass
            
            # Registrar en Coordinados
            Coordinados.objects.create(
                id_turno=turno.id,
                fecha_coordinacion=datetime.now(),
                usuario=usuario_obj,
                dni=paciente_obj,
                determinaciones=turno.determinaciones or ''
            )
            
            return True, ruta_completa, ""
            
        except Exception as e:
            return False, "", f"Error al generar archivo ASTM: {str(e)}"
    
    @staticmethod
    def verificar_coordinado(turno_id: int) -> bool:
        """
        Verifica si un turno está coordinado.
        
        Args:
            turno_id: ID del turno
            
        Returns:
            True si está coordinado, False en caso contrario
        """
        return Coordinados.objects.filter(id_turno=turno_id).exists()
