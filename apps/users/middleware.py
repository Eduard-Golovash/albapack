"""
Middleware для принудительного заполнения профиля.

Если пользователь залогинен, но profile_completed=False — редиректим
на /users/profile/complete/, чтобы он заполнил обязательные поля.

Исключения: страницы логина/регистрации/логаута, сама страница заполнения,
админка, статика и медиа.
"""

from django.shortcuts import redirect
from django.utils.deprecation import MiddlewareMixin

# Имена URL-паттернов, куда incomplete_user всё-таки может попасть.
# Берём именно имена (namespace:name), а не пути — так надёжнее,
# потому что URL можно поменять в urls.py, а имена останутся.
EXEMPT_URL_NAMES = {
    "users:login",
    "users:register",
    "users:logout",
    "users:profile_complete",
}

# Префиксы путей, которые middleware не трогает.
# Нужны для админки, статики и медиафайлов.
EXEMPT_PATH_PREFIXES = (
    "/admin/",
    "/static/",
    "/media/",
)


class ProfileCompletionMiddleware(MiddlewareMixin):
    """
    ВАЖНО: используем process_view, а НЕ process_request.

    Почему:
    - process_request вызывается ДО того, как Django определит,
      какой view будет обрабатывать URL. В этот момент
      request.resolver_match = None, и мы не можем отличить
      /users/profile/complete/ от /users/profile/.
    - process_view вызывается ПОСЛЕ резолвинга URL, и там
      resolver_match уже доступен.

    Возвращаемое значение:
    - None      → продолжаем обработку запроса (пропускаем)
    - HttpResponse → middleware сам отвечает (в нашем случае — redirect)
    """

    def process_view(self, request, view_func, view_args, view_kwargs):
        # Анонимных пропускаем — они и так упрутся в @login_required
        if not request.user.is_authenticated:
            return None

        # Пропускаем админку, статику, медиа
        if request.path.startswith(EXEMPT_PATH_PREFIXES):
            return None

        # Профиль заполнен — не наше дело
        if request.user.profile_completed:
            return None

        # Разрешаем доступ к exempt-страницам (логин, регистрация и т.п.)
        # resolver_match гарантированно есть, потому что мы в process_view.
        match = request.resolver_match
        if match and match.view_name in EXEMPT_URL_NAMES:
            return None

        # Всё остальное — отправляем заполнять профиль
        return redirect("users:profile_complete")
    