from pathlib import Path

# Base del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent

# Configuración básica
SECRET_KEY = 'django-insecure-pq8xm2k9v5w7n4j3h6r8t1y9u0i2o5p7a9s1d3f5g7h9j2k4'
DEBUG = False
ALLOWED_HOSTS = ['*', 'localhost', '127.0.0.1']

# Apps instaladas
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Apps de terceros
    'auditlog',

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
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "Laboratorio",
        "USER": "postgres",
        "PASSWORD": "estufa10",
        "HOST": "localhost",
        "PORT": "5432",
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
