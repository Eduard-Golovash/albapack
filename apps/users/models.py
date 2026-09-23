from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    """
    Кастомная модель пользователя. Регистрация только по телефону. Email и имя обязательны
    для заполнения в личном кабинете (profile_completed=True).
    """

    # --- Регистрационные поля ---
    phone = models.CharField(
        _("телефон"),
        max_length=20,
        unique=True,
        db_index=True,
        help_text=_("Формат: +7XXXXXXXXXX"),
    )

    # --- Профиль ---
    email = models.EmailField(
        _("email"),
        unique=True,
        null=True,
        blank=True,
        db_index=True,
    )
    first_name = models.CharField(_("имя"), max_length=150, blank=True)
    last_name = models.CharField(_("фамилия"), max_length=150, blank=True)
    birth_date = models.DateField(_("дата рождения"), null=True, blank=True)

    profile_completed = models.BooleanField(
        _("профиль заполнен"),
        default=False,
        help_text=_("True, когда пользователь заполнил обязательные поля профиля"),
    )

    # --- Служебные ---
    is_staff = models.BooleanField(_("статус сотрудника"), default=False)
    is_active = models.BooleanField(_("активен"), default=True)
    newsletter_subscribed = models.BooleanField(_("подписка на рассылку"), default=False)

    date_joined = models.DateTimeField(_("дата регистрации"), default=timezone.now)
    created_at = models.DateTimeField(_("создан"), auto_now_add=True)
    updated_at = models.DateTimeField(_("обновлён"), auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = ["email"]

    class Meta:
        verbose_name = _("пользователь")
        verbose_name_plural = _("пользователи")
        ordering = ["-date_joined"]

    def __str__(self):
        return self.email or self.phone

    def get_full_name(self):
        full = f"{self.first_name} {self.last_name}".strip()
        return full or self.email or self.phone

    def get_short_name(self):
        return self.first_name or self.phone

    def check_profile_completed(self):
        """Проверяет, заполнены ли обязательные поля. Обновляет флаг."""
        completed = bool(self.email and self.first_name)
        if completed != self.profile_completed:
            self.profile_completed = completed
            self.save(update_fields=["profile_completed", "updated_at"])
        return completed
    