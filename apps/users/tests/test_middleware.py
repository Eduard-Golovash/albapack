"""
Тесты для ProfileCompletionMiddleware.

Проверяем сценарии:
- Анонимный пользователь — пропускается
- Пользователь с заполненным профилем — пропускается
- Пользователь с незаполненным профилем — редиректится на profile_complete
- Exempt-страницы (login/register/logout/profile_complete) — доступны
- Админка — доступна
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class ProfileCompletionMiddlewareTests(TestCase):
    """Тесты для middleware."""

    def setUp(self):
        # Пользователь БЕЗ заполненного профиля (profile_completed=False)
        self.incomplete_user = User.objects.create_user(
            phone="+79990000060",
            password="StrongPass123!",
        )
        # Пользователь С заполненным профилем
        self.complete_user = User.objects.create_user(
            phone="+79990000061",
            password="StrongPass123!",
            email="complete@example.com",
            first_name="Иван",
            profile_completed=True,
        )

    def test_anonymous_passes_through(self):
        """Анонимный пользователь не редиректится middleware."""
        response = self.client.get(reverse("users:register"))
        self.assertEqual(response.status_code, 200)

    def test_complete_user_passes_through(self):
        """Пользователь с профилем видит /users/profile/."""
        self.client.force_login(self.complete_user)
        response = self.client.get(reverse("users:profile"))

        self.assertEqual(response.status_code, 200)

    def test_incomplete_user_redirected_from_protected_page(self):
        """Пользователь без профиля на /users/profile/ — редирект."""
        self.client.force_login(self.incomplete_user)
        response = self.client.get(reverse("users:profile"))

        self.assertRedirects(response, reverse("users:profile_complete"))

    def test_incomplete_user_can_open_profile_complete(self):
        """
        ВАЖНО: страница заполнения профиля должна быть доступна
        пользователю с незаполненным профилем — иначе будет
        бесконечный редирект.
        """
        self.client.force_login(self.incomplete_user)
        response = self.client.get(reverse("users:profile_complete"))

        # Если middleware неправильно работает — тут будет redirect loop
        # или 500. Ожидаем 200 (форма).
        self.assertEqual(response.status_code, 200)

    def test_incomplete_user_can_open_logout(self):
        """Логаут доступен — иначе пользователь не сможет выйти."""
        self.client.force_login(self.incomplete_user)

        # POST — потому что логаут у нас принимает и GET, и POST
        response = self.client.post(reverse("users:logout"))

        # Логаут редиректит на login — это ОК. Главное,
        # чтобы не было редиректа на profile_complete.
        if response.status_code == 302:
            self.assertNotIn(reverse("users:profile_complete"), response.url)

    def test_admin_url_exempt(self):
        """Админка не триггерит middleware."""
        # Делаем пользователя staff, чтобы /admin/ не редиректил на admin login
        self.incomplete_user.is_staff = True
        self.incomplete_user.is_superuser = True
        self.incomplete_user.save()
        self.client.force_login(self.incomplete_user)

        response = self.client.get("/admin/")

        # Может быть 200 или редирект внутри админки — но НЕ на profile_complete
        if response.status_code == 302:
            self.assertNotIn(reverse("users:profile_complete"), response.url)
            