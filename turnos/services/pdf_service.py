"""
Servicio para generación de PDFs (tickets de turno y retiro).
"""
from datetime import date, timedelta
from io import BytesIO
from typing import Optional
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from django.http import HttpResponse
from turnos.models import Turno
from .determinacion_service import DeterminacionService


class PDFService:
    """Servicio para generar PDFs de tickets."""
    
    # Configuración de impresora térmica
    ANCHO_PAPEL = 8 * cm
    ALTO_PAPEL = 18 * cm
    MARGEN = 0.3 * cm
    
    @staticmethod
    def _calcular_edad(fecha_nacimiento: date, fecha_referencia: date) -> Optional[int]:
        """Calcula la edad a partir de una fecha de nacimiento."""
        if not fecha_nacimiento:
            return None
        
        edad = fecha_referencia.year - fecha_nacimiento.year
        if (fecha_referencia.month, fecha_referencia.day) < (fecha_nacimiento.month, fecha_nacimiento.day):
            edad -= 1
        return edad
    
    @staticmethod
    def _escribir_texto_centrado(p: canvas.Canvas, y: float, texto: str, fuente: str, tamanio: int, ancho_papel: float):
        """Escribe texto centrado en el PDF."""
        p.setFont(fuente, tamanio)
        p.drawCentredString(ancho_papel / 2, y, texto)
    
    @staticmethod
    def _escribir_campo(p: canvas.Canvas, y: float, etiqueta: str, valor: str, margen: float, col_etiqueta: float = 2*cm) -> float:
        """
        Escribe un campo con etiqueta y valor.
        
        Returns:
            Nueva posición y después de escribir
        """
        p.setFont("Helvetica-Bold", 9)
        p.drawString(margen, y, etiqueta)
        p.setFont("Helvetica", 9)
        p.drawString(margen + col_etiqueta, y, str(valor))
        return y - 0.45 * cm
    
    @staticmethod
    def generar_ticket_turno(turno: Turno, usuario_asignador: str) -> HttpResponse:
        """
        Genera un ticket PDF de turno para impresora térmica.
        
        Args:
            turno: Instancia del turno
            usuario_asignador: Usuario que genera el ticket
            
        Returns:
            HttpResponse con el PDF
        """
        paciente_obj = turno.dni
        
        # Calcular edad
        edad = None
        if paciente_obj and paciente_obj.fecha_nacimiento:
            edad = PDFService._calcular_edad(paciente_obj.fecha_nacimiento, turno.fecha)
        
        # Obtener nombres de determinaciones
        determinaciones_nombres = DeterminacionService.obtener_nombres_determinaciones(turno.determinaciones or '')
        
        # Preparar datos
        agenda_nombre = turno.agenda.name if turno.agenda else ""
        apellido = turno.apellido or ""
        nombre = turno.nombre or ""
        dni = turno.paciente_dni or ""
        telefono = paciente_obj.telefono if paciente_obj else ""
        email = paciente_obj.email if paciente_obj else ""
        medico_nombre = turno.medico.nombre if turno.medico else ""
        
        # Crear PDF
        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=(PDFService.ANCHO_PAPEL, PDFService.ALTO_PAPEL))
        
        ancho_util = PDFService.ANCHO_PAPEL - (2 * PDFService.MARGEN)
        y = PDFService.ALTO_PAPEL - PDFService.MARGEN
        
        # Encabezado
        PDFService._escribir_texto_centrado(p, y, "Hospital Balestrini", "Helvetica-Bold", 11, PDFService.ANCHO_PAPEL)
        y -= 0.5 * cm
        PDFService._escribir_texto_centrado(p, y, agenda_nombre, "Helvetica", 9, PDFService.ANCHO_PAPEL)
        y -= 0.6 * cm
        p.line(PDFService.MARGEN, y, PDFService.ANCHO_PAPEL - PDFService.MARGEN, y)
        y -= 0.5 * cm
        
        # Datos del paciente
        p.setFont("Helvetica-Bold", 9)
        p.drawString(PDFService.MARGEN, y, "Paciente:")
        p.setFont("Helvetica", 9)
        nombre_completo = f"{apellido.strip().capitalize()}, {nombre.strip().capitalize()}"
        p.drawString(PDFService.MARGEN + 2*cm, y, nombre_completo)
        y -= 0.45 * cm
        
        y = PDFService._escribir_campo(p, y, "DNI:", str(dni), PDFService.MARGEN)
        
        if telefono:
            y = PDFService._escribir_campo(p, y, "Teléfono:", str(telefono), PDFService.MARGEN)
        
        if email:
            p.setFont("Helvetica-Bold", 9)
            p.drawString(PDFService.MARGEN, y, "Email:")
            p.setFont("Helvetica", 7 if len(email) > 30 else 9)
            if len(email) > 30:
                p.drawString(PDFService.MARGEN + 2*cm, y, email[:30])
                y -= 0.35 * cm
                p.drawString(PDFService.MARGEN + 2*cm, y, email[30:])
                y -= 0.45 * cm
            else:
                p.drawString(PDFService.MARGEN + 2*cm, y, email)
                y -= 0.45 * cm
        
        if edad is not None:
            y = PDFService._escribir_campo(p, y, "Edad:", f"{edad} años", PDFService.MARGEN)
        
        if medico_nombre:
            p.setFont("Helvetica-Bold", 9)
            p.drawString(PDFService.MARGEN, y, "Médico:")
            p.setFont("Helvetica", 9)
            medico_str = medico_nombre.strip().capitalize()
            if len(medico_str) > 30:
                p.drawString(PDFService.MARGEN + 2*cm, y, medico_str[:30])
                y -= 0.35 * cm
                p.drawString(PDFService.MARGEN + 2*cm, y, medico_str[30:])
                y -= 0.45 * cm
            else:
                p.drawString(PDFService.MARGEN + 2*cm, y, medico_str)
                y -= 0.45 * cm
        
        # Fecha del turno
        p.setFont("Helvetica-Bold", 10)
        fecha_str = turno.fecha.strftime('%d/%m/%Y')
        p.drawString(PDFService.MARGEN, y, f"Fecha: {fecha_str}")
        y -= 0.5 * cm
        
        # Determinaciones
        if determinaciones_nombres:
            p.setFont("Helvetica-Bold", 9)
            p.drawString(PDFService.MARGEN, y, "Estudios:")
            y -= 0.4 * cm
            p.setFont("Helvetica", 8)
            for det_nombre in determinaciones_nombres:
                # Dividir líneas largas
                if len(det_nombre) > 40:
                    palabras = det_nombre.split()
                    linea_actual = ""
                    for palabra in palabras:
                        if len(linea_actual) + len(palabra) + 1 <= 40:
                            linea_actual += (" " if linea_actual else "") + palabra
                        else:
                            p.drawString(PDFService.MARGEN, y, f"• {linea_actual}")
                            y -= 0.35 * cm
                            linea_actual = palabra
                    if linea_actual:
                        p.drawString(PDFService.MARGEN, y, f"• {linea_actual}")
                        y -= 0.35 * cm
                else:
                    p.drawString(PDFService.MARGEN, y, f"• {det_nombre}")
                    y -= 0.35 * cm
            y -= 0.1 * cm
        
        p.line(PDFService.MARGEN, y, PDFService.ANCHO_PAPEL - PDFService.MARGEN, y)
        y -= 0.5 * cm
        
        # Pie de página
        p.setFont("Helvetica", 10)
        PDFService._escribir_texto_centrado(p, y, f"Ticket asignado por: {usuario_asignador}", "Helvetica", 10, PDFService.ANCHO_PAPEL)
        y -= 0.5 * cm
        PDFService._escribir_texto_centrado(p, y, "admlabobalestrini@gmail.com", "Helvetica", 10, PDFService.ANCHO_PAPEL)
        y -= 0.5 * cm
        PDFService._escribir_texto_centrado(p, y, f"Ticket N° {turno.id}", "Helvetica-Bold", 11, PDFService.ANCHO_PAPEL)
        y -= 0.35 * cm
        from datetime import datetime
        PDFService._escribir_texto_centrado(p, y, datetime.now().strftime('%d/%m/%Y %H:%M'), "Helvetica", 6, PDFService.ANCHO_PAPEL)
        
        p.showPage()
        p.save()
        
        buffer.seek(0)
        response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="ticket_turno_{turno.id}.pdf"'
        return response
    
    @staticmethod
    def generar_ticket_retiro(turno: Turno, usuario_asignador: str) -> HttpResponse:
        """
        Genera un ticket PDF de retiro para impresora térmica.
        
        Args:
            turno: Instancia del turno
            usuario_asignador: Usuario que genera el ticket
            
        Returns:
            HttpResponse con el PDF
        """
        paciente_obj = turno.dni
        
        # Calcular edad
        edad = None
        if paciente_obj and paciente_obj.fecha_nacimiento:
            edad = PDFService._calcular_edad(paciente_obj.fecha_nacimiento, turno.fecha)
        
        # Calcular fecha de retiro
        max_tiempo = DeterminacionService.calcular_max_tiempo(turno.determinaciones or '')
        fecha_retiro = date.today() + timedelta(days=max_tiempo)
        
        # Preparar datos
        agenda_nombre = turno.agenda.name if turno.agenda else ""
        apellido = turno.apellido or ""
        nombre = turno.nombre or ""
        dni = turno.paciente_dni or ""
        telefono = paciente_obj.telefono if paciente_obj else ""
        email = paciente_obj.email if paciente_obj else ""
        medico_nombre = turno.medico.nombre if turno.medico else ""
        
        # Crear PDF
        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=(PDFService.ANCHO_PAPEL, PDFService.ALTO_PAPEL))
        
        y = PDFService.ALTO_PAPEL - PDFService.MARGEN
        
        # Encabezado
        PDFService._escribir_texto_centrado(p, y, "Hospital Balestrini", "Helvetica-Bold", 11, PDFService.ANCHO_PAPEL)
        y -= 0.5 * cm
        PDFService._escribir_texto_centrado(p, y, agenda_nombre, "Helvetica", 9, PDFService.ANCHO_PAPEL)
        y -= 0.6 * cm
        p.line(PDFService.MARGEN, y, PDFService.ANCHO_PAPEL - PDFService.MARGEN, y)
        y -= 0.5 * cm
        
        # Datos del paciente
        p.setFont("Helvetica-Bold", 9)
        p.drawString(PDFService.MARGEN, y, "Paciente:")
        p.setFont("Helvetica", 9)
        nombre_completo = f"{apellido.strip().capitalize()}, {nombre.strip().capitalize()}"
        p.drawString(PDFService.MARGEN + 2*cm, y, nombre_completo)
        y -= 0.45 * cm
        
        y = PDFService._escribir_campo(p, y, "DNI:", str(dni), PDFService.MARGEN)
        
        if telefono:
            y = PDFService._escribir_campo(p, y, "Teléfono:", str(telefono), PDFService.MARGEN)
        
        if email:
            p.setFont("Helvetica-Bold", 9)
            p.drawString(PDFService.MARGEN, y, "Email:")
            p.setFont("Helvetica", 7 if len(email) > 30 else 9)
            if len(email) > 30:
                p.drawString(PDFService.MARGEN + 2*cm, y, email[:30])
                y -= 0.35 * cm
                p.drawString(PDFService.MARGEN + 2*cm, y, email[30:])
                y -= 0.45 * cm
            else:
                p.drawString(PDFService.MARGEN + 2*cm, y, email)
                y -= 0.45 * cm
        
        if edad is not None:
            y = PDFService._escribir_campo(p, y, "Edad:", f"{edad} años", PDFService.MARGEN)
        
        if medico_nombre:
            p.setFont("Helvetica-Bold", 9)
            p.drawString(PDFService.MARGEN, y, "Médico:")
            p.setFont("Helvetica", 9)
            medico_str = medico_nombre.strip().capitalize()
            if len(medico_str) > 30:
                p.drawString(PDFService.MARGEN + 2*cm, y, medico_str[:30])
                y -= 0.35 * cm
                p.drawString(PDFService.MARGEN + 2*cm, y, medico_str[30:])
                y -= 0.45 * cm
            else:
                p.drawString(PDFService.MARGEN + 2*cm, y, medico_str)
                y -= 0.45 * cm
        
        # Fecha de retiro
        p.setFont("Helvetica-Bold", 10)
        fecha_retiro_str = fecha_retiro.strftime('%d/%m/%Y')
        p.drawString(PDFService.MARGEN, y, f"Fecha de retiro: a partir de {fecha_retiro_str}")
        y -= 0.45 * cm
        p.setFont("Helvetica", 11)
        p.drawString(PDFService.MARGEN, y, "De lunes a viernes de 10 a 17 hs")
        y -= 0.5 * cm
        
        p.line(PDFService.MARGEN, y, PDFService.ANCHO_PAPEL - PDFService.MARGEN, y)
        y -= 0.5 * cm
        
        # Pie de página
        PDFService._escribir_texto_centrado(p, y, f"Ticket asignado por: {usuario_asignador}", "Helvetica", 10, PDFService.ANCHO_PAPEL)
        y -= 0.5 * cm
        PDFService._escribir_texto_centrado(p, y, "admlabobalestrini@gmail.com", "Helvetica", 10, PDFService.ANCHO_PAPEL)
        y -= 0.5 * cm
        PDFService._escribir_texto_centrado(p, y, f"Ticket N° {turno.id}", "Helvetica-Bold", 11, PDFService.ANCHO_PAPEL)
        y -= 0.35 * cm
        from datetime import datetime
        PDFService._escribir_texto_centrado(p, y, datetime.now().strftime('%d/%m/%Y %H:%M'), "Helvetica", 6, PDFService.ANCHO_PAPEL)
        
        p.showPage()
        p.save()
        
        buffer.seek(0)
        response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="ticket_retiro_{turno.id}.pdf"'
        return response
