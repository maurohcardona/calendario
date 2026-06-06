import os
from pathlib import Path
from dotenv import load_dotenv
from dotenv import find_dotenv

# Base del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent


# Cargar .env desde la carpeta calendario
load_dotenv(
    find_dotenv(filename=".env", raise_error_if_not_found=False) or "calendario/.env"
)

# Configuración básica
SECRET_KEY = os.getenv("SECRET_KEY")
DEBUG = os.getenv("DEBUG")
ALLOWED_HOSTS = [
    h.strip() for h in os.getenv("ALLOWED_HOSTS", "").split(",") if h.strip()
]
# Apps instaladas
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "pacientes",
    "determinaciones",
    "medicos",
    "informes",
    "instituciones",
    # "debug_toolbar",  # Desactivado
    # Apps de terceros
    "auditlog",
    "whitenoise.runserver_nostatic",
    "dotenv",
    # Tu app
    "turnos",
    "ordenes",
]

# Middleware
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "ordenes.middleware.BloquearAdminMedicosMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "auditlog.middleware.AuditlogMiddleware",  # Registra el usuario en cada cambio
    # "debug_toolbar.middleware.DebugToolbarMiddleware",  # Desactivado
]

ROOT_URLCONF = "Agenda.urls"

# Templates
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],  # opcional si usás carpeta templates/
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                # Context processors personalizados
                "turnos.context_processors.agendas_disponibles",
                "turnos.context_processors.fecha_actual",
                "turnos.context_processors.configuracion_sistema",
            ],
        },
    },
]

WSGI_APPLICATION = "Agenda.wsgi.application"

# INTERNAL_IPS = [
#     "127.0.0.1",
# ]

# Configuración de Django Debug Toolbar (Desactivado)
# DEBUG_TOOLBAR_CONFIG = {
#     'DISABLE_PANELS': {
#         'debug_toolbar.panels.profiling.ProfilingPanel',
#     },
#     'SHOW_TOOLBAR_CALLBACK': lambda request: DEBUG,
# }

# Base de datos
DATABASES = {
    "default": {
        "ENGINE": os.getenv("DB_ENGINE"),
        "NAME": os.getenv("DB_NAME"),
        "USER": os.getenv("DB_USER"),
        "PASSWORD": os.getenv("DB_PASSWORD"),
        "HOST": os.getenv("DB_HOST"),
        "PORT": os.getenv("DB_PORT"),
    }
}

# Contraseñas
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Internacionalización
LANGUAGE_CODE = "es-ar"
TIME_ZONE = "America/Argentina/Buenos_Aires"
USE_I18N = True
USE_TZ = True

# Archivos estáticos (CSS, JS, imágenes)
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]  # Carpeta /static/ en el proyecto
STATIC_ROOT = BASE_DIR / "staticfiles_collected"  # Para producción

# WhiteNoise (storage SIN manifest)
STATICFILES_STORAGE = "whitenoise.storage.CompressedStaticFilesStorage"

# WhiteNoise: MIME type correcto para manifest.json (PWA)
WHITENOISE_MIMETYPES = {
    ".json": "application/manifest+json",
}

# Archivos subidos (si los usás)
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Default primary key type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Configuración de autenticación
LOGIN_REDIRECT_URL = "/turnos/calendario/"
LOGIN_URL = "/accounts/login/"
LOGOUT_REDIRECT_URL = "/accounts/login/"

# Configuración de sesiones
SESSION_COOKIE_AGE = 1800  # 30 minutos de inactividad (en segundos)
SESSION_SAVE_EVERY_REQUEST = True  # Actualiza la expiración con cada petición
SESSION_EXPIRE_AT_BROWSER_CLOSE = True  # Cierra sesión al cerrar el navegador

# Configuración de Auditlog
AUDITLOG_LOGENTRY_MODEL = "auditlog.LogEntry"

# Configuración de Email
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("SMTP_PORT", 587))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.getenv("SENDER_EMAIL")
EMAIL_HOST_PASSWORD = os.getenv("SENDER_PASSWORD")
DEFAULT_FROM_EMAIL = os.getenv("SENDER_EMAIL")

# Carpeta de informes pendientes (puede estar en otra ubicación en producción)
INFORMES_PENDIENTES_DIR = os.getenv(
    "INFORMES_PENDIENTES_DIR", str(BASE_DIR / "informes" / "pendientes")
)

# Configuración de WhatsApp (Twilio)
# Crear cuenta gratuita en https://www.twilio.com y activar el Sandbox de WhatsApp
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
# Número de WhatsApp de Twilio (Sandbox: 'whatsapp:+14155238886' / Producción: el tuyo)
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
# Prefijo internacional para los números del paciente (Argentina móvil = +549)
WHATSAPP_CODIGO_PAIS = os.getenv("WHATSAPP_CODIGO_PAIS", "+549")

# ── Mensajería con el Laboratorio ─────────────────────────────────────────────
# USAR_HL7=True  → se generan archivos .hl7 (OML^O21) usando HL7Service
# USAR_HL7=False → comportamiento legacy ASTM (ASTMService)
USAR_HL7 = os.getenv("USAR_HL7", "True").lower() in ("true", "1", "yes")

# ── Configuración LIS (servidor MLLP) ─────────────────────────────────────────
# El LIS actúa como servidor TCP; Django se conecta como cliente para enviar
# mensajes OML^O21 y recibir ACK + ORU^R01 en la misma conexión.
#
# Variables de entorno disponibles en .env:
#   LIS_HOST              IP del LIS (default: 150.150.150.115)
#   LIS_PORT              Puerto TCP del LIS (default: 50000)
#   LIS_TIMEOUT_CONEXION  Segundos máx para abrir conexión TCP (default: 5)
#   LIS_TIMEOUT_ACK       Segundos máx esperando ACK tras enviar OML (default: 10)
#   LIS_TIMEOUT_ORU       Segundos listener post-ACK esperando ORU (default: 30)
#   LIS_MAX_REINTENTOS    Intentos antes de marcar error permanente (default: 3)
LIS_HOST = os.getenv("LIS_HOST", "150.150.150.115")
LIS_PORT = int(os.getenv("LIS_PORT", "50000"))
LIS_TIMEOUT_CONEXION = int(os.getenv("LIS_TIMEOUT_CONEXION", "5"))
LIS_TIMEOUT_ACK = int(os.getenv("LIS_TIMEOUT_ACK", "10"))
LIS_TIMEOUT_ORU = int(os.getenv("LIS_TIMEOUT_ORU", "60"))
LIS_MAX_REINTENTOS = int(os.getenv("LIS_MAX_REINTENTOS", "3"))

# ── Servidor MLLP (modo servidor — escucha conexiones entrantes del LIS) ───────
# El servidor MLLP escucha en este puerto para recibir mensajes HL7 del LIS
# directamente (ORU^R01, ORL^O22, etc.) sin necesidad de polling.
# Iniciar con: python manage.py iniciar_servidor_mllp
MLLP_SERVER_PORT = int(os.getenv("MLLP_SERVER_PORT", "50001"))

# ── Logging ────────────────────────────────────────────────────────────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "mllp": {
            "format": "[{levelname}] {asctime} {name} | {message}",
            "style": "{",
            "datefmt": "%H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "mllp",
        },
    },
    "loggers": {
        "turnos.services": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}

