from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from datetime import date, timedelta
from .models import Agenda, Cupo, Turno, WeeklyAvailability, Coordinados
from django.db import transaction, connection
import json


class AgendaModelTest(TestCase):
    """Tests para el modelo Agenda"""
    
    def setUp(self):
        self.agenda = Agenda.objects.create(
            name="Test Agenda",
            slug="test-agenda-001",
            color="#00d4ff"
        )
    
    def test_agenda_creation(self):
        """Test creación de agenda"""
        self.assertEqual(self.agenda.name, "Test Agenda")
        self.assertEqual(self.agenda.slug, "test-agenda-001")
        self.assertEqual(str(self.agenda), "Test Agenda")
    
    def test_agenda_color_default(self):
        """Test color por defecto"""
        agenda2 = Agenda.objects.create(name="Agenda 2", slug="test-agenda-002")
        self.assertEqual(agenda2.color, "#00d4ff")


class CupoModelTest(TestCase):
    """Tests para el modelo Cupo"""
    
    def setUp(self):
        self.agenda = Agenda.objects.create(
            name="Test Ambulatorio",
            slug="test-ambulatorio",
            color="#00d4ff"
        )
        self.fecha = date.today()
        self.cupo = Cupo.objects.create(
            agenda=self.agenda,
            fecha=self.fecha,
            cantidad_total=10
        )
    
    def test_cupo_creation(self):
        """Test creación de cupo"""
        self.assertEqual(self.cupo.cantidad_total, 10)
        self.assertEqual(self.cupo.agenda, self.agenda)
    
    def test_cupo_disponibles_sin_turnos(self):
        """Test disponibles sin turnos agendados"""
        self.assertEqual(self.cupo.disponibles(), 10)
    
    def test_cupo_disponibles_con_turnos(self):
        """Test disponibles con turnos agendados"""
        # Crear 3 turnos
        for i in range(3):
            Turno.objects.create(
                agenda=self.agenda,
                dni=f"1234567{i}",
                nombre=f"Paciente {i}",
                determinaciones="101,102",
                fecha=self.fecha
            )
        self.assertEqual(self.cupo.disponibles(), 7)
    
    def test_cupo_unique_constraint(self):
        """Test constraint único por agenda y fecha"""
        with self.assertRaises(Exception):
            Cupo.objects.create(
                agenda=self.agenda,
                fecha=self.fecha,
                cantidad_total=5
            )


class TurnoModelTest(TestCase):
    """Tests para el modelo Turno"""
    
    def setUp(self):
        self.agenda = Agenda.objects.create(
            name="Test Curvas",
            slug="test-curvas",
            color="#4caf50"
        )
        self.fecha = date.today() + timedelta(days=1)
        self.cupo = Cupo.objects.create(
            agenda=self.agenda,
            fecha=self.fecha,
            cantidad_total=5
        )
    
    def test_turno_creation(self):
        """Test creación de turno"""
        turno = Turno.objects.create(
            agenda=self.agenda,
            dni="12345678",
            nombre="Juan Pérez",
            determinaciones="101,102,103",
            fecha=self.fecha
        )
        self.assertEqual(turno.dni, "12345678")
        self.assertEqual(turno.nombre, "Juan Pérez")
    
    def test_turno_validation_excede_capacidad(self):
        """Test validación cuando se excede capacidad"""
        # Crear 5 turnos (llena cupo)
        for i in range(5):
            Turno.objects.create(
                agenda=self.agenda,
                dni=f"1234567{i}",
                nombre=f"Paciente {i}",
                determinaciones="101",
                fecha=self.fecha
            )
        
        # Intentar crear un sexto turno debe fallar
        turno = Turno(
            agenda=self.agenda,
            dni="99999999",
            nombre="Paciente Extra",
            determinaciones="101",
            fecha=self.fecha
        )
        with self.assertRaises(Exception):
            turno.full_clean()


