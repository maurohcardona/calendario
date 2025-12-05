from pathlib import Path

# Base del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent

# Configuración básica
SECRET_KEY = 'cambia-esto-por-una-secret-key'
DEBUG = True
import os

# ALLOWED_HOSTS: lee la variable de entorno ALLOWED_HOSTS como una lista separada por comas.
# Ejemplo: set ALLOWED_HOSTS=127.0.0.1,192.168.18.62
raw_allowed = os.getenv('ALLOWED_HOSTS', '')
if raw_allowed:
    ALLOWED_HOSTS = [h.strip() for h in raw_allowed.split(',') if h.strip()]
else:
    # Valores por defecto para desarrollo
    # Añadir la IP del servidor en la LAN para facilitar acceso desde otras máquinas
    ALLOWED_HOSTS = ['127.0.0.1', 'localhost', '192.168.18.62']

# Apps instaladas
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Tu app
    'turnos',
]

# Middleware
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
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
import os

# Database configuration via environment variables.
# Set DB_ENGINE to 'postgres' (or 'postgresql') to use PostgreSQL, otherwise falls back to SQLite.
DB_ENGINE = os.getenv('DB_ENGINE', 'postgresql')
if DB_ENGINE.startswith('postgres') or DB_ENGINE.startswith('postgresql'):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('DB_NAME', 'Laboratorio'),
            'USER': os.getenv('DB_USER', 'postgres'),
            'PASSWORD': os.getenv('DB_PASSWORD', 'estufa10'),
            'HOST': os.getenv('DB_HOST', 'localhost'),
            'PORT': os.getenv('DB_PORT', '5432'),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
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
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / "static"]  # Carpeta /static/ en el proyecto

# Archivos subidos (si los usás)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Directorio donde se colocarán los archivos estáticos cuando se ejecute
# `python manage.py collectstatic`. Usar en despliegue (Nginx/servir estáticos).
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Default primary key type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Redirigir al login después del logout
LOGOUT_REDIRECT_URL = '/accounts/login/'
# Redirigir al calendario después del login por defecto
LOGIN_REDIRECT_URL = '/turnos/calendario/'
