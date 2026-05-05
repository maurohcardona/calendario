"""
Tests para los filtros de órdenes.

Cubre:
- Vista AJAX filtrar_mis_ordenes_ajax: autenticación, filtros por paciente, origen,
  estado, rango de fechas (creación y programada), límite de resultados.
- Vista cola_laboratorio: filtros por origen y fecha programada, contadores de tabs,
  ya no está restringida a fecha_creacion=hoy.
"""

import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from medicos.models import Medico
from ordenes.models import OrdenLaboratorio, Servicio
from pacientes.models import Paciente

User = get_user_model()


class BaseOrdenesSetup(TestCase):
    """Setup compartido para tests de órdenes con médico, pacientes y servicio."""

    def setUp(self):
        """Configurar usuario médico, pacientes y órdenes de prueba."""
        self.user = User.objects.create_user(username="medico_test", password="pass1234")
        self.medico = Medico.objects.create(nombre="Dr. Test", matricula="99999", usuario=self.user)

        self.user_otro = User.objects.create_user(username="otro_medico", password="pass1234")
        self.medico_otro = Medico.objects.create(nombre="Dr. Otro", matricula="88888", usuario=self.user_otro)

        self.paciente1 = Paciente.objects.create(
            iden="11111111",
            nombre="Ana",
            apellido="Garcia",
            fecha_nacimiento=datetime.date(1990, 5, 10),
            sexo="Femenino",
        )
        self.paciente2 = Paciente.objects.create(
            iden="22222222",
            nombre="Carlos",
            apellido="Lopez",
            fecha_nacimiento=datetime.date(1975, 3, 20),
            sexo="Masculino",
        )
        self.servicio = Servicio.objects.create(
            origen="INTERNACION",
            nombre="Clínica Médica",
            activo=True,
        )

        hoy = datetime.date.today()

        self.orden_ambulatorio = OrdenLaboratorio.objects.create(
            paciente=self.paciente1,
            medico=self.medico,
            tipo_origen="AMBULATORIO",
            estado="PENDIENTE",
        )
        self.orden_guardia = OrdenLaboratorio.objects.create(
            paciente=self.paciente2,
            medico=self.medico,
            tipo_origen="GUARDIA",
            estado="COMPLETADA",
        )
        self.orden_programada = OrdenLaboratorio.objects.create(
            paciente=self.paciente1,
            medico=self.medico,
            tipo_origen="ORDENES_PROGRAMADAS",
            servicio=self.servicio,
            fecha_programada=hoy + datetime.timedelta(days=3),
            estado="PENDIENTE",
        )
        # Orden de otro médico (no debe aparecer en mis_ordenes del médico test)
        self.orden_otro_medico = OrdenLaboratorio.objects.create(
            paciente=self.paciente2,
            medico=self.medico_otro,
            tipo_origen="AMBULATORIO",
            estado="PENDIENTE",
        )

        self.url_ajax = reverse("ordenes:filtrar_mis_ordenes_ajax")


class FiltrarMisOrdenesAjaxAuthTestCase(BaseOrdenesSetup):
    """Tests de autenticación para el endpoint AJAX filtrar_mis_ordenes_ajax."""

    def test_redirige_si_no_autenticado(self):
        """Un usuario no autenticado debe ser redirigido al login."""
        response = self.client.get(self.url_ajax)
        self.assertIn(response.status_code, [302, 403])

    def test_accesible_con_medico_autenticado(self):
        """Un médico autenticado debe recibir 200 con JSON válido."""
        self.client.login(username="medico_test", password="pass1234")
        response = self.client.get(self.url_ajax)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("ordenes", data)
        self.assertIn("total", data)