class CupoViewsTest(TestCase):
    """Tests para vistas de cupos"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.superuser = User.objects.create_superuser(
            username='admin',
            password='admin123'
        )
        self.agenda = Agenda.objects.create(
            name="Test Agenda Views",
            slug="test-views",
            color="#00d4ff"
        )
    
    def test_generar_cupos_requires_login(self):
        """Test que generador de cupos requiere login"""
        response = self.client.get(reverse('turnos:generar_cupos_masivo'))
        self.assertEqual(response.status_code, 302)  # Redirect a login
    
    def test_generar_cupos_masivo_success(self):
        """Test generación masiva de cupos exitosa"""
        self.client.login(username='admin', password='admin123')
        
        desde = date.today()
        hasta = desde + timedelta(days=7)
        
        response = self.client.post(reverse('turnos:generar_cupos_masivo'), {
            'agenda': self.agenda.id,
            'desde_fecha': desde.strftime('%Y-%m-%d'),
            'hasta_fecha': hasta.strftime('%Y-%m-%d'),
            'cantidad': 10
        })
        
        # Debe redirigir después de crear
        self.assertEqual(response.status_code, 302)
        
        # Verificar que se crearon cupos (solo días hábiles)
        cupos_creados = Cupo.objects.filter(
            agenda=self.agenda,
            fecha__gte=desde,
            fecha__lte=hasta
        ).count()
        self.assertGreater(cupos_creados, 0)
    
    def test_generar_cupos_dia_especifico(self):
        """Test generación para día de semana específico"""
        self.client.login(username='admin', password='admin123')
        
        desde = date(2025, 12, 1)  # Lunes
        hasta = date(2025, 12, 31)
        
        response = self.client.post(reverse('turnos:generar_cupos_masivo'), {
            'agenda': self.agenda.id,
            'desde_fecha': desde.strftime('%Y-%m-%d'),
            'hasta_fecha': hasta.strftime('%Y-%m-%d'),
            'cantidad': 15,
            'por_dia_semana': 'on',
            'dia_semana': '2'  # Miércoles
        })
        
        self.assertEqual(response.status_code, 302)
        
        # Verificar que solo se crearon cupos para miércoles
        cupos = Cupo.objects.filter(
            agenda=self.agenda,
            fecha__gte=desde,
            fecha__lte=hasta
        )
        for cupo in cupos:
            self.assertEqual(cupo.fecha.weekday(), 2)  # Miércoles


class BorrarCuposTest(TestCase):
    """Tests para borrado de cupos"""
    
    def setUp(self):
        self.client = Client()
        self.superuser = User.objects.create_superuser(
            username='admin',
            password='admin123'
        )
        self.agenda = Agenda.objects.create(
            name="Test Emergencia",
            slug="test-emergencia",
            color="#f44336"
        )
        self.fecha = date.today() + timedelta(days=5)
        self.cupo = Cupo.objects.create(
            agenda=self.agenda,
            fecha=self.fecha,
            cantidad_total=10
        )
    
    def test_borrar_cupos_parcial(self):
        """Test borrado parcial de cupos"""
        self.client.login(username='admin', password='admin123')
        
        response = self.client.post(reverse('turnos:borrar_cupos_masivo'), {
            'agenda': self.agenda.id,
            'desde_fecha': self.fecha.strftime('%Y-%m-%d'),
            'hasta_fecha': self.fecha.strftime('%Y-%m-%d'),
            'cantidad_a_borrar': 3
        })
        
        self.assertEqual(response.status_code, 302)
        
        # Verificar que se redujo la cantidad
        cupo = Cupo.objects.get(id=self.cupo.id)
        self.assertEqual(cupo.cantidad_total, 7)
    
    def test_borrar_cupos_total(self):
        """Test borrado total de cupos"""
        self.client.login(username='admin', password='admin123')
        
        response = self.client.post(reverse('turnos:borrar_cupos_masivo'), {
            'agenda': self.agenda.id,
            'desde_fecha': self.fecha.strftime('%Y-%m-%d'),
            'hasta_fecha': self.fecha.strftime('%Y-%m-%d')
            # Sin cantidad_a_borrar = elimina todo
        })
        
        self.assertEqual(response.status_code, 302)
        
        # Verificar que se eliminó el cupo
        self.assertFalse(Cupo.objects.filter(id=self.cupo.id).exists())
    
    def test_borrar_cupos_mantiene_turnos(self):
        """Test que borrar cupos NO borra turnos"""
        # Crear turno
        turno = Turno.objects.create(
            agenda=self.agenda,
            dni="12345678",
            nombre="Paciente Test",
            determinaciones="101",
            fecha=self.fecha
        )
        
        self.client.login(username='admin', password='admin123')
        
        # Borrar cupo
        self.client.post(reverse('turnos:borrar_cupos_masivo'), {
            'agenda': self.agenda.id,
            'desde_fecha': self.fecha.strftime('%Y-%m-%d'),
            'hasta_fecha': self.fecha.strftime('%Y-%m-%d')
        })
        
        # Verificar que turno sigue existiendo
        self.assertTrue(Turno.objects.filter(id=turno.id).exists())


class CalendarioViewTest(TestCase):
    """Tests para vista de calendario"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.agenda = Agenda.objects.create(
            name="Test Calendario",
            slug="test-calendario",
            color="#00d4ff"
        )
    
    def test_calendario_requires_login(self):
        """Test que calendario requiere login"""
        response = self.client.get(reverse('turnos:calendario'))
        self.assertEqual(response.status_code, 302)
    
    def test_calendario_view_success(self):
        """Test vista de calendario exitosa"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('turnos:calendario'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'calendario')


class DiaViewTest(TestCase):
    """Tests para vista de día"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.agenda = Agenda.objects.create(
            name="Test Dia",
            slug="test-dia",
            color="#4caf50"
        )
        self.fecha = date.today() + timedelta(days=1)
        self.cupo = Cupo.objects.create(
            agenda=self.agenda,
            fecha=self.fecha,
            cantidad_total=5
        )
    
    def test_dia_view_todas_agendas(self):
        """Test vista día sin agenda específica"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(
            reverse('turnos:dia', args=[self.fecha.strftime('%Y-%m-%d')])
        )
        self.assertEqual(response.status_code, 200)
    
    def test_dia_view_agenda_especifica(self):
        """Test vista día con agenda específica"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(
            reverse('turnos:dia', args=[self.fecha.strftime('%Y-%m-%d')]),
            {'agenda': self.agenda.id}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Agendar turno')


