"""
Views для приложения users.

Здесь:
- register_view         — регистрация нового пользователя
- login_view            — вход в систему
- logout_view           — выход
- profile_view          — просмотр своего профиля
- profile_complete_view — обязательное заполнение профиля
- profile_edit_view     — редактирование профиля (когда уже заполнен)

Все views — обычные функции (FBV, Function-Based Views), потому что логика
простая. Для сложных случаев можно использовать CBV (Class-Based Views).
"""

from django.contrib import messages
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .forms import PhoneLoginForm, ProfileCompleteForm, RegisterForm


# ---------------------------------------------------------------------------
# Регистрация
# ---------------------------------------------------------------------------
@require_http_methods(["GET", "POST"])
def register_view(request):
    """
    Регистрация нового пользователя.

    GET  → показываем пустую форму
    POST → валидируем, создаём пользователя, логиним, редиректим на профиль

    @require_http_methods — декоратор, который разрешает только указанные методы.
    Если кто-то отправит PUT/DELETE — Django вернёт 405 Method Not Allowed.
    Это защита от случайных/злонамеренных запросов.
    """
    # Если пользователь уже залогинен — нечего ему тут делать.
    # Редиректим на профиль (или на главную в будущем).
    if request.user.is_authenticated:
        return redirect("users:profile")

    if request.method == "POST":
        # request.POST — это словарь с данными из формы.
        # Передаём его в форму для валидации.
        form = RegisterForm(request.POST)

        if form.is_valid():
            # form.save() создаёт пользователя и хэширует пароль
            # (логика в RegisterForm.save())
            user = form.save()

            # Автоматически логиним пользователя после регистрации.
            # Это улучшает UX — не нужно отдельно вводить пароль.
            #
            # ВАЖНО: auth_login() создаёт сессию и записывает user.pk в неё.
            # Мы передаём backend, потому что у нас может быть несколько
            # backends аутентификации (сейчас один, но Django требует явно).
            auth_login(request, user, backend="django.contrib.auth.backends.ModelBackend")

            # messages — это фреймворк для временных сообщений (flash messages).
            # Они живут до следующего запроса и показываются в шаблоне.
            messages.success(request, "Регистрация успешна! Заполните профиль.")

            # Редирект на страницу заполнения профиля.
            # reverse() — правильный способ получить URL по имени маршрута.
            return redirect("users:profile_complete")
    else:
        # GET-запрос — показываем пустую форму
        form = RegisterForm()

    # render() — рендерит шаблон с контекстом и возвращает HttpResponse
    return render(request, "users/register.html", {"form": form})


# ---------------------------------------------------------------------------
# Логин
# ---------------------------------------------------------------------------
@require_http_methods(["GET", "POST"])
def login_view(request):
    """
    Вход в систему.

    GET  → показываем форму логина
    POST → проверяем phone+password, логиним, редиректим

    Использует PhoneLoginForm, который наследуется от AuthenticationForm.
    Он сам вызывает authenticate() и валидирует credentials.
    """
    if request.user.is_authenticated:
        return redirect("users:profile")

    if request.method == "POST":
        # Передаём request в форму — AuthenticationForm его использует
        # (например, для проверки is_active)
        form = PhoneLoginForm(request=request, data=request.POST)

        if form.is_valid():
            # form.get_user() возвращает пользователя, прошедшего аутентификацию.
            # Мы не ищем его сами — это сделал backend внутри формы.
            user = form.get_user()

            auth_login(request, user, backend="django.contrib.auth.backends.ModelBackend")

            messages.success(request, f"Добро пожаловать, {user.get_short_name()}!")

            # Логика редиректа после логина:
            # 1. Если в URL был ?next=/cart/ — идём туда (стандарт Django).
            #    Это используется, когда неаутентифицированный пользователь
            #    пытался зайти на защищённую страницу.
            # 2. Если профиль не заполнен — на заполнение.
            # 3. Иначе — на профиль.

            next_url = request.GET.get("next") or request.POST.get("next")
            if next_url:
                # Проверяем, что next — внутренний URL (защита от open redirect).
                # is_safe_url() устарел в новых версиях Django,
                # используем url_has_allowed_host_and_scheme.
                from django.utils.http import url_has_allowed_host_and_scheme
                if url_has_allowed_host_and_scheme(
                    url=next_url,
                    allowed_hosts={request.get_host()},
                    require_https=request.is_secure(),
                ):
                    return redirect(next_url)

            if not user.profile_completed:
                return redirect("users:profile_complete")

            return redirect("users:profile")
    else:
        form = PhoneLoginForm(request=request)

    return render(request, "users/login.html", {"form": form})


# ---------------------------------------------------------------------------
# Выход
# ---------------------------------------------------------------------------
@require_http_methods(["GET", "POST"])
def logout_view(request):
    """
    Выход из системы.

    Обычно делают POST, потому что logout — это изменение состояния.
    Но многие проекты допускают GET для удобства (просто клик по ссылке).
    Мы разрешаем оба.

    @login_required — если пользователь не залогинен, Django редиректит
    на LOGIN_URL с параметром ?next=...
    """
    if request.user.is_authenticated:
        auth_logout(request)
        messages.info(request, "Вы вышли из системы.")

    return redirect("users:login")


# ---------------------------------------------------------------------------
# Профиль — просмотр
# ---------------------------------------------------------------------------
@login_required
def profile_view(request):
    """
    Просмотр своего профиля.

    @login_required — защита: анонимного пользователя редиректит на логин.
    Внутри view мы уверены, что request.user — это User.
    """
    return render(request, "users/profile.html", {"user": request.user})


# ---------------------------------------------------------------------------
# Профиль — заполнение (обязательное)
# ---------------------------------------------------------------------------
@login_required
def profile_complete_view(request):
    """
    Заполнение профиля после регистрации.

    Вызывается из middleware, когда profile_completed=False.

    Если профиль уже заполнен — редиректим на просмотр
    (нечего тут делать).
    """
    # Если профиль уже заполнен — не даём сюда зайти снова
    if request.user.profile_completed:
        return redirect("users:profile")

    if request.method == "POST":
        # instance=request.user — критично!
        # Без этого Django создал бы НОВОГО пользователя,
        # а нам нужно обновить существующего.
        form = ProfileCompleteForm(request.POST, instance=request.user)

        if form.is_valid():
            # save() обновит request.user и пересчитает profile_completed
            # (логика в ProfileCompleteForm.save())
            form.save()

            messages.success(request, "Профиль заполнен!")
            return redirect("users:profile")
    else:
        # GET — предзаполняем форму текущими данными пользователя
        # (телефон там уже есть, но он read-only в шаблоне)
        form = ProfileCompleteForm(instance=request.user)

    return render(request, "users/profile_complete.html", {"form": form})


# ---------------------------------------------------------------------------
# Профиль — редактирование (когда уже заполнен)
# ---------------------------------------------------------------------------
@login_required
def profile_edit_view(request):
    """
    Редактирование профиля.

    Отличие от profile_complete_view:
    - Доступно только когда profile_completed=True
    - Просто сохраняет изменения, не дёргает middleware
    """
    if not request.user.profile_completed:
        # Если профиль не заполнен — сначала пусть заполнит
        return redirect("users:profile_complete")

    if request.method == "POST":
        form = ProfileCompleteForm(request.POST, instance=request.user)

        if form.is_valid():
            form.save()
            messages.success(request, "Профиль обновлён.")
            return redirect("users:profile")
    else:
        form = ProfileCompleteForm(instance=request.user)

    return render(request, "users/profile_edit.html", {"form": form})
