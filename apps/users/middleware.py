from django.shortcuts import redirect
from django.urls import reverse
from django.utils.deprecation import MiddlewareMixin

# URL-ы, доступные без заполненного профиля
EXEMPT_URL_NAMES = {
    "users:login",
    "users:register",
    "users:logout",
    "users:profile_complete",  # сама страница заполнения
}


class ProfileCompletionMiddleware(MiddlewareMixin):
    """
    Если пользователь аутентифицирован, но профиль не заполнен —
    редиректит на страницу заполнения.
    """

    def process_request(self, request):
        # Пропускаем анонимных
        if not request.user.is_authenticated:
            return None

        # Пропускаем админку и статику
        if request.path.startswith("/admin/") or request.path.startswith("/static/") or request.path.startswith("/media/"):
            return None

        # Уже заполнен — пропускаем
        if request.user.profile_completed:
            return None

        # Смотрим, куда идёт запрос
        match = request.resolver_match
        if match and match.view_name in EXEMPT_URL_NAMES:
            return None

        # Редирект на заполнение профиля
        return redirect("users:profile_complete")
    