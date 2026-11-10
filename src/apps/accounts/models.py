from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from .custom_user_manager import CustomUserManager


class User(AbstractBaseUser, PermissionsMixin):
    class RoleChoices(models.TextChoices):
        USER = "user", "User"
        BOSS = "boss", "Boss"

    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=100, blank=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)  # Required for Admin panel access
    is_superuser = models.BooleanField(default=False)  # Required for Admin panel access
    role = models.CharField(
        max_length=30, choices=RoleChoices.choices, default=RoleChoices.USER
    )
    objects = CustomUserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email
