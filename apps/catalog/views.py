"""
Views каталога.

Сейчас — заглушки. Реальная реализация будет в feature/catalog-views.
Заглушки нужны, чтобы:
1. reverse("catalog:...") работал (namespace регистрируется при подключении urls.py)
2. get_absolute_url() на моделях Category и Product не падал
3. Тесты моделей могли проверить эти методы

Когда будем делать реальные views — заменим тела функций,
но имена и сигнатуры оставим те же. Тогда ничего не сломается.
"""

from django.http import HttpResponse


def product_list_view(request):
    """Заглушка: список товаров. Реализация — в feature/catalog-views."""
    return HttpResponse("TODO: product list")


def category_detail_view(request, slug):
    """Заглушка: страница категории."""
    return HttpResponse(f"TODO: category {slug}")


def product_detail_view(request, slug):
    """Заглушка: страница товара."""
    return HttpResponse(f"TODO: product {slug}")
