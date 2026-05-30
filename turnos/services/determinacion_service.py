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
    def mapear_determinaciones_a_hl7(determinaciones_texto: str) -> List[Dict[str, Any]]:
        """
        Expande determinaciones para formato HL7 OML^O21.

        Sigue la misma lógica de expansión que expandir_determinaciones_para_astm,
        pero retorna dicts con 'codigo' y 'nombre' para construir segmentos OBR.

        Perfiles y complejas se expanden a sus determinaciones atómicas.

        Args:
            determinaciones_texto: String con códigos separados por coma

        Returns:
            Lista de dicts: [{"codigo": str, "nombre": str}, ...]
        """
        if not determinaciones_texto:
            return []

        det_codes, codigos_con_slash = DeterminacionService.parsear_codigos(determinaciones_texto)
        resultado: List[Dict[str, Any]] = []

        # ── Determinaciones simples ───────────────────────────────────────────
        if det_codes:
            det_map = {
                d.codigo: d
                for d in Determinacion.objects.filter(codigo__in=det_codes)
            }
            for codigo in det_codes:
                det = det_map.get(codigo)
                resultado.append({
                    "codigo": codigo,
                    "nombre": det.nombre if det else codigo,
                })

        # ── Complejas y perfiles ──────────────────────────────────────────────
        for codigo_slash in codigos_con_slash:
            code_sin_slash = codigo_slash.lstrip("/")

            # Determinación compleja (/XXXX)
            compleja = DeterminacionCompleja.objects.filter(codigo=codigo_slash).first()
            if compleja:
                sub_codes = compleja.determinaciones or []
                sub_map = {
                    d.codigo: d
                    for d in Determinacion.objects.filter(codigo__in=sub_codes)
                }
                for sub_code in sub_codes:
                    sub = sub_map.get(sub_code)
                    resultado.append({
                        "codigo": sub_code,
                        "nombre": sub.nombre if sub else sub_code,
                    })
                continue

            # Perfil (/XXXX)
            perfil = PerfilDeterminacion.objects.filter(codigo=code_sin_slash).first()
            if perfil:
                for det_code in perfil.determinaciones or []:
                    if det_code.startswith("/"):
                        # Compleja dentro del perfil
                        compleja_en_perfil = DeterminacionCompleja.objects.filter(
                            codigo=det_code
                        ).first()
                        if compleja_en_perfil:
                            sub_codes = compleja_en_perfil.determinaciones or []
                            sub_map = {
                                d.codigo: d
                                for d in Determinacion.objects.filter(codigo__in=sub_codes)
                            }
                            for sub_code in sub_codes:
                                sub = sub_map.get(sub_code)
                                resultado.append({
                                    "codigo": sub_code,
                                    "nombre": sub.nombre if sub else sub_code,
                                })
                    else:
                        det = Determinacion.objects.filter(codigo=det_code).first()
                        resultado.append({
                            "codigo": det_code,
                            "nombre": det.nombre if det else det_code,
                        })
                continue

            # No encontrado: incluir tal cual
            resultado.append({"codigo": codigo_slash, "nombre": codigo_slash})

        return resultado

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

    @staticmethod
    def serializar_determinaciones_orden(orden: "Any") -> str:
        """
        Convierte las determinaciones M2M de una OrdenLaboratorio a formato CSV.

        Genera la misma cadena que se usa en Turno.determinaciones (TextField CSV),
        necesaria para pasarle a mapear_determinaciones_a_hl7().

        Args:
            orden: Instancia de OrdenLaboratorio con sus relaciones M2M cargadas.

        Returns:
            String de códigos separados por coma.
            Determinaciones simples: código directo (ej: "GLUCEMIA").
            Determinaciones complejas: código con prefijo "/" (ej: "/HEPATO").

        Ejemplo:
            "GLUCEMIA,UREA,/HEPATO"
        """
        codigos: List[str] = []

        for det in orden.determinaciones.all():
            codigos.append(det.codigo)

        for det_c in orden.determinaciones_complejas.all():
            # Los códigos complejos ya incluyen "/" en la BD; asegurar prefijo.
            codigo = det_c.codigo if det_c.codigo.startswith("/") else f"/{det_c.codigo}"
            codigos.append(codigo)

        return ",".join(codigos)
