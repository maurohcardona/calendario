"""
Servicio para lógica de negocio relacionada con turnos.
"""

import unicodedata
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from django.db import transaction
from django.core.exceptions import ValidationError
from turnos.models import Turno, Cupo, Agenda, Feriados
from pacientes.models import Paciente
from medicos.models import Medico
from instituciones.models import Institucion

# Límite de edad en días para considerar a un paciente como recién nacido (NEO)
NEO_LIMITE_DIAS = 90


def _normalizar_texto(texto: str) -> str:
    """
    Normaliza un texto para generar el número NEO.

    Elimina acentos, convierte Ñ→N, y conserva solo letras en mayúsculas.

    Args:
        texto: Texto a normalizar (nombre o apellido)

    Returns:
        Texto normalizado en mayúsculas, sin acentos ni caracteres especiales
    """
    texto = texto.replace("Ñ", "N").replace("ñ", "n")
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = "".join(c for c in texto if c.isalpha())
    return texto.upper()


def generar_numero_neo_unico(
    nombre: str, apellido: str, fecha_nacimiento
) -> str:
    """
    Genera un número NEO único con formato: {2N}{2A}{DDMMAAAA}RN

    Si el número base ya existe en la base de datos, agrega un sufijo
    incremental: -1, -2, etc.

    Normalización aplicada:
    - Ñ → N
    - Acentos eliminados: José → JOSE
    - Solo primeras 2 letras del primer nombre: "Juan Carlos" → JU
    - Relleno con X si tiene < 2 letras: "Li" → LIX

    Args:
        nombre: Nombre del paciente
        apellido: Apellido del paciente
        fecha_nacimiento: Objeto date o string 'YYYY-MM-DD'

    Returns:
        Número NEO único (ej: "CALO01042010RN" o "CALO01042010RN-1")

    Raises:
        ValueError: Si nombre o apellido no tienen ninguna letra
        ValueError: Si no se puede generar número único en 100 intentos
    """
    nombre_limpio = _normalizar_texto(nombre.strip())
    apellido_limpio = _normalizar_texto(apellido.strip())

    if not nombre_limpio or not apellido_limpio:
        raise ValueError(
            "Nombre y apellido deben contener al menos una letra para generar el número NEO."
        )

    # Primeras 2 letras; rellenar con 'X' si tiene menos de 2
    n = (nombre_limpio + "XX")[:2]
    a = (apellido_limpio + "XX")[:2]

    # Convertir fecha a objeto date si viene como string
    if isinstance(fecha_nacimiento, str):
        fecha_obj = datetime.strptime(fecha_nacimiento, "%Y-%m-%d").date()
    else:
        fecha_obj = fecha_nacimiento

    fecha_formateada = fecha_obj.strftime("%d%m%Y")
    base = f"{n}{a}{fecha_formateada}RN"

    # Buscar número libre con sufijo incremental en caso de colisión
    sufijo = 0
    while True:
        numero_neo = base if sufijo == 0 else f"{base}-{sufijo}"

        if not Paciente.objects.filter(tipo_iden="NEO", iden=numero_neo).exists():
            return numero_neo

        sufijo += 1

        if sufijo > 100:
            raise ValueError(
                f"No se pudo generar número NEO único para '{base}' después de 100 intentos."
            )


