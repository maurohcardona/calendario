"""
Comando de Django para procesar y enviar informes médicos pendientes
Uso: python manage.py procesar_informes
"""
from django.core.management.base import BaseCommand
from informes.services import InformesService


class Command(BaseCommand):
    help = 'Procesa los archivos PDF pendientes en la carpeta informes/pendientes y los envía por email'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simula el procesamiento sin enviar emails ni mover archivos',
        )
        parser.add_argument(
            '--horas',
            type=int,
            default=24,
            help='Horas que deben pasar después de crear el PDF antes de enviarlo (default: 24)',
        )
    
    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        horas_espera = options.get('horas', 24)
        
        self.stdout.write(self.style.SUCCESS('='*60))
        self.stdout.write(self.style.SUCCESS('PROCESAMIENTO DE INFORMES MÉDICOS'))
        self.stdout.write(self.style.SUCCESS('='*60))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('MODO DRY-RUN (simulación)'))
        
        self.stdout.write(f'Tiempo de espera: {horas_espera} hora(s) después de creado el PDF')
        self.stdout.write('')
        
        # Crear instancia del servicio
        service = InformesService()
        
        # Mostrar estadísticas previas
        self.stdout.write(self.style.HTTP_INFO('📊 Estadísticas previas:'))
        stats_previas = service.obtener_estadisticas()
        self.stdout.write(f"  • Total de registros: {stats_previas['total']}")
        self.stdout.write(f"  • Pendientes: {stats_previas['pendientes']}")
        self.stdout.write(f"  • Enviados: {stats_previas['enviados']}")
        self.stdout.write(f"  • Con errores: {stats_previas['errores']}")
        self.stdout.write('')
        
        # Procesar archivos
        self.stdout.write(self.style.HTTP_INFO('📂 Procesando archivos...'))
        
        if not dry_run:
            resultados = service.procesar_archivos_pendientes(horas_espera=horas_espera)
            
            # Mostrar resultados
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('✅ PROCESAMIENTO COMPLETADO'))
            self.stdout.write('')
            self.stdout.write(f"  • Archivos procesados: {resultados['procesados']}")
            self.stdout.write(self.style.SUCCESS(f"  • Enviados exitosamente: {resultados['enviados']}"))
            
            if resultados['errores'] > 0:
                self.stdout.write(self.style.ERROR(f"  • Errores: {resultados['errores']}"))
            
            if resultados['omitidos'] > 0:
                self.stdout.write(self.style.WARNING(f"  • Omitidos (sin antigüedad suficiente): {resultados['omitidos']}"))
            
            # Mostrar detalles
            if resultados['detalles']:
                self.stdout.write('')
                self.stdout.write(self.style.HTTP_INFO('📋 Detalles:'))
                for detalle in resultados['detalles']:
                    if detalle['exito']:
                        self.stdout.write(self.style.SUCCESS(
                            f"  ✓ {detalle['archivo']} - {detalle.get('mensaje', 'Enviado')}"
                        ))
                    else:
                        self.stdout.write(self.style.ERROR(
                            f"  ✗ {detalle['archivo']} - {detalle.get('error', 'Error desconocido')}"
                        ))
            
            # Estadísticas finales
            self.stdout.write('')
            self.stdout.write(self.style.HTTP_INFO('📊 Estadísticas finales:'))
            stats_finales = service.obtener_estadisticas()
            self.stdout.write(f"  • Total de registros: {stats_finales['total']}")
            self.stdout.write(f"  • Pendientes: {stats_finales['pendientes']}")
            self.stdout.write(f"  • Enviados: {stats_finales['enviados']}")
            self.stdout.write(f"  • Con errores: {stats_finales['errores']}")
        else:
            # Modo dry-run: mostrar información de archivos con su antigüedad
            archivos_info = service.obtener_archivos_pendientes_info(horas_espera=horas_espera)
            
            if not archivos_info:
                self.stdout.write(self.style.WARNING('  No hay archivos pendientes para procesar'))
            else:
                self.stdout.write(f'  Se encontraron {len(archivos_info)} archivo(s):\n')
                
                for info in archivos_info:
                    self.stdout.write(f'    📄 {info["nombre"]}')
                    
                    # Parsear datos del archivo
                    datos = service.parsear_nombre_archivo(info['nombre'])
                    if datos:
                        paciente = service.buscar_paciente(datos['iden'])
                        if paciente:
                            self.stdout.write(f'       Paciente: {paciente.apellido}, {paciente.nombre}')
                            self.stdout.write(f'       Email: {paciente.email or "NO REGISTRADO"}')
                        else:
                            self.stdout.write(self.style.WARNING(f'       PACIENTE NO ENCONTRADO'))
                    else:
                        self.stdout.write(self.style.ERROR(f'       FORMATO INVÁLIDO'))
                    
                    # Mostrar antigüedad y estado
                    self.stdout.write(f'       Creado: {info["fecha_creacion"].strftime("%d/%m/%Y %H:%M")}')
                    self.stdout.write(f'       Antigüedad: {info["horas_transcurridas"]:.1f} horas')
                    
                    if info['listo_para_enviar']:
                        self.stdout.write(self.style.SUCCESS(f'       ✓ Listo para enviar'))
                    else:
                        self.stdout.write(self.style.WARNING(
                            f'       ⏳ Faltan {info["horas_restantes"]:.1f} horas para enviar'
                        ))
                    self.stdout.write('')
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('='*60))
