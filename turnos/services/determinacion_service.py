"""
Servicio para manejar lógica de determinaciones, perfiles y determinaciones complejas.
"""
from typing import List, Dict, Any, Tuple
from determinaciones.models import Determinacion, PerfilDeterminacion, DeterminacionCompleja


class DeterminacionService:
    """Servicio para procesar y formatear determinaciones."""
    
    @staticmethod
    def parsear_codigos(determinaciones_texto: str) -> Tuple[List[str], List[str]]:
        """
        Separa códigos en determinaciones simples y códigos con slash (perfiles/complejas).
        
        Args:
            determinaciones_texto: String con códigos separados por coma
            
        Returns:
            Tupla (códigos_simples, códigos_con_slash)
        """
        if not determinaciones_texto:
            return [], []
        
        codigos = [c.strip() for c in determinaciones_texto.split(',') if c.strip()]
        det_codes = [c for c in codigos if not c.startswith('/')]
        codigos_con_slash = [c for c in codigos if c.startswith('/')]
        
        return det_codes, codigos_con_slash
    
    @staticmethod
    def obtener_nombres_determinaciones(determinaciones_texto: str) -> List[str]:
        """
        Convierte códigos de determinaciones a nombres legibles.
        
        Args:
            determinaciones_texto: String con códigos separados por coma
            
        Returns:
            Lista de nombres de determinaciones
        """
        if not determinaciones_texto:
            return []
        
        det_codes, codigos_con_slash = DeterminacionService.parsear_codigos(determinaciones_texto)
        nombres = []
        
        # Determinaciones simples
        if det_codes:
            det_map = {d.codigo: d.nombre for d in Determinacion.objects.filter(codigo__in=det_codes)}
            for code in det_codes:
                nombres.append(det_map.get(code, code))
        
        # Procesar códigos con slash
        for code in codigos_con_slash:
            code_sin_slash = code.lstrip('/')
            
            # Intentar como determinación compleja
            compleja = DeterminacionCompleja.objects.filter(codigo=code).first()
            if compleja:
                nombres.append(compleja.nombre)
                continue
            
            # Buscar como perfil
            perfil = PerfilDeterminacion.objects.filter(codigo=code_sin_slash).first()
            if perfil:
                cant = len(perfil.determinaciones or [])
                nombres.append(f"Perfil {perfil.codigo} ({cant} dets)")
        
        return nombres
    
    @staticmethod
    def obtener_determinaciones_detalladas(determinaciones_texto: str) -> List[Dict[str, Any]]:
        """
        Obtiene información detallada de todas las determinaciones.
        
        Args:
            determinaciones_texto: String con códigos separados por coma
            
        Returns:
            Lista de diccionarios con información detallada de cada determinación
        """
        if not determinaciones_texto:
            return []
        
        det_codes, codigos_con_slash = DeterminacionService.parsear_codigos(determinaciones_texto)
        determinaciones_detalle = []
        
        # Determinaciones simples
        for codigo in det_codes:
            det = Determinacion.objects.filter(codigo=codigo).first()
            if det:
                determinaciones_detalle.append({
                    'tipo': 'determinacion',
                    'codigo': det.codigo,
                    'nombre': det.nombre,
                    'stock': det.stock
                })
            else:
                determinaciones_detalle.append({
                    'tipo': 'desconocido',
                    'codigo': codigo,
                    'nombre': 'Código no encontrado'
                })
        
        # Perfiles y complejas
        for codigo in codigos_con_slash:
            code_sin_slash = codigo.lstrip('/')
            
            # Buscar en perfiles
            perfil = PerfilDeterminacion.objects.filter(codigo=code_sin_slash).first()
            if perfil:
                determinaciones_detalle.append({
                    'tipo': 'perfil',
                    'codigo': perfil.codigo,
                    'nombre': perfil.nombre,
                    'determinaciones': perfil.determinaciones
                })
                continue
            
            # Buscar en complejas
            compleja = DeterminacionCompleja.objects.filter(codigo=codigo).first()
            if compleja:
                determinaciones_detalle.append({
                    'tipo': 'compleja',
                    'codigo': compleja.codigo,
                    'nombre': compleja.nombre,
                    'stock': compleja.stock
                })
                continue
            
            # Si no se encuentra
            determinaciones_detalle.append({
                'tipo': 'desconocido',
                'codigo': codigo,
                'nombre': 'Código no encontrado'
            })
        
        return determinaciones_detalle
    
    @staticmethod
    def expandir_determinaciones_para_astm(determinaciones_texto: str) -> List[str]:
        """
        Expande determinaciones para formato ASTM.
        
        Args:
            determinaciones_texto: String con códigos separados por coma
            
        Returns:
            Lista de códigos en formato ASTM
        """
        if not determinaciones_texto:
            return []
        
        det_codes, codigos_con_slash = DeterminacionService.parsear_codigos(determinaciones_texto)
        determinaciones_astm = []
        
        # Determinaciones simples
        if det_codes:
            determinaciones_astm.extend([f'^^^{c}\\' for c in det_codes])
        
        # Determinaciones complejas
        if codigos_con_slash:
            complejas = DeterminacionCompleja.objects.filter(codigo__in=codigos_con_slash)
            for compleja in complejas:
                for det_code in compleja.determinaciones:
                    determinaciones_astm.append(f'^^^{det_code}\\')
            
            # Perfiles
            perfil_codes = [c.lstrip('/') for c in codigos_con_slash]
            perfiles = PerfilDeterminacion.objects.filter(codigo__in=perfil_codes)
            for perfil in perfiles:
                for det_code in perfil.determinaciones:
                    if det_code.startswith('/'):
                        # Expandir determinación compleja dentro del perfil
                        compleja_en_perfil = DeterminacionCompleja.objects.filter(codigo=det_code).first()
                        if compleja_en_perfil:
                            for sub_det_code in compleja_en_perfil.determinaciones:
                                determinaciones_astm.append(f'^^^{sub_det_code}\\')
                    else:
                        determinaciones_astm.append(f'^^^{det_code}\\')
        
        return determinaciones_astm
    
    @staticmethod
    def calcular_max_tiempo(determinaciones_texto: str) -> int:
        """
        Calcula el tiempo máximo (en días) entre todas las determinaciones.
        
        Args:
            determinaciones_texto: String con códigos separados por coma
            
        Returns:
            Número máximo de días
        """
        if not determinaciones_texto:
            return 0
        
        det_codes, codigos_con_slash = DeterminacionService.parsear_codigos(determinaciones_texto)
        tiempos = []
        
        # Tiempos de determinaciones simples
        if det_codes:
            tiempos.extend([
                d.tiempo for d in Determinacion.objects.filter(codigo__in=det_codes)
                if d.tiempo is not None
            ])
        
        # Tiempos de complejas y perfiles
        if codigos_con_slash:
            # Quitar el '/' de los códigos
            codigos_sin_slash = [c.lstrip('/') for c in codigos_con_slash]
            
            # Determinaciones complejas
            complejas = DeterminacionCompleja.objects.filter(codigo__in=codigos_sin_slash)
            dets_complejas = []
            for compleja in complejas:
                dets_complejas.extend(compleja.determinaciones)
            if dets_complejas:
                tiempos.extend([
                    d.tiempo for d in Determinacion.objects.filter(codigo__in=dets_complejas)
                    if d.tiempo is not None
                ])
            
            # Perfiles
            perfiles = PerfilDeterminacion.objects.filter(codigo__in=codigos_sin_slash)
            dets_perfiles = []
            for perfil in perfiles:
                for det_code in perfil.determinaciones:
                    if det_code.startswith('/'):
                        compleja_en_perfil = DeterminacionCompleja.objects.filter(codigo=det_code).first()
                        if compleja_en_perfil:
                            dets_perfiles.extend(compleja_en_perfil.determinaciones)
                    else:
                        dets_perfiles.append(det_code)
            if dets_perfiles:
                tiempos.extend([
                    d.tiempo for d in Determinacion.objects.filter(codigo__in=dets_perfiles)
                    if d.tiempo is not None
                ])
        
        return max(tiempos) if tiempos else 0
