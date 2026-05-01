"""
Tests para el layout separado de médicos y bloqueo de acceso al admin.

Cubre:
- Bloqueo del admin para usuarios con médico asociado
- Acceso correcto al admin para superusuarios y usuarios sin médico
- Acceso de médicos a sus vistas de órdenes
- Bloqueo de vistas de médico para usuarios sin médico
- Redirección post-login según tipo de usuario
- Elementos visuales del template base_medico.html
"""
from django.contrib.auth.models import User
from django.test import Client, TestCase

from medicos.models import Medico
from ordenes.models import OrdenLaboratorio
from pacientes.models import Paciente


class MedicoLayoutTestCase(TestCase):
    """Tests para el layout separado de médicos y bloqueo de admin."""

    def setUp(self):
        """Crea usuarios de prueba: normal, médico y superusuario."""
        # Usuario normal sin médico
        self.user_normal = User.objects.create_user(
            username="normal_test",
            password="test1234",
        )

        # Usuario con médico asociado (is_staff para que Django no redirija a admin/login antes del middleware)
        self.user_medico = User.objects.create_user(
            username="medico_test",
            password="test1234",
            is_staff=True,
        )
        self.medico = Medico.objects.create(
            nombre="Dr. Juan Pérez",
            matricula="MAT-TEST-001",
            usuario=self.user_medico,
        )

        # Superusuario
        self.superuser = User.objects.create_superuser(
            username="admin_test",
            password="admin1234",
        )

        self.client = Client()

    # ---------------------------------------------------------------
    # Bloqueo del admin
    # ---------------------------------------------------------------

    def test_medico_bloqueado_en_admin(self):
        """Médico intenta acceder al admin → redirect a mis_ordenes."""
        self.client.login(username="medico_test", password="test1234")
        response = self.client.get("/admin/")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/ordenes/mis-ordenes/", response.url)

    def test_medico_bloqueado_en_subruta_admin(self):
        """Médico intenta acceder a una subruta del admin → redirect."""
        self.client.login(username="medico_test", password="test1234")
        response = self.client.get("/admin/auth/user/")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/ordenes/mis-ordenes/", response.url)

    def test_superuser_no_bloqueado_en_admin(self):
        """Superusuario SÍ puede acceder al admin sin bloqueo por middleware."""
        self.client.login(username="admin_test", password="admin1234")
        response = self.client.get("/admin/")

        # El admin puede redirigir a /admin/login/ o mostrar 200 — nunca a mis_ordenes
        if response.status_code == 302:
            self.assertNotIn("mis-ordenes", response.url)
        else:
            self.assertEqual(response.status_code, 200)

    def test_usuario_sin_medico_no_bloqueado_por_middleware(self):
        """Usuario sin médico no es interceptado por el middleware."""
        self.client.login(username="normal_test", password="test1234")
        response = self.client.get("/admin/")

        # Puede recibir redirect al login del admin, pero NO a mis_ordenes
        if response.status_code == 302:
            self.assertNotIn("mis-ordenes", response.url)

    # ---------------------------------------------------------------
    # Acceso a vistas de médico
    # ---------------------------------------------------------------

    def test_medico_accede_mis_ordenes(self):
        """Médico SÍ puede acceder a mis_ordenes."""
        self.client.login(username="medico_test", password="test1234")
        response = self.client.get("/ordenes/mis-ordenes/")

        self.assertEqual(response.status_code, 200)

    def test_medico_accede_todas_ordenes(self):
        """Médico SÍ puede acceder a todas_ordenes."""
        self.client.login(username="medico_test", password="test1234")
        response = self.client.get("/ordenes/todas/")

        self.assertEqual(response.status_code, 200)

    def test_usuario_sin_medico_bloqueado_en_mis_ordenes(self):
        """Usuario sin médico NO puede acceder a mis_ordenes → redirect al calendario."""
        self.client.login(username="normal_test", password="test1234")
        response = self.client.get("/ordenes/mis-ordenes/")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/turnos/calendario/", response.url)

    def test_usuario_sin_medico_bloqueado_en_todas_ordenes(self):
        """Usuario sin médico NO puede acceder a todas_ordenes → redirect al calendario."""
        self.client.login(username="normal_test", password="test1234")
        response = self.client.get("/ordenes/todas/")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/turnos/calendario/", response.url)

    def test_usuario_anonimo_bloqueado_en_mis_ordenes(self):
        """Usuario no autenticado NO puede acceder a mis_ordenes → redirect al login."""
        response = self.client.get("/ordenes/mis-ordenes/")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    # ---------------------------------------------------------------
    # Redirección post-login
    # ---------------------------------------------------------------

    def test_medico_post_login_redirige_a_mis_ordenes(self):
        """Médico después de login es redirigido a mis_ordenes."""
        response = self.client.post(
            "/accounts/login/",
            {"username": "medico_test", "password": "test1234"},
            follow=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("/ordenes/mis-ordenes/", response.url)

    def test_usuario_normal_post_login_no_redirige_a_mis_ordenes(self):
        """Usuario sin médico después de login NO va a mis_ordenes."""
        response = self.client.post(
            "/accounts/login/",
            {"username": "normal_test", "password": "test1234"},
            follow=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertNotIn("mis-ordenes", response.url)

    # ---------------------------------------------------------------
    # Template base_medico.html
    # ---------------------------------------------------------------

    def test_base_medico_muestra_nombre_medico(self):
        """El header de base_medico.html muestra el nombre del médico."""
        self.client.login(username="medico_test", password="test1234")
        response = self.client.get("/ordenes/mis-ordenes/")

        self.assertContains(response, "Dr. Juan Pérez")

    def test_base_medico_tiene_navegacion_completa(self):
        """El header tiene los tres enlaces de navegación."""
        self.client.login(username="medico_test", password="test1234")
        response = self.client.get("/ordenes/mis-ordenes/")

        self.assertContains(response, "Todas las órdenes")
        self.assertContains(response, "Mis órdenes")
        self.assertContains(response, "Nueva Orden")

    def test_base_medico_tiene_boton_logout(self):
        """El header tiene el botón de cerrar sesión."""
        self.client.login(username="medico_test", password="test1234")
        response = self.client.get("/ordenes/mis-ordenes/")

        self.assertContains(response, "Cerrar sesión")

    def test_mis_ordenes_solo_muestra_ordenes_del_medico(self):
        """mis_ordenes filtra y muestra solo las órdenes del médico autenticado."""
        # Crear otro médico
        otro_user = User.objects.create_user(username="otro_medico", password="test1234")
        otro_medico = Medico.objects.create(
            nombre="Dra. Ana García",
            matricula="MAT-TEST-002",
            usuario=otro_user,
        )

        # Crear paciente
        paciente = Paciente.objects.create(
            nombre="Test",
            apellido="Paciente",
            iden="99999999",
            fecha_nacimiento="1990-01-01",
        )

        # Crear orden del médico autenticado
        orden_mia = OrdenLaboratorio.objects.create(
            paciente=paciente,
            medico=self.medico,
            tipo_origen="AMBULATORIO",
        )

        # Crear orden del otro médico
        orden_ajena = OrdenLaboratorio.objects.create(
            paciente=paciente,
            medico=otro_medico,
            tipo_origen="AMBULATORIO",
        )

        self.client.login(username="medico_test", password="test1234")
        response = self.client.get("/ordenes/mis-ordenes/")

        ordenes_en_ctx = list(response.context["ordenes"])
        pks_en_ctx = [o.pk for o in ordenes_en_ctx]

        self.assertIn(orden_mia.pk, pks_en_ctx)
        self.assertNotIn(orden_ajena.pk, pks_en_ctx)
