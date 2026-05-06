# config/settings/prod.py
from .base import *  # noqa: F403,F401

DEBUG = False
ALLOWED_HOSTS = ["seb-contracts.ru", "www.seb-contracts.ru", "192.168.9.71", "127.0.0.1", "localhost"]
CSRF_TRUSTED_ORIGINS = ["https://seb-contracts.ru"]