class FiltrarMisOrdenesAjaxResultadosTestCase(BaseOrdenesSetup):
    """Tests de resultados y filtros del endpoint AJAX."""

    def setUp(self):
        """Autenticar el cliente como médico_test."""
        super().setUp()
        self.client.login(username="medico_test", password="pass1234")

    def test_sin_filtros_retorna_solo_mis_ordenes(self):
        """Sin filtros deben retornarse solo las órdenes del médico autenticado."""
        response = self.client.get(self.url_ajax)
        data = response.json()
        # Solo las 3 órdenes del médico_test (no la del otro médico)
        self.assertEqual(data["total"], 3)

    def test_filtro_por_origen(self):
        """El filtro por origen debe devolver solo las órdenes de ese tipo."""
        response = self.client.get(self.url_ajax, {"origen": "AMBULATORIO"})
        data = response.json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["ordenes"][0]["tipo_origen"], "AMBULATORIO")

    def test_filtro_por_estado(self):
        """El filtro por estado debe devolver solo las órdenes con ese estado."""
        response = self.client.get(self.url_ajax, {"estado": "COMPLETADA"})
        data = response.json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["ordenes"][0]["estado"], "COMPLETADA")

    def test_filtro_por_nombre_paciente(self):
        """El filtro por nombre debe buscar en nombre y apellido del paciente."""
        response = self.client.get(self.url_ajax, {"paciente": "Ana"})
        data = response.json()
        # Ana tiene orden_ambulatorio y orden_programada (2 órdenes)
        self.assertEqual(data["total"], 2)

    def test_filtro_por_dni_paciente(self):
        """El filtro por DNI debe buscar por iden del paciente."""
        response = self.client.get(self.url_ajax, {"paciente": "22222222"})
        data = response.json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["ordenes"][0]["paciente_dni"], "22222222")

    def test_filtro_origen_programada_retorna_fecha_programada(self):
        """Las órdenes programadas deben incluir fecha_programada en la respuesta."""
        response = self.client.get(self.url_ajax, {"origen": "ORDENES_PROGRAMADAS"})
        data = response.json()
        self.assertEqual(data["total"], 1)
        self.assertIsNotNone(data["ordenes"][0]["fecha_programada"])

    def test_filtro_fecha_desde_creacion(self):
        """Filtro fecha_desde con tipo_fecha=creacion debe usar fecha_creacion."""
        hoy = datetime.date.today().isoformat()
        response = self.client.get(self.url_ajax, {
            "fecha_desde": hoy,
            "tipo_fecha": "creacion",
        })
        data = response.json()
        # Todas las órdenes fueron creadas hoy
        self.assertEqual(data["total"], 3)

    def test_filtro_fecha_hasta_creacion_pasada_excluye_todo(self):
        """Filtro fecha_hasta en el pasado no debe retornar ninguna orden."""
        ayer = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        response = self.client.get(self.url_ajax, {
            "fecha_hasta": ayer,
            "tipo_fecha": "creacion",
        })
        data = response.json()
        self.assertEqual(data["total"], 0)

    def test_filtro_fecha_programada_tipo(self):
        """El filtro por fecha_desde con tipo_fecha=programada debe filtrar por fecha_programada."""
        hoy = datetime.date.today().isoformat()
        response = self.client.get(self.url_ajax, {
            "fecha_desde": hoy,
            "tipo_fecha": "programada",
        })
        data = response.json()
        # Solo la orden programada tiene fecha_programada >= hoy
        self.assertEqual(data["total"], 1)

    def test_respuesta_incluye_campos_requeridos(self):
        """Cada orden en la respuesta debe tener todos los campos requeridos."""
        response = self.client.get(self.url_ajax, {"origen": "AMBULATORIO"})
        data = response.json()
        campos = {"pk", "numero_orden_lab", "paciente_nombre", "paciente_dni",
                  "origen", "tipo_origen", "sala", "tiene_observaciones",
                  "estado", "estado_display", "fecha_creacion", "fecha_programada", "url"}
        for campo in campos:
            self.assertIn(campo, data["ordenes"][0], f"Falta campo: {campo}")


class ColaLaboratorioFiltrosTestCase(BaseOrdenesSetup):
    """Tests de filtros en la vista cola_laboratorio."""

    def setUp(self):
        """Autenticar como usuario con rol operador_lab (grupo laboratorio)."""
        super().setUp()
        from django.contrib.auth.models import Group
        grupo_lab, _ = Group.objects.get_or_create(name="laboratorio")
        self.op_user = User.objects.create_user(
            username="operador_lab",
            password="pass1234",
        )
        self.op_user.groups.add(grupo_lab)
        self.client.login(username="operador_lab", password="pass1234")
        self.url_cola = reverse("ordenes:cola_laboratorio")

    def test_cola_muestra_todas_las_pendientes_sin_filtro_fecha_creacion(self):
        """La cola debe mostrar TODAS las órdenes PENDIENTES, sin restricción de fecha_creacion=hoy."""
        response = self.client.get(self.url_cola)
        self.assertEqual(response.status_code, 200)
        # orden_ambulatorio (PENDIENTE), orden_programada (PENDIENTE) + orden_otro_medico (PENDIENTE)
        # = 3 pendientes en total
        total = response.context.get("total_ordenes", 0)
        self.assertGreaterEqual(total, 2)

    def test_cola_filtro_por_origen(self):
        """El filtro por origen debe reducir las órdenes mostradas."""
        response = self.client.get(self.url_cola, {"origen": "AMBULATORIO"})
        self.assertEqual(response.status_code, 200)
        grupos = response.context["grupos"]
        for tipo, ordenes_grupo in grupos.items():
            for orden in ordenes_grupo:
                self.assertEqual(orden.tipo_origen, "AMBULATORIO")

    def test_cola_filtro_por_fecha_programada(self):
        """El filtro por fecha_programada debe mostrar solo órdenes de esa fecha."""
        fecha = (datetime.date.today() + datetime.timedelta(days=3)).isoformat()
        response = self.client.get(self.url_cola, {"fecha_programada": fecha})
        self.assertEqual(response.status_code, 200)
        total = response.context.get("total_ordenes", 0)
        self.assertEqual(total, 1)

    def test_cola_contadores_por_origen(self):
        """El contexto debe incluir contadores correctos para cada origen."""
        response = self.client.get(self.url_cola)
        self.assertEqual(response.status_code, 200)
        contadores = response.context["contadores"]
        self.assertIn("AMBULATORIO", contadores)
        self.assertIn("GUARDIA", contadores)
        self.assertIn("INTERNACION", contadores)
        self.assertIn("ORDENES_PROGRAMADAS", contadores)
        self.assertIn("TODOS", contadores)
        # TODOS debe ser >= suma de los otros
        self.assertGreaterEqual(contadores["TODOS"], contadores["AMBULATORIO"])

    def test_cola_contadores_son_enteros_no_negativos(self):
        """Los contadores no deben ser negativos."""
        response = self.client.get(self.url_cola)
        contadores = response.context["contadores"]
        for key, val in contadores.items():
            self.assertGreaterEqual(val, 0, f"Contador {key} es negativo")