def validar_edad_neo(fecha_nacimiento, limite_dias: int = NEO_LIMITE_DIAS) -> Tuple[bool, str]:
    """
    Valida que la fecha de nacimiento corresponda a un recién nacido.

    Args:
        fecha_nacimiento: Objeto date o string 'YYYY-MM-DD'
        limite_dias: Edad máxima en días para considerar recién nacido (default: 90)

    Returns:
        Tupla (es_valido, mensaje_error). mensaje_error es vacío si es válido.
    """
    if isinstance(fecha_nacimiento, str):
        fecha_obj = datetime.strptime(fecha_nacimiento, "%Y-%m-%d").date()
    else:
        fecha_obj = fecha_nacimiento

    hoy = date.today()
    edad_dias = (hoy - fecha_obj).days

    if edad_dias < 0:
        return False, "La fecha de nacimiento no puede ser futura."

    if edad_dias > limite_dias:
        return (
            False,
            f"El tipo de identificación NEO es solo para recién nacidos "
            f"(hasta {limite_dias} días de nacido). "
            f"El paciente tiene {edad_dias} días. Use otro tipo de identificación.",
        )

    return True, ""


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
            return (
                False,
                f"No se pueden asignar turnos en feriados: {feriado.descripcion}",
                0,
            )

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
        tipo_iden: str = "DNI",
        telefono: str = "",
        email: str = "",
        observaciones_paciente: str = "",
        medico_nombre: str = "",
        institucion_nombre: str = "",
        nota_interna: str = "",
        determinaciones: str = "",
        usuario: Any = None,
        orden_pk: Optional[int] = None,
        ordenes_pks: Optional[List[int]] = None,
    ) -> Tuple[bool, Optional[Turno], str]:
        """
        Crea un nuevo turno con validaciones.

        Puede vincular una sola orden (orden_pk) o múltiples órdenes unificadas
        (ordenes_pks). En ambos casos actualiza estado de las órdenes a 'TURNO'
        y sincroniza la relación M2M turno.ordenes.

        Returns:
            Tupla (exito, turno, mensaje_error)
        """
        try:
            with transaction.atomic():
                # Validar disponibilidad con lock
                es_valido, mensaje, _ = TurnoService.validar_disponibilidad(
                    fecha, agenda
                )
                if not es_valido:
                    return False, None, mensaje

                # ── Lógica especial para tipo NEO (recién nacidos) ──────────
                if tipo_iden == "NEO":
                    es_valido_edad, mensaje_edad = validar_edad_neo(fecha_nacimiento)
                    if not es_valido_edad:
                        return False, None, mensaje_edad
                    # El número se genera siempre server-side; ignorar lo que venga del frontend
                    dni = generar_numero_neo_unico(nombre, apellido, fecha_nacimiento)

                # Obtener o crear paciente
                paciente_obj, _ = Paciente.objects.update_or_create(
                    tipo_iden=tipo_iden,
                    iden=dni,
                    defaults={
                        "nombre": nombre,
                        "apellido": apellido,
                        "fecha_nacimiento": fecha_nacimiento,
                        "sexo": sexo,
                        "telefono": telefono or "",
                        "email": email or "",
                        "observaciones": observaciones_paciente or "",
                    },
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

                # Obtener institución si se especificó
                institucion_obj = None
                if institucion_nombre:
                    institucion_obj, _ = Institucion.objects.get_or_create(
                        nombre__iexact=institucion_nombre,
                        defaults={"nombre": institucion_nombre},
                    )

                # Crear turno
                turno = Turno.objects.create(
                    fecha=fecha,
                    agenda=agenda,
                    dni=paciente_obj,
                    medico=medico_obj,
                    institucion=institucion_obj,
                    nota_interna=nota_interna,
                    determinaciones=determinaciones,
                    usuario=usuario,
                )

                # ═══ VINCULACIÓN DE ÓRDENES ═══
                from ordenes.models import OrdenLaboratorio

                if ordenes_pks:
                    # ── MODO UNIFICACIÓN: múltiples órdenes ──
                    ordenes = OrdenLaboratorio.objects.filter(
                        pk__in=ordenes_pks,
                        paciente=paciente_obj,  # Seguridad: solo del mismo paciente
                        estado__in=["PENDIENTE", "INGRESADA"],
                    )

                    if ordenes.count() != len(ordenes_pks):
                        return (
                            False,
                            None,
                            "Algunas órdenes no están disponibles para vincular "
                            "(pueden haber sido asignadas a otro turno o no pertenecen al paciente).",
                        )

                    # Actualizar estado y FK de cada orden
                    for orden in ordenes:
                        orden.turno = turno
                        orden.estado = "TURNO"
                        orden.save(update_fields=["turno", "estado"])

                    # Sincronizar relación M2M
                    turno.ordenes.set(ordenes)

                elif orden_pk:
                    # ── MODO SIMPLE: una sola orden ──
                    try:
                        orden = OrdenLaboratorio.objects.get(
                            pk=orden_pk,
                            estado="PENDIENTE",  # Solo PENDIENTE (comportamiento original)
                        )
                        orden.turno = turno
                        orden.estado = "TURNO"
                        orden.save(update_fields=["turno", "estado"])

                        # Sincronizar relación M2M para consistencia
                        turno.ordenes.add(orden)

                    except OrdenLaboratorio.DoesNotExist:
                        pass  # Orden inexistente o ya no está pendiente → ignorar

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
        institucion_nombre: str = None,
        nota_interna: str = None,
        telefono: str = None,
        email: str = None,
        observaciones_paciente: str = None,
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

            # Actualizar institución
            if institucion_nombre is not None:
                if institucion_nombre:
                    turno.institucion, _ = Institucion.objects.get_or_create(
                        nombre__iexact=institucion_nombre,
                        defaults={"nombre": institucion_nombre},
                    )
                else:
                    turno.institucion = None

            turno.save()

            # Actualizar paciente si hay datos
            if turno.dni and any([telefono, email, observaciones_paciente]):
                if telefono is not None:
                    turno.dni.telefono = telefono or turno.dni.telefono
                if email is not None:
                    turno.dni.email = email or turno.dni.email
                if observaciones_paciente is not None:
                    turno.dni.observaciones = (
                        observaciones_paciente or turno.dni.observaciones
                    )
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
            "nombre": turno.dni.nombre,
            "apellido": turno.dni.apellido,
            "dni": turno.dni.iden,
            "fecha_nacimiento": turno.dni.fecha_nacimiento,
            "sexo": turno.dni.sexo,
            "telefono": turno.dni.telefono,
            "email": turno.dni.email,
            "observaciones": turno.dni.observaciones or "",
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

        return {"capacidad": capacidad, "usados": usados, "disponibles": disponibles}
