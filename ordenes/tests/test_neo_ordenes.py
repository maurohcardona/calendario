"""
Tests para validación de NEO en el módulo de órdenes.

Cubre:
- PacienteInlineForm: validación de edad NEO, campo iden vacío permitido
- Vista buscar_paciente: búsqueda cross-tipo
- Vista crear_orden: generación automática de número NEO
- Vista crear_orden_programada: generación automática de número NEO
"""

import datetime

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from medicos.models import Medico
from ordenes.forms import PacienteInlineForm
from pacientes.models import Paciente

User = get_user_model()


def _crear_medico_y_usuario(username="medico_test_neo"):
    """Crea un usuario medico para las pruebas de vistas."""
    user = User.objects.create_user(username=username, password="test1234")
    medico = Medico.objects.create(
        usuario=user,
        nombre=f"Dr. Test {username}",
        matricula=f"M{username[-4:]}",
    )
    return user, medico


class PacienteInlineFormNEOTestCase(TestCase):
    """Tests unitarios del formulario PacienteInlineForm con tipo NEO."""

    def _form_data(self, **kwargs):
        """Datos base válidos para un paciente NEO recién nacido."""
        hoy = datetime.date.today()
        fecha_nac = (hoy - datetime.timedelta(days=5)).isoformat()
        base = {
            "tipo_iden": "NEO",
            "iden": "",  # vacío: se genera server-side
            "apellido": "GARCIA",
            "nombre": "JUAN",
            "fecha_nacimiento": fecha_nac,
            "sexo": "Masculino",
            "telefono": "",
            "email": "",
        }
        base.update(kwargs)
        return base

    def test_form_valido_neo_recien_nacido(self):
        """PacienteInlineForm es válido para NEO con fecha de nacimiento ≤ 90 días."""
        form = PacienteInlineForm(data=self._form_data())
        self.assertTrue(form.is_valid(), form.errors)

    def test_form_invalido_neo_mayor_90_dias(self):
        """PacienteInlineForm rechaza NEO con fecha de nacimiento > 90 días."""
        hoy = datetime.date.today()
        fecha_vieja = (hoy - datetime.timedelta(days=100)).isoformat()
        form = PacienteInlineForm(data=self._form_data(fecha_nacimiento=fecha_vieja))
        self.assertFalse(form.is_valid())
        self.assertIn("90 días", str(form.errors))

    def test_form_invalido_neo_sin_fecha_nacimiento(self):
        """PacienteInlineForm rechaza NEO sin fecha de nacimiento."""
        form = PacienteInlineForm(data=self._form_data(fecha_nacimiento=""))
        self.assertFalse(form.is_valid())
        self.assertIn("fecha de nacimiento", str(form.errors).lower())

    def test_form_valido_dni_sin_restriccion_edad(self):
        """PacienteInlineForm con DNI no valida restricción de edad NEO."""
        hoy = datetime.date.today()
        fecha_adulto = (hoy - datetime.timedelta(days=365 * 30)).isoformat()
        data = {
            "tipo_iden": "DNI",
            "iden": "12345678",
            "apellido": "PEREZ",
            "nombre": "MARIA",
            "fecha_nacimiento": fecha_adulto,
            "sexo": "Femenino",
            "telefono": "",
            "email": "",
        }
        form = PacienteInlineForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)

    def test_form_neo_iden_vacio_es_permitido(self):
        """PacienteInlineForm con NEO permite iden vacío (se genera server-side)."""
        form = PacienteInlineForm(data=self._form_data(iden=""))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data.get("iden"), "")


