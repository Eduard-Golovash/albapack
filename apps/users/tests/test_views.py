"""
Тесты для views приложения users.

Здесь проверяем:
- register_view         — регистрация
- login_view            — логин
- logout_view           — логаут
- profile_view          — просмотр профиля
- profile_complete_view — обязательное заполнение профиля
- profile_edit_view     — редактирование профиля

Инструменты:
- django.test.TestCase — базовый класс для тестов с БД
- django.test.Client   — имитирует HTTP-запросы из кода,
                         помнит cookies и сессию между запросами
- reverse()            — превращает "users:login" в "/users/login/",
                         так тесты не зависят от конкретных URL
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

# get_user_model() — правильный способ получить модель User.
# Не импортируем напрямую: если завтра модель переопределят, тесты
# останутся рабочими.
User = get_user_model()


# ---------------------------------------------------------------------------
# Регистрация
# ---------------------------------------------------------------------------
class RegisterViewTests(TestCase):
    """Тесты для register_view."""

    def setUp(self):
        """
        setUp вызывается перед КАЖДЫМ тестом класса.
        Здесь готовим общие данные — URL и валидный payload формы.
        """
        self.url = reverse("users:register")
        self.valid_data = {
            "phone": "+79990000001",
            "password1": "StrongPass123!",
            "password2": "StrongPass123!",
        }
        # Пользователь для теста "уже залогинен" — с завершённым профилем,
        # чтобы после редиректа на /users/profile/ middleware не перекинул
        # его дальше на /users/profile/complete/.
        self.logged_in_user = User.objects.create_user(
            phone="+79990000002",
            password="Pass123!",
            email="existing@example.com",
            first_name="Иван",
            profile_completed=True,
        )

    def test_get_returns_200(self):
        """GET /users/register/ рендерит форму."""
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/register.html")
        # response.context — словарь контекста, переданный в render()
        self.assertIn("form", response.context)

    def test_post_valid_creates_user(self):
        """POST с валидными данными создаёт пользователя."""
        self.client.post(self.url, self.valid_data)
    
        # Проверяем, что пользователь с указанным телефоном появился
        self.assertTrue(User.objects.filter(phone="+79990000001").exists())
        user = User.objects.get(phone="+79990000001")
        self.assertTrue(user.check_password("StrongPass123!"))
        self.assertFalse(user.profile_completed)    

    def test_post_valid_redirects_to_profile_complete(self):
        """После успешной регистрации — редирект на заполнение профиля."""
        response = self.client.post(self.url, self.valid_data)
        self.assertRedirects(response, reverse("users:profile_complete"))

    def test_post_valid_logs_user_in(self):
        """После регистрации пользователь сразу авторизован."""
        self.client.post(self.url, self.valid_data)

        # После login() Django кладёт в сессию ключ _auth_user_id.
        # Если он есть — значит пользователь залогинен.
        self.assertIn("_auth_user_id", self.client.session)

    def test_post_passwords_mismatch(self):
        """Пароли не совпадают — форма невалидна, пользователь не создан."""
        data = self.valid_data.copy()
        data["password2"] = "DifferentPass123!"
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)  # та же страница с ошибкой
        # Проверяем КОНКРЕТНО, что пользователь с этим телефоном не создан.
        # Это устойчивее, чем абсолютный count(): если в setUp добавится
        # ещё одна фикстура, тест не сломается.
        self.assertFalse(User.objects.filter(phone="+79990000001").exists())
        self.assertIn("password2", response.context["form"].errors)

    def test_post_phone_already_exists(self):
        """Нельзя зарегистрироваться с занятым телефоном."""
        # Заняли телефон у существующего пользователя (logged_in_user.phone).
        data = self.valid_data.copy()
        data["phone"] = self.logged_in_user.phone

        response = self.client.post(self.url, data)

        self.assertEqual(response.status_code, 200)
        self.assertIn("phone", response.context["form"].errors)

    def test_logged_in_user_redirected(self):
        """Залогиненного пользователя с /register/ редиректит на профиль."""
        self.client.force_login(self.logged_in_user)

        response = self.client.get(self.url)
        self.assertRedirects(response, reverse("users:profile"))


# ---------------------------------------------------------------------------
# Логин
# ---------------------------------------------------------------------------
class LoginViewTests(TestCase):
    """Тесты для login_view."""

    def setUp(self):
        self.url = reverse("users:login")
        # Создаём пользователя с ЗАПОЛНЕННЫМ профилем — иначе
        # после логина он уйдёт на profile_complete, а не на profile.
        self.user = User.objects.create_user(
            phone="+79990000010",
            password="StrongPass123!",
            email="user10@example.com",
            first_name="Иван",
            profile_completed=True,
        )

    def test_get_returns_200(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/login.html")

    def test_post_valid_logs_in(self):
        response = self.client.post(self.url, {
            # ВАЖНО: поле в форме называется "username" — это legacy
            # от Django AuthenticationForm. Мы его переименовали в label,
            # но имя ключа осталось "username".
            "username": "+79990000010",
            "password": "StrongPass123!",
        })

        # Успешный POST с редиректом → 302
        self.assertEqual(response.status_code, 302)
        self.assertIn("_auth_user_id", self.client.session)

    def test_post_valid_redirects_to_profile_if_completed(self):
        response = self.client.post(self.url, {
            "username": "+79990000010",
            "password": "StrongPass123!",
        })
        self.assertRedirects(response, reverse("users:profile"))

    def test_post_valid_redirects_to_complete_if_not_completed(self):
        """Если профиль не заполнен — редирект на заполнение."""
        self.user.profile_completed = False
        self.user.save()

        response = self.client.post(self.url, {
            "username": "+79990000010",
            "password": "StrongPass123!",
        })
        self.assertRedirects(response, reverse("users:profile_complete"))

    def test_post_invalid_password(self):
        response = self.client.post(self.url, {
            "username": "+79990000010",
            "password": "WrongPass!",
        })

        self.assertEqual(response.status_code, 200)  # страница с ошибкой
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_post_nonexistent_phone(self):
        response = self.client.post(self.url, {
            "username": "+79990009999",
            "password": "StrongPass123!",
        })

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_next_parameter_respected(self):
        """После логина с ?next=... редиректим именно туда."""
        # /users/profile/ — валидный безопасный URL (тот же хост)
        next_url = reverse("users:profile")

        response = self.client.post(
            f"{self.url}?next={next_url}",
            {
                "username": "+79990000010",
                "password": "StrongPass123!",
                # next передаётся и в POST — login_view смотрит оба места
                "next": next_url,
            },
        )

        # response.url — куда редиректит
        self.assertEqual(response.url, next_url)

    def test_already_logged_in_redirected(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse("users:profile"))


# ---------------------------------------------------------------------------
# Логаут
# ---------------------------------------------------------------------------
class LogoutViewTests(TestCase):
    """Тесты для logout_view."""

    def setUp(self):
        self.url = reverse("users:logout")
        self.user = User.objects.create_user(
            phone="+79990000020", password="StrongPass123!"
        )

    def test_logout_clears_session(self):
        self.client.force_login(self.user)
        self.assertIn("_auth_user_id", self.client.session)

        self.client.post(self.url)

        # После логаута ключа в сессии нет
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_redirects_to_login(self):
        self.client.force_login(self.user)
        response = self.client.post(self.url)
        self.assertRedirects(response, reverse("users:login"))

    def test_anonymous_logout_does_not_crash(self):
        """Анонимный логаут не падает, редиректит на логин."""
        response = self.client.post(self.url)
        self.assertRedirects(response, reverse("users:login"))


# ---------------------------------------------------------------------------
# Просмотр профиля
# ---------------------------------------------------------------------------
class ProfileViewTests(TestCase):
    """Тесты для profile_view."""

    def setUp(self):
        self.url = reverse("users:profile")
        self.user = User.objects.create_user(
            phone="+79990000030",
            password="StrongPass123!",
            email="user30@example.com",
            first_name="Пётр",
            profile_completed=True,
        )

    def test_requires_login(self):
        """Анонимный пользователь получает редирект на логин."""
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)
        # @login_required добавляет ?next=/users/profile/, проверим что URL логина
        # встречается в редиректе
        self.assertIn(reverse("users:login"), response.url)

    def test_shows_user_data(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/profile.html")
        self.assertEqual(response.context["user"], self.user)

    def test_page_contains_phone_and_name(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)

        # assertContains ищет подстроку в HTML — удобно для быстрых проверок
        self.assertContains(response, "+79990000030")
        self.assertContains(response, "Пётр")


# ---------------------------------------------------------------------------
# Заполнение профиля
# ---------------------------------------------------------------------------
class ProfileCompleteViewTests(TestCase):
    """Тесты для profile_complete_view."""

    def setUp(self):
        self.url = reverse("users:profile_complete")
        # profile_completed=False по умолчанию из модели
        self.user = User.objects.create_user(
            phone="+79990000040", password="StrongPass123!"
        )

    def test_requires_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("users:login"), response.url)

    def test_get_returns_form(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/profile_complete.html")

    def test_redirects_if_profile_already_completed(self):
        """Если профиль уже заполнен — редирект на профиль."""
        self.user.profile_completed = True
        self.user.save()
        self.client.force_login(self.user)

        response = self.client.get(self.url)
        self.assertRedirects(response, reverse("users:profile"))

    def test_post_valid_saves_and_completes(self):
        self.client.force_login(self.user)

        response = self.client.post(self.url, {
            "email": "complete@example.com",
            "first_name": "Анна",
            "last_name": "Петрова",
            "birth_date": "1990-05-15",
        })

        self.assertRedirects(response, reverse("users:profile"))

        # refresh_from_db() перечитывает объект из БД —
        # иначе мы бы видели старое состояние в памяти
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "complete@example.com")
        self.assertEqual(self.user.first_name, "Анна")
        self.assertEqual(self.user.last_name, "Петрова")
        self.assertTrue(self.user.profile_completed)

    def test_post_without_email_fails(self):
        """email обязателен на уровне формы."""
        self.client.force_login(self.user)

        response = self.client.post(self.url, {
            "first_name": "Анна",
        })

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertFalse(self.user.profile_completed)
        self.assertIn("email", response.context["form"].errors)

    def test_post_without_first_name_fails(self):
        """first_name обязателен на уровне формы."""
        self.client.force_login(self.user)

        response = self.client.post(self.url, {
            "email": "a@example.com",
        })

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertIn("first_name", response.context["form"].errors)

    def test_post_with_taken_email_fails(self):
        """Нельзя занять email, который уже есть у другого пользователя."""
        User.objects.create_user(
            phone="+79990000041",
            password="Pass123!",
            email="taken@example.com",
        )
        self.client.force_login(self.user)

        response = self.client.post(self.url, {
            "email": "taken@example.com",
            "first_name": "Анна",
        })

        self.assertEqual(response.status_code, 200)
        self.assertIn("email", response.context["form"].errors)


# ---------------------------------------------------------------------------
# Редактирование профиля
# ---------------------------------------------------------------------------
class ProfileEditViewTests(TestCase):
    """Тесты для profile_edit_view."""

    def setUp(self):
        self.url = reverse("users:profile_edit")
        self.user = User.objects.create_user(
            phone="+79990000050",
            password="StrongPass123!",
            email="edit@example.com",
            first_name="Иван",
            profile_completed=True,
        )

    def test_requires_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("users:login"), response.url)

    def test_redirects_if_profile_not_completed(self):
        """Незаполненный профиль — сначала на profile_complete."""
        self.user.profile_completed = False
        self.user.save()
        self.client.force_login(self.user)

        response = self.client.get(self.url)
        self.assertRedirects(response, reverse("users:profile_complete"))

    def test_get_prefills_form(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/profile_edit.html")
        # Форма привязана к request.user — initial-значения из модели
        self.assertEqual(response.context["form"].initial["email"], "edit@example.com")

    def test_post_updates_profile(self):
        self.client.force_login(self.user)

        response = self.client.post(self.url, {
            "email": "edit@example.com",
            "first_name": "Пётр",
            "last_name": "Сидоров",
            "birth_date": "1985-03-20",
        })

        self.assertRedirects(response, reverse("users:profile"))

        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Пётр")
        self.assertEqual(self.user.last_name, "Сидоров")
        self.assertTrue(self.user.profile_completed)
        