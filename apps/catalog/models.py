"""
Модели каталога: категории, товары, изображения товаров.
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .constants import WHOLESALE_TIERS

from slugify import slugify

# ---------------------------------------------------------------------------
# Утилита
# ---------------------------------------------------------------------------
def generate_unique_slug(instance, value, slug_field_name="slug"):
    """
    Генерирует уникальный slug.

    Используем python-slugify, который транслитерирует кириллицу:
    "Коробка картонная" → "korobka-kartonnaya".
    Без транслита Django возвращал бы "упаковка" (кириллица в URL).
    """
    model = instance.__class__
    # Транслит + slug + lowercase (всё делает python-slugify)
    slug = slugify(value) or "item"

    queryset = model.objects.all()
    if instance.pk:
        queryset = queryset.exclude(pk=instance.pk)

    original_slug = slug
    counter = 1
    while queryset.filter(**{slug_field_name: slug}).exists():
        slug = f"{original_slug}-{counter}"
        counter += 1

    return slug


# ---------------------------------------------------------------------------
# Категория
# ---------------------------------------------------------------------------
class Category(models.Model):
    """
    Категория товаров с поддержкой вложенности.
    """

    name = models.CharField(_("название"), max_length=200)
    slug = models.SlugField(
        _("slug"),
        max_length=200,
        unique=True,
        blank=True,
        help_text=_("URL-идентификатор. Заполнится автоматически из названия"),
    )
    parent = models.ForeignKey(
        "self",
        verbose_name=_("родительская категория"),
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
    )
    description = models.TextField(_("описание"), blank=True)
    is_active = models.BooleanField(_("активна"), default=True)

    created_at = models.DateTimeField(_("создана"), auto_now_add=True)
    updated_at = models.DateTimeField(_("обновлена"), auto_now=True)

    class Meta:
        verbose_name = _("категория")
        verbose_name_plural = _("категории")
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["parent", "name"],
                name="unique_category_name_per_parent",
            ),
        ]

    def __str__(self):
        if self.parent:
            return f"{self.parent} / {self.name}"
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = generate_unique_slug(self, self.name)
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.parent and self.parent.pk == self.pk:
            raise ValidationError({
                "parent": _("Категория не может быть родителем самой себя")
            })
        ancestor = self.parent
        while ancestor is not None:
            if ancestor.pk == self.pk:
                raise ValidationError({
                    "parent": _("Обнаружен цикл в иерархии категорий")
                })
            ancestor = ancestor.parent

    def get_absolute_url(self):
        return reverse("catalog:category_detail", kwargs={"slug": self.slug})

    def get_ancestors(self):
        """Список предков от корня к родителю — для breadcrumbs."""
        ancestors = []
        current = self.parent
        while current is not None:
            ancestors.append(current)
            current = current.parent
        return list(reversed(ancestors))


# ---------------------------------------------------------------------------
# Товар
# ---------------------------------------------------------------------------
class Product(models.Model):
    """
    Товар с четырьмя тирами цен.

    Цены (все Decimal, никогда Float):
    - price_retail — базовая, обязательная
    - price_opt1/2/3 — оптовые. Могут быть None: тогда применяется
      предыдущий тир (или розничная, если ни один опт не задан).
    """

    name = models.CharField(_("название"), max_length=255)
    slug = models.SlugField(
        _("slug"),
        max_length=255,
        unique=True,
        blank=True,
        help_text=_("URL-идентификатор. Заполнится автоматически из названия"),
    )
    sku = models.CharField(
        _("артикул"),
        max_length=50,
        unique=True,
        help_text=_("Внутренний артикул, например PKG-BOX-001"),
    )
    category = models.ForeignKey(
        Category,
        verbose_name=_("категория"),
        # PROTECT: нельзя удалить категорию, пока в ней есть товары.
        # Это защита от случайной потери данных — админ сначала
        # переносит или удаляет товары, потом удаляет категорию.
        on_delete=models.PROTECT,
        related_name="products",
    )
    description = models.TextField(_("описание"), blank=True)

    # ---- Цены ----
    # max_digits=10, decimal_places=2 → максимум 99 999 999.99 ₽.
    # НИКОГДА не Float — 0.1 + 0.2 = 0.30000000000000004 на float.
    price_retail = models.DecimalField(
        _("розничная цена"),
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    price_opt1 = models.DecimalField(
        _("цена при заказе от 10 000 ₽"),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Оставьте пустым, если опт не применяется"),
    )
    price_opt2 = models.DecimalField(
        _("цена при заказе от 30 000 ₽"),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )
    price_opt3 = models.DecimalField(
        _("цена при заказе от 60 000 ₽"),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )

    # ---- Склад и статус ----
    stock = models.PositiveIntegerField(_("остаток на складе"), default=0)
    is_active = models.BooleanField(_("активен"), default=True)

    created_at = models.DateTimeField(_("создан"), auto_now_add=True)
    updated_at = models.DateTimeField(_("обновлён"), auto_now=True)

    class Meta:
        verbose_name = _("товар")
        verbose_name_plural = _("товары")
        ordering = ["name"]
        indexes = [
            models.Index(fields=["category", "is_active"]),
            models.Index(fields=["is_active", "name"]),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = generate_unique_slug(self, self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("catalog:product_detail", kwargs={"slug": self.slug})

    # -----------------------------------------------------------------
    # Изображения
    # -----------------------------------------------------------------
    @property
    def main_image(self):
        """
        Главное изображение — первое по order.
        Возвращает ProductImage или None.
        """
        return self.images.first()

    # -----------------------------------------------------------------
    # Оптовые цены
    # -----------------------------------------------------------------
    def get_price_for_amount(self, base_amount):
        """
        Цена для этого товара при данной БАЗОВОЙ сумме корзины.

        base_amount — сумма корзины по РОЗНИЧНЫМ ценам (см. constants.py).
        """
        for threshold, field_name in WHOLESALE_TIERS:
            if base_amount >= threshold:
                price = getattr(self, field_name)
                # Явная проверка на None, а не `if price:`
                # Decimal("0") — falsy, но это валидная цена.
                if price is not None:
                    return price
        return self.price_retail

    def get_current_tier(self, base_amount):
        """
        Имя поля-цены, которое применится при base_amount.
        Например, "price_opt2". Для UI-плашки "применён Опт 2".
        """
        for threshold, field_name in WHOLESALE_TIERS:
            if base_amount >= threshold and getattr(self, field_name) is not None:
                return field_name
        return "price_retail"

    @property
    def is_in_stock(self):
        return self.stock > 0

    def clean(self):
        """
        Валидация:
        - Оптовые цены ≤ розничной.
        - Тиры убывают: opt3 ≤ opt2 ≤ opt1 ≤ розница.
        """
        super().clean()
        errors = {}

        for field_name in ("price_opt1", "price_opt2", "price_opt3"):
            price = getattr(self, field_name)
            if price is not None and price > self.price_retail:
                errors[field_name] = _(
                    "Оптовая цена не может быть выше розничной"
                )

        # Проверяем монотонность: opt1 → opt2 → opt3 должны убывать.
        chain = [
            ("price_opt1", self.price_opt1),
            ("price_opt2", self.price_opt2),
            ("price_opt3", self.price_opt3),
        ]
        prev_name, prev_price = None, None
        for name, price in chain:
            if price is None:
                continue
            if prev_price is not None and price > prev_price:
                errors[name] = _(
                    "Оптовая цена должна уменьшаться с ростом тира"
                )
            prev_name, prev_price = name, price

        if errors:
            raise ValidationError(errors)


# ---------------------------------------------------------------------------
# Изображение товара
# ---------------------------------------------------------------------------
class ProductImage(models.Model):
    """
    Изображение товара.

    Один товар — много изображений. Главное = первое по order.
    """

    product = models.ForeignKey(
        Product,
        verbose_name=_("товар"),
        on_delete=models.CASCADE,
        related_name="images",
    )
    image = models.ImageField(
        _("изображение"),
        upload_to="products/%Y/%m/",  # медиа раскидывается по годам/месяцам
    )
    alt = models.CharField(
        _("alt-текст"),
        max_length=255,
        blank=True,
        help_text=_("Описание для SEO и скринридеров"),
    )
    order = models.PositiveSmallIntegerField(_("порядок"), default=0)

    created_at = models.DateTimeField(_("загружено"), auto_now_add=True)

    class Meta:
        verbose_name = _("изображение товара")
        verbose_name_plural = _("изображения товаров")
        ordering = ["order", "id"]
        indexes = [
            models.Index(fields=["product", "order"]),
        ]

    def __str__(self):
        return f"Изображение для «{self.product.name}»"
    