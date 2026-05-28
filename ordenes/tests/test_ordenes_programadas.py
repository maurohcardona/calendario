"""
Tests para el origen Órdenes Programadas.

Cubre:
- Modelo: campo fecha_programada, nuevo choice ORDENES_PROGRAMADAS
- Formulario: validaciones de fecha y servicio
- Vista: flujo GET/POST, recarga con servicio/fecha mantenidos
- Integración: creación de múltiples órdenes consecutivas
"""

import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from determinaciones.models import Determinacion, Sector
from medicos.models import Medico
from ordenes.forms import OrdenProgramadaForm
from ordenes.models import OrdenLaboratorio, Servicio
from pacientes.models import Paciente

User = get_user_model()


class OrdenProgramadaModelTestCase(TestCase):
    """Tests del modelo OrdenLaboratorio con origen ORDENES_PROGRAMADAS."""

    def setUp(self):
        """Configurar datos base."""
        self.medico = Medico.objects.create(nombre="Dr. Test", matricula="12345")
        self.paciente = Paciente.objects.create(
            iden="12345678",
            nombre="Juan",
            apellido="Perez",
            fecha_nacimiento=datetime.date(1980, 1, 1),
            sexo="Masculino",
        )
        self.servicio = Servicio.objects.create(
            origen="INTERNACION",
            nombre="Clínica Médica",
            activo=True,
        )

    def test_origen_ordenes_programadas_valido(self):
        """El choice ORDENES_PROGRAMADAS debe existir en TIPO_ORIGEN_CHOICES."""
        choices_values = [c[0] for c in OrdenLaboratorio.TIPO_ORIGEN_CHOICES]
        self.assertIn("ORDENES_PROGRAMADAS", choices_values)

    def test_crear_orden_programada_con_fecha(self):
        """Debe poder crearse una orden programada con fecha_programada."""
        fecha = datetime.date.today() + datetime.timedelta(days=1)
        orden = OrdenLaboratorio.objects.create(
            paciente=self.paciente,
            medico=self.medico,
            tipo_origen="ORDENES_PROGRAMADAS",
            servicio=self.servicio,
            fecha_programada=fecha,
            estado="PENDIENTE",
        )
        self.assertEqual(orden.tipo_origen, "ORDENES_PROGRAMADAS")
        self.assertEqual(orden.fecha_programada, fecha)
        self.assertEqual(orden.estado, "PENDIENTE")

    def test_fecha_programada_nullable(self):
        """El campo fecha_programada puede ser nulo para otros orígenes."""
        orden = OrdenLaboratorio.objects.create(
            paciente=self.paciente,
            medico=self.medico,
            tipo_origen="AMBULATORIO",
            estado="PENDIENTE",
        )
        self.assertIsNone(orden.fecha_programada)


class OrdenProgramadaFormTestCase(TestCase):
    """Tests del formulario OrdenProgramadaForm."""

    def setUp(self):
        """Crear servicios y determinaciones de prueba."""
        self.servicio_internacion = Servicio.objects.create(
            origen="INTERNACION",
            nombre="Clínica Médica",
            activo=True,
        )
        self.servicio_guardia = Servicio.objects.create(
            origen="GUARDIA",
            nombre="Guardia Central",
            activo=True,
        )
        self.servicio_ambulatorio = Servicio.objects.create(
            origen="AMBULATORIO",
            nombre="Consultorio Externo",
            activo=True,
        )
        self.sector = Sector.objects.create(nombre="Química")
        self.determinacion = Determinacion.objects.create(
            nombre="Glucemia",
            activa=True,
            visible=True,
            sector=self.sector,
        )

    def _form_data_valido(self, **kwargs):
        """Retornar datos válidos para el formulario."""
        data = {
            "servicio": self.servicio_internacion.pk,
            "sala": "Cama 5 - Sala C",
            "fecha_programada": (datetime.date.today() + datetime.timedelta(days=1)).isoformat(),
            "observaciones": "Diabetes tipo 2",
            "determinaciones": [self.determinacion.pk],
        }
        data.update(kwargs)
        return data

    def test_formulario_valido(self):
        """Datos correctos deben producir un formulario válido."""
        form = OrdenProgramadaForm(data=self._form_data_valido())
        self.assertTrue(form.is_valid(), form.errors)

    def test_fecha_hoy_valida(self):
        """La fecha de hoy debe ser aceptada (opción A: mínimo = hoy)."""
        data = self._form_data_valido(
            fecha_programada=datetime.date.today().isoformat()
        )
        form = OrdenProgramadaForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)

    def test_fecha_pasada_invalida(self):
        """Una fecha anterior a hoy debe rechazarse con error de validación."""
        ayer = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        form = OrdenProgramadaForm(data=self._form_data_valido(fecha_programada=ayer))
        self.assertFalse(form.is_valid())
        self.assertIn("fecha_programada", form.errors)

    def test_sin_determinaciones_invalido(self):
        """El formulario debe requerir al menos una determinación."""
        data = self._form_data_valido()
        data.pop("determinaciones")
        form = OrdenProgramadaForm(data=data)
        self.assertFalse(form.is_valid())

    def test_queryset_servicio_excluye_ambulatorio(self):
        """El queryset de servicio NO debe incluir servicios ambulatorios."""
        form = OrdenProgramadaForm()
        qs = form.fields["servicio"].queryset
        origenes = list(qs.values_list("origen", flat=True))
        self.assertNotIn("AMBULATORIO", origenes)

    def test_queryset_servicio_incluye_internacion(self):
        """El queryset de servicio debe incluir servicios de internación."""
        form = OrdenProgramadaForm()
        qs = form.fields["servicio"].queryset
        self.assertIn(self.servicio_internacion, qs)

    def test_queryset_servicio_incluye_guardia(self):
        """El queryset de servicio debe incluir servicios de guardia."""
        form = OrdenProgramadaForm()
        qs = form.fields["servicio"].queryset
        self.assertIn(self.servicio_guardia, qs)


