"""
Tests de integración: transiciones de estado entre OrdenLaboratorio y Turno.

Valida el flujo completo:
  PENDIENTE → (crear turno desde orden) → TURNO → (coordinar turno) → INGRESADA
"""

from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase

from medicos.models import Medico
from ordenes.models import OrdenLaboratorio
from pacientes.models import Paciente
from turnos.models import Agenda, Cupo
from turnos.services.turno_service import TurnoService

User = get_user_model()


class OrdenTurnoIntegrationTestCase(TestCase):
    """Tests para la integración entre órdenes de laboratorio y turnos."""

    def setUp(self):
        """Configurar datos de prueba comunes."""
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.medico = Medico.objects.create(nombre="Dr. Test", matricula="99999")
        self.paciente = Paciente.objects.create(
            iden="99887766",
            nombre="Maria",
            apellido="Lopez",
            fecha_nacimiento=date(1985, 6, 15),
            sexo="Femenino",
            telefono="",
        )
        self.agenda = Agenda.objects.create(
            name="Agenda Test", slug="agenda-test", color="#00d4ff"
        )
        self.fecha_futura = date.today() + timedelta(days=2)
        Cupo.objects.create(
            fecha=self.fecha_futura,
            agenda=self.agenda,
            cantidad_total=10,
            usuario="testuser",
        )
        self.orden = OrdenLaboratorio.objects.create(
            paciente=self.paciente,
            medico=self.medico,
            tipo_origen="AMBULATORIO",
            estado="PENDIENTE",
        )

    def _crear_turno(self, orden_pk=None):
        """Helper para crear un turno con los datos de setUp."""
        return TurnoService.crear_turno(
            fecha=self.fecha_futura,
            agenda=self.agenda,
            dni=self.paciente.iden,
            nombre=self.paciente.nombre,
            apellido=self.paciente.apellido,
            fecha_nacimiento=self.paciente.fecha_nacimiento,
            sexo=self.paciente.sexo,
            usuario=self.user,
            orden_pk=orden_pk,
        )

    def test_crear_turno_desde_orden_pendiente_vincula_y_cambia_estado(self):
        """Al crear turno con orden_pk, la orden pasa a TURNO y queda vinculada."""
        exito, turno, error = self._crear_turno(orden_pk=self.orden.pk)

        self.assertTrue(exito, f"Error inesperado: {error}")
        self.assertIsNotNone(turno)

        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, "TURNO")
        self.assertEqual(self.orden.turno, turno)

    def test_turno_orden_reverse_relation(self):
        """El turno creado permite acceder a la orden vía related_name='orden'."""
        exito, turno, _ = self._crear_turno(orden_pk=self.orden.pk)

        self.assertTrue(exito)
        # turno.orden es el RelatedManager (related_name="orden")
        self.assertEqual(turno.orden.count(), 1)
        self.assertEqual(turno.orden.first(), self.orden)

    def test_crear_turno_sin_orden_pk_no_falla(self):
        """Crear turno sin orden_pk funciona normalmente, sin vincular orden."""
        exito, turno, error = self._crear_turno(orden_pk=None)

        self.assertTrue(exito, f"Error inesperado: {error}")
        self.assertIsNotNone(turno)
        self.assertEqual(turno.orden.count(), 0)
        # La orden original sigue PENDIENTE
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, "PENDIENTE")

    def test_orden_inexistente_no_interrumpe_creacion_de_turno(self):
        """Si el orden_pk no existe, el turno se crea igualmente sin error."""
        exito, turno, error = self._crear_turno(orden_pk=999999)

        self.assertTrue(exito, f"Error inesperado: {error}")
        self.assertIsNotNone(turno)

    def test_orden_no_pendiente_no_se_vincula(self):
        """Si la orden ya no está en estado PENDIENTE, no se vincula al turno."""
        self.orden.estado = "INGRESADA"
        self.orden.save(update_fields=["estado"])

        exito, turno, error = self._crear_turno(orden_pk=self.orden.pk)

        self.assertTrue(exito, f"Error inesperado: {error}")
        # La orden no cambia de estado ni se vincula
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, "INGRESADA")
        self.assertIsNone(self.orden.turno)

    def test_estado_turno_display(self):
        """El estado TURNO tiene el display correcto en ESTADO_CHOICES."""
        self.orden.estado = "TURNO"
        self.orden.save(update_fields=["estado"])
        self.orden.refresh_from_db()

        self.assertEqual(self.orden.get_estado_display(), "Turno Asignado")

    def test_puede_ingresar_con_estado_turno(self):
        """Una orden en estado TURNO puede ser ingresada."""
        self.orden.estado = "TURNO"
        self.orden.save(update_fields=["estado"])
        self.orden.refresh_from_db()

        self.assertTrue(self.orden.puede_ingresar)

    def test_puede_cancelar_con_estado_turno(self):
        """Una orden en estado TURNO puede ser cancelada."""
        self.orden.estado = "TURNO"
        self.orden.save(update_fields=["estado"])
        self.orden.refresh_from_db()

        self.assertTrue(self.orden.puede_cancelar)

    def test_puede_ingresar_con_estado_pendiente(self):
        """Una orden en estado PENDIENTE puede ser ingresada (comportamiento previo)."""
        self.assertTrue(self.orden.puede_ingresar)

    def test_puede_ingresar_con_estado_ingresada_es_false(self):
        """Una orden ya INGRESADA NO puede volver a ingresarse."""
        self.orden.estado = "INGRESADA"
        self.orden.save(update_fields=["estado"])
        self.orden.refresh_from_db()

        self.assertFalse(self.orden.puede_ingresar)
