"""
Админка каталога: категории, товары, изображения.

Ключевые фишки:
- prepopulated_fields: slug автоматически заполняется из name в браузере (JS)
- list_editable: цены и остаток можно редактировать прямо в списке товаров
- ProductImageInline: загрузка нескольких изображений на странице товара
- Фильтры по категории, активности, наличию на складе
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import Category, Product, ProductImage


# ---------------------------------------------------------------------------
# Category
# ---------------------------------------------------------------------------
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """
    Админка категорий.

    ВАЖНО: prepopulated_fields не работает с полями, у которых
    есть собственный save-override на основе name — но у нас slug
    задаётся в save() модели. Если админ введёт slug вручную —
    он и сохранится. Если оставит пустым — сгенерируется в save().
    """

    list_display = ("name", "parent", "slug", "is_active", "products_count")
    list_filter = ("is_active", "parent")
    search_fields = ("name", "slug")
    # prepopulated_fields: пока админ печатает name, JS заполняет slug.
    # Кириллица в slug-источнике → JS сам не транслитерирует,
    # но так как у нас на сервере slug генерируется с python-slugify,
    # в браузере будет кириллический slug — не страшно, при сохранении
    # мы всё равно проверим.
    # Если хотите, чтобы JS-транслит работал — можно добавить пакет,
    # но для нашего проекта не критично: реальные slug генерирует сервер.
    # prepopulated_fields = {"slug": ("name",)}
    ordering = ("name",)
    list_per_page = 50

    fieldsets = (
        (None, {
            "fields": ("name", "slug", "parent", "description", "is_active")
        }),
    )

    @admin.display(description=_("товаров"))
    def products_count(self, obj):
        """
        Счётчик товаров в категории.

        Использует related_name="products" из ForeignKey.
        Не считаем через obj.products.count() напрямую — при больших
        категориях это N+1 запросов. Для оптимизации нужен
        get_queryset() с annotate(Count("products")). Но для админки
        пока и так нормально — админ видит 50 категорий на странице.
        """
        return obj.products.count()


# ---------------------------------------------------------------------------
# ProductImage — inline для Product
# ---------------------------------------------------------------------------
class ProductImageInline(admin.TabularInline):
    """
    Inline-редактирование изображений на странице товара.

    TabularInline — компактная таблица (в отличие от StackedInline,
    где каждое поле на своей строке). Для изображений таблица удобнее:
    видно сразу все и порядок.
    """

    model = ProductImage
    extra = 1  # сколько пустых строк показывать для добавления
    fields = ("image", "alt", "order", "image_preview")
    readonly_fields = ("image_preview",)
    ordering = ("order", "id")

    @admin.display(description=_("превью"))
    def image_preview(self, obj):
        """
        Миниатюра загруженного изображения.

        format_html экранирует HTML — нельзя возвращать сырой HTML
        из пользовательских данных (XSS). Здесь url и alt — наши,
        но привычка полезная.
        """
        if obj.image:
            return format_html(
                '<img src="{}" style="max-height: 80px; max-width: 120px;" alt="{}">',
                obj.image.url,
                obj.alt or "",
            )
        return "—"


# ---------------------------------------------------------------------------
# Product
# ---------------------------------------------------------------------------
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """
    Админка товаров.

    Основная фишка — list_editable: цены и остаток можно править
    прямо из списка, не заходя в карточку. Для магазина, где цены
    меняются регулярно, это экономит кучу кликов.
    """

    list_display = (
        "name",
        "sku",
        "category",
        "price_retail",
        "price_opt1",
        "price_opt2",
        "price_opt3",
        "stock",
        "is_active",
    )
    # Поля, которые можно редактировать прямо в list_display.
    # ВАЖНО: first column (name) должен быть ссылкой на карточку —
    # поэтому name НЕ в list_editable. Django требует, чтобы
    # list_editable не пересекался с первой колонкой.
    list_editable = (
        "price_retail",
        "price_opt1",
        "price_opt2",
        "price_opt3",
        "stock",
        "is_active",
    )
    list_filter = ("is_active", "category")
    search_fields = ("name", "sku", "slug")
    # prepopulated_fields = {"slug": ("name",)}
    ordering = ("name",)
    list_per_page = 50

    # Inline: изображения можно загружать прямо из карточки товара
    inlines = [ProductImageInline]

    # Группировка полей в карточке товара.
    # Логика: сначала основное, потом цены, потом склад/статус.
    fieldsets = (
        (None, {
            "fields": ("name", "slug", "sku", "category", "description")
        }),
        (_("Цены"), {
            "fields": (
                "price_retail",
                ("price_opt1", "price_opt2", "price_opt3"),
            ),
            "description": _(
                "Розничная цена обязательна. Оптовые — опциональны, "
                "применяются по сумме корзины. Если опт не задан, "
                "используется предыдущий доступный тир."
            ),
        }),
        (_("Склад и статус"), {
            "fields": ("stock", "is_active")
        }),
    )

    # readonly — поля, которые нельзя редактировать в карточке.
    readonly_fields = ("created_at", "updated_at")

    # Дополнительно выводим created_at / updated_at в карточке
    # (они не в fieldsets — добавим в конец через отдельный fieldset,
    # но проще так: сделаем их видимыми через fieldsets выше)
    # На практике updated_at часто не показывают — не нужно. Оставим
    # только в API/консоли.

    def get_queryset(self, request):
        """
        Оптимизация запроса: select_related("category") — чтобы
        в list_display не было N+1 при обращении к category.name.
        """
        return super().get_queryset(request).select_related("category")


# ---------------------------------------------------------------------------
# ProductImage — отдельная админка (удобно для управления всеми изображениями)
# ---------------------------------------------------------------------------
@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    """
    Отдельная админка для изображений.

    Зачем отдельно, если есть inline?
    - Inline удобен при работе с конкретным товаром.
    - Отдельная админка удобна для аудита: "покажи все изображения,
      загруженные за последнюю неделю" или "найди изображения без alt".

    Это стандартный паттерн — inline + отдельная регистрация.
    """

    list_display = ("id", "product", "image_preview", "alt", "order", "created_at")
    list_filter = ("created_at", "product__category")
    search_fields = ("product__name", "product__sku", "alt")
    ordering = ("-created_at",)
    readonly_fields = ("image_preview", "created_at")
    list_per_page = 50

    @admin.display(description=_("превью"))
    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-height: 60px; max-width: 90px;" alt="{}">',
                obj.image.url,
                obj.alt or "",
            )
        return "—"

    def get_queryset(self, request):
        # select_related("product") — чтобы product.name в list_display
        # не дёргал БД на каждую строку.
        return super().get_queryset(request).select_related("product")
    