class WeeklyAvailabilityTest(TestCase):
    """Tests para disponibilidad semanal"""
    
    def setUp(self):
        self.agenda = Agenda.objects.create(
            name="Test",
            slug="test",
            color="#00d4ff"
        )
    
    def test_weekly_availability_creation(self):
        """Test creación de disponibilidad semanal"""
        wa = WeeklyAvailability.objects.create(
            agenda=self.agenda,
            weekday=0,  # Lunes
            capacidad=20,
            active=True
        )
        self.assertEqual(wa.capacidad, 20)
        self.assertTrue(wa.active)
    
    def test_cupo_explicito_prevalece_sobre_weekly(self):
        """Test que cupo explícito tiene prioridad sobre weekly"""
        WeeklyAvailability.objects.create(
            agenda=self.agenda,
            weekday=0,
            capacidad=15,
            active=True
        )
        
        fecha_lunes = date(2025, 12, 8)
        # Crear cupo explícito con otra cantidad
        Cupo.objects.create(
            agenda=self.agenda,
            fecha=fecha_lunes,
            cantidad_total=25
        )
        
        capacidad = self.agenda.get_capacity_for_date(fecha_lunes)
        self.assertEqual(capacidad, 25)  # Debe usar cupo explícito


class IntegracionBaseDatosTest(TestCase):
    """Tests de integración con base de datos PostgreSQL"""
    
    @classmethod
    def setUpClass(cls):
        """Crear tablas externas una sola vez para todos los tests"""
        super().setUpClass()
        
        # Crear tablas externas en la base de datos de tests
        with connection.cursor() as cursor:
            # Tabla pacientes
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pacientes (
                    id SERIAL PRIMARY KEY,
                    dni VARCHAR(20) UNIQUE NOT NULL,
                    nombre VARCHAR(100) NOT NULL,
                    apellido VARCHAR(100) NOT NULL,
                    fecha_nacimiento DATE,
                    sexo VARCHAR(10),
                    observaciones TEXT,
                    creado TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Tabla determinaciones
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS determinaciones (
                    id SERIAL PRIMARY KEY,
                    codigo INTEGER UNIQUE NOT NULL,
                    nombre VARCHAR(200) NOT NULL,
                    descripcion TEXT,
                    creado TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Tabla perfiles
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS perfiles (
                    id SERIAL PRIMARY KEY,
                    codigo VARCHAR(50) UNIQUE NOT NULL,
                    nombre VARCHAR(200) NOT NULL,
                    determinaciones TEXT,
                    descripcion TEXT,
                    creado TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Insertar datos de prueba
            cursor.execute("""
                INSERT INTO pacientes (dni, nombre, apellido, fecha_nacimiento, sexo)
                VALUES ('12345678', 'Test', 'Paciente', '1990-01-01', 'M')
                ON CONFLICT (dni) DO NOTHING
            """)
            
            cursor.execute("""
                INSERT INTO determinaciones (codigo, nombre, descripcion)
                VALUES (101, 'Test Hemograma', 'Análisis de sangre completo')
                ON CONFLICT (codigo) DO NOTHING
            """)
    
    @classmethod
    def tearDownClass(cls):
        """Limpiar tablas externas después de todos los tests"""
        with connection.cursor() as cursor:
            cursor.execute("DROP TABLE IF EXISTS pacientes CASCADE")
            cursor.execute("DROP TABLE IF EXISTS determinaciones CASCADE")
            cursor.execute("DROP TABLE IF EXISTS perfiles CASCADE")
        
        super().tearDownClass()
    
    def test_conexion_postgresql(self):
        """Test que la conexión a PostgreSQL funciona"""
        cursor = connection.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        self.assertEqual(result[0], 1)
    
    def test_tablas_externas_existen(self):
        """Test que tablas externas (pacientes, determinaciones) existen"""
        with connection.cursor() as cursor:
            # Verificar tabla pacientes
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'pacientes'
                )
            """)
            self.assertTrue(cursor.fetchone()[0])
            
            # Verificar tabla determinaciones
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'determinaciones'
                )
            """)
            self.assertTrue(cursor.fetchone()[0])
            
            # Verificar que hay datos
            cursor.execute("SELECT COUNT(*) FROM pacientes")
            self.assertGreater(cursor.fetchone()[0], 0)
            
            cursor.execute("SELECT COUNT(*) FROM determinaciones")
            self.assertGreater(cursor.fetchone()[0], 0)


# Ejecutar con: python manage.py test turnos
