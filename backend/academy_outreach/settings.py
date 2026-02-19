"""
Django settings for Academy Outreach Platform.

Uses PostgreSQL as the database and django-rest-framework for the API layer.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'dev-secret-key-change-in-production')

DEBUG = os.environ.get('DEBUG', 'True').lower() in ('true', '1', 'yes')

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

# Application definition
INSTALLED_APPS = [
    'django.contrib.contenttypes',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'django_q',
    'app',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
]

# Don't redirect to add trailing slashes — API clients send exact URLs
APPEND_SLASH = False

ROOT_URLCONF = 'academy_outreach.urls'

FRONTEND_DIST_DIR = BASE_DIR.parent / 'frontend' / 'dist'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [FRONTEND_DIST_DIR],
        'APP_DIRS': True,
    },
]

WSGI_APPLICATION = 'academy_outreach.wsgi.application'

# Database — PostgreSQL in production, SQLite for local dev
DB_ENGINE = os.environ.get('DB_ENGINE', 'django.db.backends.sqlite3')

if DB_ENGINE == 'django.db.backends.sqlite3':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': DB_ENGINE,
            'NAME': os.environ.get('DB_NAME', 'academy_outreach'),
            'USER': os.environ.get('DB_USER', 'postgres'),
            'PASSWORD': os.environ.get('DB_PASSWORD', 'postgres'),
            'HOST': os.environ.get('DB_HOST', 'localhost'),
            'PORT': os.environ.get('DB_PORT', '5432'),
        }
    }

# Static files — serve React production build assets
STATIC_URL = '/static/'
STATICFILES_DIRS = [FRONTEND_DIST_DIR]

# CORS
CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOWED_ORIGINS = [
    'http://localhost:5173',
    'http://localhost:5174',
    'http://localhost:3000',
    'http://127.0.0.1:5173',
    'http://127.0.0.1:5174',
]

# DRF
REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
    ],
    'DEFAULT_PAGINATION_CLASS': None,
    'UNAUTHENTICATED_USER': None,
    'DEFAULT_AUTHENTICATION_CLASSES': [],
    'DEFAULT_PERMISSION_CLASSES': [],
}

# LLM / App configuration
LLM_PROVIDER = os.environ.get('LLM_PROVIDER', 'mock')  # "openai" or "mock"
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')
OPENAI_MODEL = os.environ.get('OPENAI_MODEL', 'gpt-4o-mini')

# NBA policy config
MAX_ATTEMPTS_PER_CHANNEL = int(os.environ.get('MAX_ATTEMPTS_PER_CHANNEL', '3'))
COOLDOWN_HOURS_AFTER_NO_RESPONSE = int(os.environ.get('COOLDOWN_HOURS_AFTER_NO_RESPONSE', '24'))
ESCALATION_AFTER_FAILED_ATTEMPTS = int(os.environ.get('ESCALATION_AFTER_FAILED_ATTEMPTS', '5'))

# django-q2 — lightweight task queue using the ORM broker (no Redis needed)
Q_CLUSTER = {
    'name': 'academy-outreach',
    'workers': 2,
    'timeout': 120,
    'retry': 180,
    'orm': 'default',
    'bulk': 10,
    'catch_up': True,
}

# SMS batch extraction timing
SMS_QUIET_PERIOD_MINUTES = int(os.environ.get('SMS_QUIET_PERIOD_MINUTES', '5'))
SMS_MAX_ACCUMULATION_MINUTES = int(os.environ.get('SMS_MAX_ACCUMULATION_MINUTES', '15'))
SMS_MAX_BUFFERED_MESSAGES = int(os.environ.get('SMS_MAX_BUFFERED_MESSAGES', '6'))

# All datetimes are timezone-aware UTC (Django best practice)
USE_TZ = True
TIME_ZONE = 'UTC'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}