class BuscarPacienteViewCrossTipoTestCase(TestCase):
    """Tests del endpoint buscar_paciente con búsqueda cross-tipo."""

    def setUp(self):
        """Crear pacientes de distintos tipos y usuario médico para autenticación."""
        self.user, self.medico = _crear_medico_y_usuario("medico_buscar_neo")
        self.client = Client()
        self.client.login(username="medico_buscar_neo", password="test1234")
        self.url = reverse("ordenes:buscar_paciente")

        self.paciente_dni = Paciente.objects.create(
            tipo_iden="DNI",
            iden="99887766",
            apellido="LOPEZ",
            nombre="CARLOS",
            sexo="Masculino",
            fecha_nacimiento=datetime.date(1990, 5, 15),
        )
        self.paciente_neo = Paciente.objects.create(
            tipo_iden="NEO",
            iden="CALO01012024RN",
            apellido="ALVAREZ",
            nombre="CARLOS",
            sexo="Masculino",
            fecha_nacimiento=datetime.date.today() - datetime.timedelta(days=10),
        )

    def test_buscar_por_dni_encuentra_paciente(self):
        """Búsqueda cross-tipo encuentra paciente con tipo DNI."""
        resp = self.client.get(self.url, {"iden": "99887766"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["encontrado"])
        self.assertEqual(data["paciente"]["iden"], "99887766")
        self.assertEqual(data["paciente"]["tipo_iden"], "DNI")

    def test_buscar_por_neo_encuentra_paciente(self):
        """Búsqueda cross-tipo encuentra paciente con tipo NEO."""
        resp = self.client.get(self.url, {"iden": "CALO01012024RN"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["encontrado"])
        self.assertEqual(data["paciente"]["tipo_iden"], "NEO")

    def test_buscar_inexistente_retorna_no_encontrado(self):
        """Búsqueda de identificación inexistente retorna encontrado=False."""
        resp = self.client.get(self.url, {"iden": "00000000"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertFalse(data["encontrado"])

    def test_respuesta_incluye_tipo_iden(self):
        """La respuesta JSON incluye el campo tipo_iden para mostrar en frontend."""
        resp = self.client.get(self.url, {"iden": "99887766"})
        data = resp.json()
        self.assertIn("tipo_iden", data["paciente"])


class CrearOrdenConNEOTestCase(TestCase):
    """Tests de integración: crear_orden con paciente NEO nuevo."""

    def setUp(self):
        """Crear usuario médico y configurar cliente."""
        self.user, self.medico = _crear_medico_y_usuario("medico_neo_orden")
        self.client = Client()
        self.client.login(username="medico_neo_orden", password="test1234")
        self.url = reverse("ordenes:crear_orden")

    def test_crear_orden_neo_genera_numero_automatico(self):
        """Crear orden con paciente NEO genera número automáticamente (no se ingresa manualmente)."""
        hoy = datetime.date.today()
        fecha_nac = hoy - datetime.timedelta(days=3)

        # Verificar que no existe el paciente aún
        self.assertFalse(Paciente.objects.filter(tipo_iden="NEO").exists())

        # El POST simula el formulario con NEO seleccionado y DNI vacío
        # Nota: se necesita al menos una determinación para que la orden sea válida;
        # aquí verificamos que el paciente NEO se crea correctamente.
        from determinaciones.models import Determinacion
        det = Determinacion.objects.filter(activa=True, visible=True).first()
        if det is None:
            self.skipTest("No hay determinaciones activas configuradas")

        post_data = {
            "tipo_iden": "NEO",
            "iden": "",
            "apellido": "GONZALEZ",
            "nombre": "SOFIA",
            "fecha_nacimiento": fecha_nac.isoformat(),
            "sexo": "Femenino",
            "telefono": "",
            "email": "",
            "tipo_origen": "AMBULATORIO",
            f"determinaciones": [str(det.pk)],
        }
        resp = self.client.post(self.url, data=post_data, follow=True)

        # Verificar que se creó el paciente NEO
        paciente_neo = Paciente.objects.filter(tipo_iden="NEO").first()
        self.assertIsNotNone(paciente_neo, "Debe crearse un paciente NEO")
        self.assertTrue(
            paciente_neo.iden.startswith("SO"),
            f"Número NEO debe iniciar con SO (primeras 2 letras de Sofia): {paciente_neo.iden}"
        )
        self.assertTrue(paciente_neo.iden.endswith("RN"))


class CrearOrdenProgramadaConNEOTestCase(TestCase):
    """Tests de integración: crear_orden_programada con paciente NEO nuevo."""

    def setUp(self):
        """Crear usuario médico y configurar cliente."""
        self.user, self.medico = _crear_medico_y_usuario("medico_neo_prog")
        self.client = Client()
        self.client.login(username="medico_neo_prog", password="test1234")
        self.url = reverse("ordenes:crear_orden_programada")

    def test_crear_orden_programada_neo_genera_numero(self):
        """Crear orden programada con paciente NEO genera número automáticamente."""
        hoy = datetime.date.today()
        fecha_nac = hoy - datetime.timedelta(days=7)
        fecha_programada = hoy + datetime.timedelta(days=1)

        from determinaciones.models import Determinacion
        from ordenes.models import Servicio
        det = Determinacion.objects.filter(activa=True, visible=True).first()
        servicio = Servicio.objects.filter(activo=True).exclude(origen="AMBULATORIO").first()
        if not det or not servicio:
            self.skipTest("Faltan determinaciones o servicios no-ambulatorios activos")

        post_data = {
            "tipo_iden": "NEO",
            "iden": "",
            "apellido": "MARTINEZ",
            "nombre": "PEDRO",
            "fecha_nacimiento": fecha_nac.isoformat(),
            "sexo": "Masculino",
            "telefono": "",
            "email": "",
            "servicio": str(servicio.pk),
            "fecha_programada": fecha_programada.isoformat(),
            "sala": "Cama 1",
            "observaciones": "Test NEO",
            "determinaciones": [str(det.pk)],
        }
        self.client.post(self.url, data=post_data, follow=True)

        paciente_neo = Paciente.objects.filter(tipo_iden="NEO").first()
        self.assertIsNotNone(paciente_neo, "Debe crearse un paciente NEO en orden programada")
        self.assertTrue(paciente_neo.iden.endswith("RN"))
