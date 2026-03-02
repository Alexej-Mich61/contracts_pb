#config/settings/base.py
import environ
from pathlib import Path

env = environ.Env(DEBUG=(bool, True))

BASE_DIR = Path(__file__).resolve().parent.parent

ROOT_DIR = BASE_DIR.parent
APPS_DIR = ROOT_DIR / "apps"

#import sys
#sys.path.insert(0, str(APPS_DIR))   # APPS_DIR = ROOT_DIR / "apps"


SECRET_KEY = env("SECRET_KEY", default="dev-secret-change-me")

DEBUG = env("DEBUG")

ALLOWED_HOSTS = []


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
    #"simple_history",
    "auditlog",
    "apps.identity",
    "apps.contract_core",
    "apps.audit",
    "apps.chat",
    "apps.mailing",
    "import_export",
    "frontend",

]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'debug_toolbar.middleware.DebugToolbarMiddleware',  # ← новая
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'simple_history.middleware.HistoryRequestMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'config.middleware.CurrentUserMiddleware', # ← мой middleware.py, путь указан от корня проекта
    'auditlog.middleware.AuditlogMiddleware',
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
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ROOT_DIR / "db.sqlite3",   # файл появится в корне проекта
    }
}
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
            "maxBytes": 10 * 1024 * 1024,   # 10 МБ
            "backupCount": 5,
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
    "loggers": {
        "django": {                       # системные логи Django
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "apps": {                         # всё, что пишем мы
            "handlers": ["console", "file"],
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
