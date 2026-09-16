from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Временная модель — расширим в feature/users-custom-model."""
    email = models.EmailField(unique=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    def __str__(self):
        return self.email
    