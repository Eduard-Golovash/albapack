from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("phone", "email", "first_name", "last_name", "profile_completed", "is_staff", "is_active")
    list_filter = ("is_staff", "is_superuser", "is_active", "profile_completed", "newsletter_subscribed")
    search_fields = ("phone", "email", "first_name", "last_name")
    ordering = ("-date_joined",)
    readonly_fields = ("date_joined", "created_at", "updated_at", "last_login", "profile_completed")

    fieldsets = (
        (None, {"fields": ("phone", "password")}),
        (_("Профиль"), {"fields": ("email", "first_name", "last_name", "birth_date")}),
        (_("Права"), {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        (_("Подписки"), {"fields": ("newsletter_subscribed",)}),
        (_("Даты"), {"fields": ("last_login", "date_joined", "created_at", "updated_at")}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("phone", "email", "password1", "password2", "is_staff", "is_active"),
        }),
    )
    