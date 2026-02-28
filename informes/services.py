"""
Servicios para el procesamiento y envío de informes médicos por email
"""
import os
import shutil
from pathlib import Path
from django.conf import settings
from django.core.mail import EmailMessage
from django.db import transaction
from django.utils import timezone
from .models import Informes
from pacientes.models import Paciente


class InformesService:
    """Servicio para gestionar el envío de informes médicos"""

    def __init__(self):
        self.base_dir = Path(settings.BASE_DIR) / 'informes'
        self.pendientes_dir = Path(settings.INFORMES_PENDIENTES_DIR)
        self.enviados_dir = self.base_dir / 'enviados'
        self.sin_email_dir = self.base_dir / 'sin_email'
        self.otros_origenes_dir = self.base_dir / 'otros_origenes'

        # Crear directorios si no existen
        self.pendientes_dir.mkdir(parents=True, exist_ok=True)
        self.enviados_dir.mkdir(parents=True, exist_ok=True)
        self.sin_email_dir.mkdir(parents=True, exist_ok=True)
        self.otros_origenes_dir.mkdir(parents=True, exist_ok=True)

    def mover_archivo_guardia(self, archivo_path):
        import shutil
        destino = self.base_dir / 'Guardia'
        destino.mkdir(parents=True, exist_ok=True)
        shutil.move(str(archivo_path), str(destino / archivo_path.name))

    def mover_archivo_internacion(self, archivo_path):
        import shutil
        destino = self.base_dir / 'Internación'
        destino.mkdir(parents=True, exist_ok=True)
        shutil.move(str(archivo_path), str(destino / archivo_path.name))

    def procesar_archivos_pendientes(self, horas_espera=24):
        """
        Procesa todos los archivos PDF en la carpeta pendientes que tengan
        al menos 'horas_espera' horas de antigüedad
        
        Args:
            horas_espera: Horas que deben pasar desde la creación del archivo
        
        Retorna un dict con estadísticas del procesamiento
        """
        stats = {
            'procesados': 0,
            'enviados': 0,
            'errores': 0,
            'omitidos': 0,
            'sin_email': 0,
            'otros_origenes': 0,
            'detalles': []
        }
        
        # Buscar todos los PDFs en la carpeta pendientes
        archivos_pdf = list(self.pendientes_dir.glob('*.pdf'))
        
        for archivo_path in archivos_pdf:
            # Verificar antigüedad del archivo
            if not self._archivo_cumple_tiempo_espera(archivo_path, horas_espera):
                stats['omitidos'] += 1
                continue
            stats['procesados'] += 1
            try:
                resultado = self.procesar_archivo(archivo_path)
                if resultado['exito']:
                    stats['enviados'] += 1
                elif resultado.get('sin_email'):
                    stats['sin_email'] += 1
                elif resultado.get('otro_origen'):
                    stats['otros_origenes'] += 1
                else:
                    stats['errores'] += 1
                stats['detalles'].append(resultado)
            except Exception as e:
                stats['errores'] += 1
                stats['detalles'].append({
                    'archivo': archivo_path.name,
                    'exito': False,
                    'error': str(e)
                })
        
        return stats
    
    def procesar_archivo(self, archivo_path):
        """
        Procesa un archivo individual: parsea el nombre, busca/crea el registro,
        envía el email y mueve el archivo
        """
        resultado = {
            'archivo': archivo_path.name,
            'exito': False,
            'error': None
        }
        
        try:
            # Parsear el nombre del archivo: [Origen]_[DNI]_[N Peticion]_[Turno].pdf
            datos = self.parsear_nombre_archivo(archivo_path.name)
            if not datos:
                resultado['error'] = 'Formato de nombre de archivo inválido'
                return resultado
            
            # Solo los archivos de origen Ambulatorio se envían por mail
            if datos['origen'] == 'Internacion':
                resultado['error'] = "Informe de Internación, movido a carpeta Internación (no se envía por mail)"
                resultado['otro_origen'] = True
                self.mover_archivo_internacion(archivo_path)
                return resultado
            if datos['origen'] == 'Guardia':
                resultado['error'] = "Informe de Guardia, movido a carpeta Guardia (no se envía por mail)"
                resultado['otro_origen'] = True
                self.mover_archivo_guardia(archivo_path)
                return resultado
            if datos['origen'] != 'Ambulatorio':
                resultado['error'] = f"Origen '{datos['origen']}' no corresponde a envío por email"
                resultado['otro_origen'] = True
                self.mover_archivo_otro_origen(archivo_path)
                return resultado
                def mover_archivo_internacion(self, archivo_path):
                    destino = self.base_dir / 'Internación'
                    destino.mkdir(parents=True, exist_ok=True)
                    archivo_path.rename(destino / archivo_path.name)

                def mover_archivo_guardia(self, archivo_path):
                    destino = self.base_dir / 'Guardia'
                    destino.mkdir(parents=True, exist_ok=True)
                    archivo_path.rename(destino / archivo_path.name)
            
            # Buscar o crear el paciente
            paciente = self.buscar_paciente(datos['iden'])
            if not paciente:
                resultado['error'] = f"Paciente con identificación {datos['iden']} no encontrado"
                self.mover_archivo_sin_email(archivo_path)
                return resultado
            
            # Validar que el paciente tenga email
            if not paciente.email:
                resultado['error'] = f"Paciente {datos['iden']} no tiene email registrado"
                resultado['sin_email'] = True
                self.mover_archivo_sin_email(archivo_path)
                return resultado
            
            # Buscar o crear el registro del informe
            with transaction.atomic():
                informe, created = Informes.objects.get_or_create(
                    paciente=paciente,
                    numero_orden=datos['orden'],
                    numero_protocolo=datos['protocolo'],
                    defaults={
                        'nombre_archivo': archivo_path.name,
                        'email_destino': paciente.email,
                        'estado': 'PENDIENTE'
                    }
                )
                
                # Si el informe ya fue enviado, no lo procesamos de nuevo
                if informe.estado == 'ENVIADO' and not created:
                    resultado['error'] = 'El informe ya fue enviado anteriormente'
                    return resultado
                
                # Intentar enviar el email
                exito_envio = self.enviar_email(informe, archivo_path)
                
                if exito_envio:
                    # Marcar como enviado
                    informe.estado = 'ENVIADO'
                    informe.fecha_envio = timezone.now()
                    informe.mensaje_error = ''
                    informe.save()
                    
                    # Mover el archivo a enviados
                    self.mover_archivo_enviado(archivo_path)
                    
                    resultado['exito'] = True
                    resultado['mensaje'] = f'Informe enviado a {paciente.email}'

                    # Envío por WhatsApp desactivado temporalmente
                    # if paciente.telefono:
                    #     exito_wa = self.enviar_whatsapp(informe, paciente)
                    #     if exito_wa:
                    #         resultado['whatsapp'] = f'WhatsApp enviado a {paciente.telefono}'
                    #     else:
                    #         resultado['whatsapp_error'] = informe.whatsapp_error
                else:
                    # Marcar como error
                    informe.estado = 'ERROR'
                    informe.intentos_envio += 1
                    informe.save()
                    resultado['error'] = informe.mensaje_error
                    
        except Exception as e:
            resultado['error'] = f'Error al procesar: {str(e)}'
        
        return resultado
    
    def parsear_nombre_archivo(self, nombre_archivo):
        """
        Parsea el nombre del archivo en formato:
        [Origen]_[DNI]_[NPeticion]-[Turno].pdf
        o
        [Origen]_[DNI]_[NPeticion]_[Turno].pdf
        El campo Turno puede ser opcional.
        Orígenes válidos: Internacion, Guardia, Ambulatorio
        Retorna un dict con los datos o None si el formato es inválido
        """
        try:
            nombre_sin_ext = Path(nombre_archivo).stem
            partes = [p.strip() for p in nombre_sin_ext.split('_') if p.strip()]
            origenes_validos = ('Internacion', 'Internación', 'Guardia', 'Ambulatorio')
            if len(partes) < 3:
                return None
            origen = partes[0]
            if origen not in origenes_validos:
                return None
            iden = partes[1]
            orden = partes[2]
            protocolo = partes[3] if len(partes) > 3 else ''
            return {
                'origen': origen,
                'iden': iden,
                'orden': int(orden) if orden.isdigit() else orden,
                'protocolo': protocolo,
            }
        except (ValueError, IndexError):
            return None
    
    def buscar_paciente(self, iden):
        """Busca un paciente por su identificación"""
        try:
            return Paciente.objects.get(iden=iden)
        except Paciente.DoesNotExist:
            return None
    
    def _archivo_cumple_tiempo_espera(self, archivo_path, horas_espera):
        """
        Verifica si un archivo tiene la antigüedad mínima requerida
        
        Args:
            archivo_path: Path del archivo a verificar
            horas_espera: Horas que deben haber pasado desde la creación
        
        Returns:
            True si el archivo cumple el tiempo de espera, False en caso contrario
        """
        from datetime import timedelta
        
        # Obtener la fecha de creación del archivo
        timestamp_creacion = archivo_path.stat().st_ctime
        fecha_creacion = timezone.datetime.fromtimestamp(timestamp_creacion, tz=timezone.get_current_timezone())
        
        # Calcular el tiempo transcurrido
        tiempo_transcurrido = timezone.now() - fecha_creacion
        tiempo_minimo = timedelta(hours=horas_espera)
        
        return tiempo_transcurrido >= tiempo_minimo
    
    def obtener_archivos_pendientes_info(self, horas_espera=24):
        """
        Retorna información sobre los archivos pendientes y su estado
        """
        from datetime import timedelta
        
        archivos_info = []
        archivos_pdf = list(self.pendientes_dir.glob('*.pdf'))
        
        for archivo_path in archivos_pdf:
            timestamp_creacion = archivo_path.stat().st_ctime
            fecha_creacion = timezone.datetime.fromtimestamp(timestamp_creacion, tz=timezone.get_current_timezone())
            tiempo_transcurrido = timezone.now() - fecha_creacion
            tiempo_minimo = timedelta(hours=horas_espera)
            tiempo_restante = tiempo_minimo - tiempo_transcurrido
            
            archivos_info.append({
                'nombre': archivo_path.name,
                'fecha_creacion': fecha_creacion,
                'horas_transcurridas': tiempo_transcurrido.total_seconds() / 3600,
                'listo_para_enviar': tiempo_transcurrido >= tiempo_minimo,
                'horas_restantes': max(0, tiempo_restante.total_seconds() / 3600)
            })
        
        return archivos_info
    
    def enviar_email(self, informe, archivo_path):
        """
        Envía el email con el PDF adjunto
        Retorna True si el envío fue exitoso, False en caso contrario
        """
        try:
            # Preparar el email
            asunto = f'Informe Médico - Petición {informe.numero_orden} - Turno {informe.numero_protocolo}'
            
            cuerpo = f"""
Estimado/a {informe.paciente.nombre} {informe.paciente.apellido},

Adjuntamos su informe médico correspondiente a:

- N° de Petición: {informe.numero_orden}
- N° de Turno: {informe.numero_protocolo}
- Fecha: {timezone.now().strftime('%d/%m/%Y')}

Por favor, conserve este documento para su historia clínica.

Por favor, no responda a este correo electrónico.
Para cualquier consulta puede contactarnos:
  📧 admlabobalestini@gmail.com
  💬 WhatsApp +54 9 11 2705-3761 (solo mensajes)

Saludos cordiales.
            """.strip()
            
            # Crear el mensaje de email
            email = EmailMessage(
                subject=asunto,
                body=cuerpo,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[informe.email_destino],
            )
            
            # Adjuntar el PDF
            with open(archivo_path, 'rb') as pdf_file:
                email.attach(
                    filename=archivo_path.name,
                    content=pdf_file.read(),
                    mimetype='application/pdf'
                )
            
            # Enviar el email
            email.send(fail_silently=False)
            
            return True
            
        except Exception as e:
            # Guardar el error en el informe
            informe.mensaje_error = f'Error al enviar email: {str(e)}'
            informe.save()
            return False
    
    def _formatear_telefono_whatsapp(self, telefono):
        """
        Convierte el teléfono local almacenado en formato Twilio WhatsApp.
        Ej: '1145678901'  -> 'whatsapp:+5491145678901'
        Si el número ya incluye '+' se usa directamente con el prefijo 'whatsapp:'.
        El código de país se lee de WHATSAPP_CODIGO_PAIS (default '+549' Argentina móvil).
        """
        numero = str(telefono).strip()
        if numero.startswith('+'):
            return f'whatsapp:{numero}'
        codigo_pais = getattr(settings, 'WHATSAPP_CODIGO_PAIS', '+549')
        return f'whatsapp:{codigo_pais}{numero}'

    def enviar_whatsapp(self, informe, paciente):
        """
        Envía una notificación por WhatsApp al paciente informando que su
        informe médico fue procesado y enviado a su correo electrónico.
        Requiere que TWILIO_ACCOUNT_SID y TWILIO_AUTH_TOKEN estén configurados en .env
        Retorna True si el envío fue exitoso, False en caso contrario.
        """
        try:
            account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
            auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')

            if not account_sid or not auth_token:
                informe.whatsapp_error = 'Twilio no configurado (TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN ausentes)'
                informe.save()
                return False

            from twilio.rest import Client

            destino = self._formatear_telefono_whatsapp(paciente.telefono)
            remitente = getattr(settings, 'TWILIO_WHATSAPP_FROM', 'whatsapp:+14155238886')

            mensaje = (
                f"Estimado/a {paciente.nombre} {paciente.apellido},\n\n"
                f"Su informe médico ya fue procesado:\n"
                f"- N\u00ba Petición: {informe.numero_orden}\n"
                f"- N\u00ba Turno: {informe.numero_protocolo}\n\n"
                f"El mismo fue enviado a su correo electrónico registrado.\n"
                f"Ante cualquier consulta, no dude en contactarnos."
            )

            client = Client(account_sid, auth_token)
            message = client.messages.create(
                body=mensaje,
                from_=remitente,
                to=destino,
            )

            informe.whatsapp_enviado = True
            informe.whatsapp_telefono = destino
            informe.whatsapp_error = ''
            informe.save()
            return True

        except Exception as e:
            informe.whatsapp_error = f'Error al enviar WhatsApp: {str(e)}'
            informe.save()
            return False

    def mover_archivo_otro_origen(self, archivo_path):
        """Mueve archivos de Internacion o Guardia a otros_origenes"""
        try:
            destino = self.otros_origenes_dir / archivo_path.name
            
            if destino.exists():
                timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
                nombre_base = archivo_path.stem
                destino = self.otros_origenes_dir / f"{nombre_base}_{timestamp}.pdf"
            
            shutil.move(str(archivo_path), str(destino))
            
        except Exception as e:
            print(f"Error al mover archivo de otro origen {archivo_path.name}: {e}")

    def mover_archivo_sin_email(self, archivo_path):
        """Mueve el archivo de pendientes a sin_email"""
        try:
            destino = self.sin_email_dir / archivo_path.name
            
            # Si ya existe, agregar timestamp
            if destino.exists():
                timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
                nombre_base = archivo_path.stem
                destino = self.sin_email_dir / f"{nombre_base}_{timestamp}.pdf"
            
            shutil.move(str(archivo_path), str(destino))
            
        except Exception as e:
            print(f"Error al mover archivo sin email {archivo_path.name}: {e}")

    def mover_archivo_enviado(self, archivo_path):
        """Mueve el archivo de pendientes a enviados"""
        try:
            destino = self.enviados_dir / archivo_path.name
            
            # Si ya existe en enviados, agregar timestamp
            if destino.exists():
                timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
                nombre_base = archivo_path.stem
                destino = self.enviados_dir / f"{nombre_base}_{timestamp}.pdf"
            
            shutil.move(str(archivo_path), str(destino))
            
        except Exception as e:
            print(f"Error al mover archivo {archivo_path.name}: {e}")
            # No lanzamos la excepción para no bloquear el flujo
    
    def obtener_estadisticas(self):
        """Retorna estadísticas de los informes"""
        from django.db.models import Count
        
        return {
            'total': Informes.objects.count(),
            'pendientes': Informes.objects.filter(estado='PENDIENTE').count(),
            'enviados': Informes.objects.filter(estado='ENVIADO').count(),
            'errores': Informes.objects.filter(estado='ERROR').count(),
            'por_estado': Informes.objects.values('estado').annotate(count=Count('id'))
        }
