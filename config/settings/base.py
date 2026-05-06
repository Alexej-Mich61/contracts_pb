# config/settings/base.py
import environ
from pathlib import Path
import os

env = environ.Env(DEBUG=(bool, True))

# === Читаем .env из той же папки, где лежит base.py ===
_ENV_FILE = Path(__file__).resolve().parent / ".env"
if _ENV_FILE.exists():
    environ.Env.read_env(str(_ENV_FILE))

BASE_DIR = Path(__file__).resolve().parent.parent

ROOT_DIR = BASE_DIR.parent
APPS_DIR = ROOT_DIR / "apps"

#import sys
#sys.path.insert(0, str(APPS_DIR))   # APPS_DIR = ROOT_DIR / "apps"


SECRET_KEY = env("SECRET_KEY", default="dev-secret-change-me")

DEBUG = env("DEBUG")

# ALLOWED_HOSTS из .env (через запятую) или пустой список по умолчанию
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

# Если нужен fallback для разработки:
# ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])


# Apps
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
]

THIRD_PARTY_APPS = [
    "debug_toolbar",
    "django_extensions",
]

LOCAL_APPS = [
    "auditlog",
    "apps.identity",
    "apps.contract_core",
    "apps.faq",
    "apps.mailing",
    "import_export",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'debug_toolbar.middleware.DebugToolbarMiddleware',  # ← Дебаг тулбар
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'simple_history.middleware.HistoryRequestMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'config.middleware.CurrentUserMiddleware', # ← мой middleware.py, путь указан от корня проекта
    'auditlog.middleware.AuditlogMiddleware',
    'django_htmx.middleware.HtmxMiddleware',  # <-- Обязательно
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        "DIRS": [ROOT_DIR / "templates"],
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

WSGI_APPLICATION = "config.wsgi.application"


# Database
DB_ENGINE = env("DB_ENGINE", default="sqlite")

if DB_ENGINE == "postgres":
    DATABASES = {
        "default": env.db_url("DATABASE_URL")
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ROOT_DIR / "db.sqlite3",
        }
    }
# DATABASES = {
#     "default": {
#         "ENGINE": "django.db.backends.sqlite3",
#         "NAME": ROOT_DIR / "db.sqlite3",   # файл появится в корне проекта
#     }
# }
# DATABASES = {
#     "default": env.db(
#         default="postgres://postgres:pbpass@localhost:5433/contracts_pb"
#     )
# }

# Redis (для Celery + Channels)
# REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")


# Passwords / Auth
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

AUTH_USER_MODEL = "identity.User"


# Static / Media
STATIC_URL = "/static/"
STATICFILES_DIRS = [ROOT_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"   # Для продакшена
MEDIA_URL = "/media/"
MEDIA_ROOT = ROOT_DIR / "media"


# Internationalization
LANGUAGE_CODE = "ru"
TIME_ZONE = "Europe/Moscow"
USE_I18N = True
USE_TZ = True


# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Logging
LOGS_DIR = ROOT_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)         # создаст при первом запуске

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {name} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOGS_DIR / "contracts.log",
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 5,
            "formatter": "verbose",
        },
        "scheduler_file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOGS_DIR / "scheduler.log",
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 3,
            "formatter": "verbose",
        },
        # ← НОВЫЙ handler для сохранения договоров
        "contracts_save_file": {
            "level": "DEBUG",   # DEBUG, чтобы ловить и принты-уровень при разработке
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOGS_DIR / "contracts_save.log",
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 5,
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "apps": {
            "handlers": ["console", "file"],
            "level": "DEBUG",
            "propagate": False,
        },
        "contract_core.scheduler": {
            "handlers": ["console", "scheduler_file"],
            "level": "INFO",
            "propagate": False,
        },
        # ← НОВЫЙ logger для миксина сохранения договоров
        "apps.contract_core.mixins": {
            "handlers": ["console", "contracts_save_file"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}

ADMIN_AUTOCOMPLETE_FIELDS = True

# # Добавить в CELERY_BEAT_SCHEDULE
# CELERY_BEAT_SCHEDULE = {
#     'update-online-statuses': {
#         'task': 'apps.chat.tasks.update_online_statuses',
#         'schedule': 60.0,  # каждую минуту
#     },
# }

# Tailwind не используется

# Auth
LOGIN_URL = "identity:login"
LOGIN_REDIRECT_URL = "identity:home"