class OrdenProgramadaVistaTestCase(TestCase):
    """Tests de la vista crear_orden_programada."""

    def setUp(self):
        """Configurar usuario médico autenticado y datos base."""
        self.user = User.objects.create_user(
            username="medico_test", password="testpass123"
        )
        self.medico = Medico.objects.create(
            nombre="Dr. Test", matricula="99999", usuario=self.user
        )
        self.client.login(username="medico_test", password="testpass123")

        self.servicio = Servicio.objects.create(
            origen="INTERNACION",
            nombre="Clínica Médica",
            activo=True,
        )
        self.sector = Sector.objects.create(nombre="Química")
        self.determinacion = Determinacion.objects.create(
            nombre="Glucemia",
            activa=True,
            visible=True,
            sector=self.sector,
        )
        self.paciente = Paciente.objects.create(
            iden="99887766",
            nombre="Maria",
            apellido="Lopez",
            fecha_nacimiento=datetime.date(1985, 6, 15),
            sexo="Femenino",
        )
        self.url = reverse("ordenes:crear_orden_programada")

    def _post_data_valido(self, **kwargs):
        """Retornar datos POST válidos para crear una orden programada."""
        data = {
            "paciente_id": self.paciente.pk,
            "servicio": self.servicio.pk,
            "sala": "Cama 3",
            "fecha_programada": (datetime.date.today() + datetime.timedelta(days=1)).isoformat(),
            "observaciones": "Diagnóstico de prueba",
            "determinaciones": [self.determinacion.pk],
        }
        data.update(kwargs)
        return data

    def test_get_requiere_medico(self):
        """Un usuario sin médico asociado debe ser rechazado."""
        user_sin_medico = User.objects.create_user(
            username="sin_medico", password="pass123"
        )
        self.client.login(username="sin_medico", password="pass123")
        response = self.client.get(self.url)
        self.assertNotEqual(response.status_code, 200)

    def test_get_formulario_vacio(self):
        """GET sin parámetros debe devolver el formulario limpio con status 200."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nueva Orden Programada")
        self.assertFalse(response.context["es_recarga"])

    def test_get_con_parametros_es_recarga(self):
        """GET con servicio_id y fecha marca es_recarga=True."""
        fecha = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
        response = self.client.get(
            self.url,
            {"servicio_id": self.servicio.pk, "fecha_programada": fecha},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["es_recarga"])

    def test_post_crear_orden_exitoso(self):
        """POST válido debe crear una OrdenLaboratorio con tipo_origen correcto."""
        ordenes_antes = OrdenLaboratorio.objects.count()
        response = self.client.post(self.url, self._post_data_valido())
        self.assertEqual(OrdenLaboratorio.objects.count(), ordenes_antes + 1)

        orden = OrdenLaboratorio.objects.latest("fecha_creacion")
        self.assertEqual(orden.tipo_origen, "ORDENES_PROGRAMADAS")
        self.assertEqual(orden.estado, "PENDIENTE")
        self.assertEqual(orden.servicio, self.servicio)
        self.assertEqual(orden.paciente, self.paciente)

    def test_post_redirect_mantiene_servicio_y_fecha(self):
        """Después de crear, el redirect debe incluir servicio_id y fecha_programada en la URL."""
        fecha = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
        response = self.client.post(self.url, self._post_data_valido(fecha_programada=fecha))
        self.assertEqual(response.status_code, 302)
        location = response["Location"]
        self.assertIn(f"servicio_id={self.servicio.pk}", location)
        self.assertIn(f"fecha_programada={fecha}", location)

    def test_post_sin_paciente_no_crea_orden(self):
        """POST sin paciente_id ni datos de paciente nuevo no debe crear la orden."""
        data = self._post_data_valido()
        data.pop("paciente_id")
        ordenes_antes = OrdenLaboratorio.objects.count()
        self.client.post(self.url, data)
        self.assertEqual(OrdenLaboratorio.objects.count(), ordenes_antes)

    def test_post_fecha_pasada_no_crea_orden(self):
        """POST con fecha anterior a hoy no debe crear la orden."""
        ayer = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        ordenes_antes = OrdenLaboratorio.objects.count()
        self.client.post(self.url, self._post_data_valido(fecha_programada=ayer))
        self.assertEqual(OrdenLaboratorio.objects.count(), ordenes_antes)

    def test_post_mensaje_exito_incluye_numero_orden(self):
        """El mensaje de éxito debe incluir el número de la orden creada."""
        response = self.client.post(
            self.url, self._post_data_valido(), follow=True
        )
        # Seguir el redirect para obtener los mensajes
        messages_list = list(response.context["messages"])
        self.assertTrue(
            any("LAB-" in str(m) for m in messages_list),
            "El mensaje de éxito debe contener el número LAB-XXXXXX",
        )


class OrdenProgramadaFlujoIntegracionTestCase(TestCase):
    """Tests de integración: creación de múltiples órdenes consecutivas."""

    def setUp(self):
        """Configurar datos para flujo completo."""
        self.user = User.objects.create_user(
            username="medico_integracion", password="testpass123"
        )
        self.medico = Medico.objects.create(
            nombre="Dr. Integracion", matricula="55555", usuario=self.user
        )
        self.client.login(username="medico_integracion", password="testpass123")

        self.servicio = Servicio.objects.create(
            origen="INTERNACION",
            nombre="Clínica Médica",
            activo=True,
        )
        self.sector = Sector.objects.create(nombre="Química")
        self.det = Determinacion.objects.create(
            nombre="Glucemia", activa=True, visible=True, sector=self.sector
        )

        # Tres pacientes distintos para el flujo
        self.pacientes = []
        for i in range(3):
            p = Paciente.objects.create(
                iden=f"1111111{i}",
                nombre=f"Paciente{i}",
                apellido="Test",
                fecha_nacimiento=datetime.date(1990, 1, 1),
                sexo="Masculino",
            )
            self.pacientes.append(p)

        self.url = reverse("ordenes:crear_orden_programada")
        self.fecha = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()

    def test_flujo_crear_tres_ordenes_consecutivas(self):
        """
        Simular la creación de 3 órdenes consecutivas.

        Verificar que:
        1. Cada orden tiene el mismo servicio y fecha
        2. El redirect incluye servicio_id y fecha en la URL
        3. Las 3 órdenes son independientes con distinto paciente
        """
        for i, paciente in enumerate(self.pacientes):
            response = self.client.post(self.url, {
                "paciente_id": paciente.pk,
                "servicio": self.servicio.pk,
                "sala": f"Cama {i + 1}",
                "fecha_programada": self.fecha,
                "observaciones": f"Diagnóstico paciente {i}",
                "determinaciones": [self.det.pk],
            })
            # Debe redirigir con servicio y fecha
            self.assertEqual(response.status_code, 302, f"Fallo en orden {i + 1}")
            location = response["Location"]
            self.assertIn(f"servicio_id={self.servicio.pk}", location)
            self.assertIn(f"fecha_programada={self.fecha}", location)

        # Las 3 órdenes deben existir con mismo servicio y fecha
        ordenes = OrdenLaboratorio.objects.filter(
            tipo_origen="ORDENES_PROGRAMADAS"
        ).order_by("pk")
        self.assertEqual(ordenes.count(), 3)

        for orden in ordenes:
            self.assertEqual(orden.servicio, self.servicio)
            self.assertEqual(str(orden.fecha_programada), self.fecha)
            self.assertEqual(orden.tipo_origen, "ORDENES_PROGRAMADAS")
            self.assertEqual(orden.estado, "PENDIENTE")
            self.assertEqual(orden.medico, self.medico)

        # Cada orden debe tener distinto paciente
        paciente_pks = list(ordenes.values_list("paciente_id", flat=True))
        self.assertEqual(len(set(paciente_pks)), 3, "Las 3 órdenes deben tener pacientes distintos")
