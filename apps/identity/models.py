#apps/identity/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models





class User(AbstractUser):
    email = models.EmailField("email", unique=True)
    phone = models.CharField("телефон", max_length=20, blank=True)
    is_system = models.BooleanField("Системный пользователь", default=False, editable=False)

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"

    def __str__(self):
        return self.get_full_name() or self.username