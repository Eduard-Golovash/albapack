from django.shortcuts import redirect
from django.urls import reverse, resolve, Resolver404
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
        if request.path.startswith(("/admin/", "/static/", "/media/")):
            return None

        # Уже заполнен — пропускаем
        if request.user.profile_completed:
            return None

        # Резолвим URL сами — на этапе process_request request.resolver_match ещё пуст
        try:
            match = resolve(request.path_info)
        except Resolver404:
            return None  # пусть дальше разбирается Django (вернёт 404)

        current = (
            f"{match.namespace}:{match.url_name}"
            if match.namespace
            else match.url_name
        )

        if current in EXEMPT_URL_NAMES:
            return None

        return redirect("users:profile_complete")
    