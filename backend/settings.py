# /srv/escrutinio/backend/settings.py
import os
from pathlib import Path
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent

#AGREGAR AL PRODUCCION 29-8-----!!!!!!!

ADHERENTES_BASE_URL = os.getenv('ADHERENTES_BASE_URL', 'http://localhost:8001')  # ajustá host/puerto
ADHERENTES_SYNC_TOKEN = os.getenv('ADHERENTES_SYNC_TOKEN', 'cambia-este-secreto-largo')


# === Logs ===
LOG_DIR = BASE_DIR / "logs"
try:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    # En entornos sin permisos, seguimos sin romper el arranque
    pass


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
    'api', # <- AGREGAR PRODUCCION
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # opcional si servís estáticos
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',

    # NEW: presencia de usuarios
    "elecciones.middleware.LastSeenMiddleware",

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
        'CONN_MAX_AGE': 60,
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
STATICFILES_DIRS = [BASE_DIR / 'elecciones' / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'   # ← agrega esto de nuevo

# Si usás WhiteNoise:
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        # Si necesitás browsable API autenticada por sesión:
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
}

SIMPLE_JWT = {
    "ALGORITHM": "HS256",
    "SIGNING_KEY": os.getenv("JWT_SECRET", SECRET_KEY),
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=4),   # antes 15m
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
}

LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/panel_operador/'
LOGOUT_REDIRECT_URL = '/accounts/login/'

LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

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
            "filename": str(BASE_DIR / "logs" / "app.log"),
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 5,
            "encoding": "utf-8",
            "formatter": "verbose",
        },
        "audit_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(BASE_DIR / "logs" / "audit.log"),
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 10,
            "encoding": "utf-8",
            "formatter": "audit",
        },
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "conciliacion_file": {
            "class": "logging.handlers.TimedRotatingFileHandler",
            "filename": str(BASE_DIR / "logs" / "conciliacion.log"),
            "when": "midnight",     # rota cada medianoche
            "interval": 1,
            "backupCount": 14,      # guarda 14 días de históricos
            "encoding": "utf-8",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "django": {"handlers": ["console", "app_file"], "level": "INFO"},
        "audit": {"handlers": ["audit_file"], "level": "INFO", "propagate": False},
        "app": {"handlers": ["app_file"], "level": "INFO"},
        "sync": {"handlers": ["app_file"], "level": "INFO", "propagate": False},
        "conciliacion": {"handlers": ["conciliacion_file"],"level": "INFO","propagate": False,},
    },
}

REGISTRO_BASE_URL = os.getenv("REGISTRO_BASE_URL", "http://localhost:8080")
REGISTRO_OUTBOX_TOKEN = os.getenv("REGISTRO_OUTBOX_TOKEN", "")

# =====================
# Sesiones en Redis
# =====================
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.getenv("REDIS_URL", "redis://redis:6379/0"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        }
    }
}
