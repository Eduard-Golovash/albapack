"""
URL-маршруты каталога.

app_name = "catalog" — namespace. В шаблонах и коде используем
{% url 'catalog:product_detail' slug=... %} и reverse("catalog:product_detail", ...).

ВАЖНО: этот файл создаётся на этапе моделей, ДО реализации views.
Заглушки во views.py будут заменены реальными обработчиками в фиче
feature/catalog-views, но имена маршрутов останутся неизменными —
иначе поломаются get_absolute_url() и все ссылки.
"""

from django.urls import path

from . import views

app_name = "catalog"

urlpatterns = [
    # Список товаров (главная каталога)
    path("", views.product_list_view, name="product_list"),

    # Конкретная категория
    path(
        "category/<slug:slug>/",
        views.category_detail_view,
        name="category_detail",
    ),

    # Конкретный товар
    path(
        "product/<slug:slug>/",
        views.product_detail_view,
        name="product_detail",
    ),
]
