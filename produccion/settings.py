# /srv/escrutinio/backend/settings.py
import os
from pathlib import Path
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent

# === Integración con Adherentes ===
ADHERENTES_BASE_URL = os.getenv("ADHERENTES_BASE_URL", "http://adherentes_web:8000")
ADHERENTES_SYNC_TOKEN = os.getenv("ADHERENTES_SYNC_TOKEN", "cambia-este-secreto-largo")

# === Logs ===
# Podés setear LOG_DIR en el entorno; si no, usa /srv/escrutinio/logs o BASE_DIR/logs como fallback.
LOG_DIR = os.getenv('LOG_DIR', '/srv/escrutinio/logs')
try:
    os.makedirs(LOG_DIR, exist_ok=True)
except Exception:
    # Si no se puede crear, usa un fallback seguro
    LOG_DIR = str(BASE_DIR / 'logs')
    os.makedirs(LOG_DIR, exist_ok=True)


# === Seguridad / entorno ===
SECRET_KEY = os.getenv('SECRET_KEY', 'changeme-in-env')   # ponelo en .env
DEBUG = os.getenv('DEBUG', '0') in ('1', 'true', 'True', 'yes', 'on')

def _split_csv(s):
    return [h.strip() for h in s.split(',')] if s else []

# Agrega tu IP/host del VPS
ALLOWED_HOSTS = _split_csv(os.getenv('ALLOWED_HOSTS', '149.50.147.161,localhost,127.0.0.1'))
CSRF_TRUSTED_ORIGINS = _split_csv(
    os.getenv('CSRF_TRUSTED_ORIGINS', 'http://149.50.147.161')
)


AUTH_USER_MODEL = 'elecciones.User'

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',     # <- necesario
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'elecciones',
    'rest_framework',
    'rest_framework_simplejwt',
    'api',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # 'whitenoise.middleware.WhiteNoiseMiddleware',  # opcional si servís estáticos
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',

    # NEW: presencia de usuarios
    "elecciones.middleware.LastSeenMiddleware",
    "elecciones.middleware.TimingMiddleware",   # 👈 NUEVO
    "elecciones.middleware.AuditMiddleware",    # 👈 después del timing

    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',

    # Tu auditoría (paths sensibles)
    "elecciones.middleware.AuditMiddleware",
]


ROOT_URLCONF = 'backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],  # o [] si no usás carpeta global
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

WSGI_APPLICATION = 'backend.wsgi.application'

# === Base de datos ===
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.getenv('MYSQL_DATABASE', 'escrutinio'),
        'USER': os.getenv('MYSQL_USER', 'escrutinio_user'),
        'PASSWORD': os.getenv('MYSQL_PASSWORD', ''),
        'HOST': os.getenv('MYSQL_HOST', 'db'),
        'PORT': os.getenv('MYSQL_PORT', '3306'),
        'OPTIONS': {
            'charset': 'utf8mb4',
            'use_unicode': True,
        }
    }
}

# === i18n ===
LANGUAGE_CODE = 'es-ar'
TIME_ZONE = 'America/Argentina/Buenos_Aires'
USE_I18N = True
USE_TZ = True

# === Estáticos ===
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'        # << NECESARIO EN PRODUCCIÓN
STATICFILES_DIRS = [BASE_DIR / 'elecciones' / 'static']

# Si usás WhiteNoise:
# STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        # Si necesitás browsable API autenticada por sesión:
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=12),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
}

LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/panel_operador/'
LOGOUT_REDIRECT_URL = '/accounts/login/'

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "audit": {
            "format": "[{asctime}] {levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "app_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(LOG_DIR, "app.log"),
            "maxBytes": 5 * 1024 * 1024,  # 5MB
            "backupCount": 5,
            "encoding": "utf-8",
            "formatter": "verbose",
        },
        "audit_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(LOG_DIR, "audit.log"),
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 10,
            "encoding": "utf-8",
            "formatter": "audit",
        },
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "django": {"handlers": ["console", "app_file"], "level": "INFO"},
        "audit": {
            "handlers": ["audit_file", "console"],   # 👈 ahora también en consola
            "level": "INFO",
            "propagate": False
        },
        "app": {"handlers": ["app_file", "console"], "level": "INFO"},  # 👈 app también en consola
    },
}

