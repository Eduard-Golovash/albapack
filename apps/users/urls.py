"""
URL-маршруты для приложения users.

app_name = "users" — это namespace.
Это значит, что в шаблонах и в коде мы ссылаемся на URL-ы как "users:login",
"users:profile" и т.д. Namespace защищает от конфликтов, если в разных
приложениях есть одинаковые имена маршрутов (например, "login" и в users, и в admin).
"""

from django.urls import path

from . import views

app_name = "users"

urlpatterns = [
    # Регистрация
    path("register/", views.register_view, name="register"),

    # Логин и логаут
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),

    # Профиль
    path("profile/", views.profile_view, name="profile"),
    path("profile/complete/", views.profile_complete_view, name="profile_complete"),
    path("profile/edit/", views.profile_edit_view, name="profile_edit"),
]
