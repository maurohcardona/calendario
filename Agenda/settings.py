import os
from pathlib import Path
from dotenv import load_dotenv
from dotenv import find_dotenv

# Base del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent


# Cargar .env desde la carpeta calendario
load_dotenv(find_dotenv(filename='.env', raise_error_if_not_found=False) or 'calendario/.env')

# Configuración básica
SECRET_KEY = os.getenv('SECRET_KEY')
DEBUG = os.getenv('DEBUG')
ALLOWED_HOSTS = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "").split(",") if h.strip()]
# Apps instaladas
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.postgres',
    'pacientes',
    'determinaciones',
   
    # Apps de terceros
    'auditlog',
    'whitenoise.runserver_nostatic',
    'dotenv',

    # Tu app
    'turnos',
]

# Middleware
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'auditlog.middleware.AuditlogMiddleware',  # Registra el usuario en cada cambio
]

ROOT_URLCONF = 'Agenda.urls'

# Templates
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / "templates"],  # opcional si usás carpeta templates/
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'Agenda.wsgi.application'

# Base de datos
DATABASES = {
    "default": {
        "ENGINE": os.getenv('DB_ENGINE'),
        "NAME": os.getenv('DB_NAME'),
        "USER": os.getenv('DB_USER'),
        "PASSWORD": os.getenv('DB_PASSWORD'),
        "HOST": os.getenv('DB_HOST'),
        "PORT": os.getenv('DB_PORT'),
    }
}

# Contraseñas
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internacionalización
LANGUAGE_CODE = 'es-ar'
TIME_ZONE = 'America/Argentina/Buenos_Aires'
USE_I18N = True
USE_TZ = True

# Archivos estáticos (CSS, JS, imágenes)
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / "static"]  # Carpeta /static/ en el proyecto
STATIC_ROOT = BASE_DIR / 'staticfiles_collected'  # Para producción

# WhiteNoise (storage SIN manifest)
STATICFILES_STORAGE = "whitenoise.storage.CompressedStaticFilesStorage"

# Archivos subidos (si los usás)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Configuración de autenticación
LOGIN_REDIRECT_URL = '/turnos/calendario/'
LOGIN_URL = '/accounts/login/'
LOGOUT_REDIRECT_URL = '/accounts/login/'

# Configuración de sesiones
SESSION_COOKIE_AGE = 1800  # 30 minutos de inactividad (en segundos)
SESSION_SAVE_EVERY_REQUEST = True  # Actualiza la expiración con cada petición
SESSION_EXPIRE_AT_BROWSER_CLOSE = True  # Cierra sesión al cerrar el navegador

# Configuración de Auditlog
AUDITLOG_LOGENTRY_MODEL = 'auditlog.LogEntry'
