#config/settings/local.py
from .base import *  # noqa: F403,F401

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]

# Django-debug-toolbar
INTERNAL_IPS = ["127.0.0.1"]

# Email backend
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"