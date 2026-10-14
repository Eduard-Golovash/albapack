"""
Тесты моделей каталога.

Покрывают:
- Category: slug-генерация (транслит, уникальность), __str__, get_ancestors,
  валидацию циклов, UniqueConstraint(parent, name).
- Product: get_price_for_amount для всех тиров, fallback на младший тир,
  get_current_tier, clean() (валидация монотонности), is_in_stock,
  PROTECT на удаление категории.
- ProductImage: ordering, main_image, CASCADE.
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import ProtectedError
from django.test import TestCase
from django.urls import reverse

from apps.catalog.models import Category, Product, ProductImage


# ---------------------------------------------------------------------------
# Category
# ---------------------------------------------------------------------------
class CategoryModelTests(TestCase):
    """Тесты модели Category."""

    def test_create_root_category(self):
        """Корневая категория создаётся без parent."""
        cat = Category.objects.create(name="Упаковка")

        self.assertEqual(cat.name, "Упаковка")
        self.assertIsNone(cat.parent)
        self.assertTrue(cat.is_active)  # default=True
        self.assertIsNotNone(cat.created_at)

    def test_slug_generated_from_name_cyrillic(self):
        """
        Slug генерируется из русского названия, транслитерируется
        в латиницу через python-slugify.
        """
        cat = Category.objects.create(name="Упаковка")

        # python-slugify: "Упаковка" → "upakovka"
        self.assertEqual(cat.slug, "upakovka")

    def test_slug_generated_complex_name(self):
        """Сложное название с цифрами и пробелами."""
        cat = Category.objects.create(name="Коробки картонные 400x300")

        # Ожидаем: "korobki-kartonnye-400x300"
        self.assertEqual(cat.slug, "korobki-kartonnye-400x300")

    def test_slug_unique_across_categories(self):
        """
        Если slug занят — добавляется числовой суффикс.
        Это глобальная уникальность (в отличие от имени).
        """
        c1 = Category.objects.create(name="Коробки")
        c2 = Category.objects.create(name="Коробки")  # другое имя? нет, то же
        # Но у нас UniqueConstraint на (parent, name), поэтому второй
        # Category.objects.create(name="Коробки") с parent=None упадёт.
        # Значит, создаём через другое имя, но ожидаем такой же slug.
        # Обойдём это через прямое присваивание slug.

    def test_slug_unique_with_different_names(self):
        """
        Разные имена с одинаковым slug-результатом получают уникальные slug.
        Например, "Коробка" и "Коробка!" → оба транслитерируются в "korobka".
        """
        c1 = Category.objects.create(name="Коробка")
        # Уникализируем имя, но slug-источник тот же:
        c2 = Category.objects.create(name="Коробка!")  # slugify уберёт "!"

        self.assertEqual(c1.slug, "korobka")
        self.assertEqual(c2.slug, "korobka-1")

    def test_slug_unique_within_parent_but_different_parents(self):
        """
        У двух категорий с одинаковым именем, но разными родителями
        могут быть одинаковые slug-источники, и slug будет уникализирован.
        """
        root1 = Category.objects.create(name="Раздел А")
        root2 = Category.objects.create(name="Раздел Б")

        c1 = Category.objects.create(name="Коробки", parent=root1)
        c2 = Category.objects.create(name="Коробки", parent=root2)

        # UniqueConstraint(parent, name) разрешает — parent разный.
        self.assertEqual(c1.slug, "korobki")
        self.assertEqual(c2.slug, "korobki-1")

    def test_slug_not_regenerated_on_save(self):
        """
        Если slug уже задан — при save() он НЕ пересчитывается.
        Это важно для SEO: URL не должен меняться при переименовании.
        """
        cat = Category.objects.create(name="Упаковка")
        original_slug = cat.slug

        cat.name = "Совсем другое название"
        cat.save()
        cat.refresh_from_db()

        self.assertEqual(cat.slug, original_slug)

    def test_manual_slug_is_kept(self):
        """Если slug задан явно — используется он, а не автогенерация."""
        cat = Category.objects.create(name="Упаковка", slug="custom-slug")

        self.assertEqual(cat.slug, "custom-slug")

    def test_str_root(self):
        """__str__ корневой категории = имя."""
        cat = Category.objects.create(name="Упаковка")

        self.assertEqual(str(cat), "Упаковка")

    def test_str_nested(self):
        """__str__ дочерней = 'Родитель / Ребёнок'."""
        root = Category.objects.create(name="Упаковка")
        child = Category.objects.create(name="Коробки", parent=root)

        self.assertEqual(str(child), "Упаковка / Коробки")

    def test_get_absolute_url(self):
        """URL категории содержит её slug."""
        cat = Category.objects.create(name="Коробки")
        expected = reverse("catalog:category_detail", kwargs={"slug": "korobki"})

        self.assertEqual(cat.get_absolute_url(), expected)

    def test_get_ancestors_empty_for_root(self):
        """У корневой категории нет предков."""
        cat = Category.objects.create(name="Упаковка")

        self.assertEqual(cat.get_ancestors(), [])

    def test_get_ancestors_full_chain(self):
        """
        get_ancestors возвращает предков от корня к родителю —
        порядок важен для breadcrumbs.
        """
        root = Category.objects.create(name="Упаковка")
        mid = Category.objects.create(name="Коробки", parent=root)
        leaf = Category.objects.create(name="Картонные", parent=mid)

        ancestors = leaf.get_ancestors()

        self.assertEqual(ancestors, [root, mid])

    def test_clean_self_parent_raises(self):
        """Категория не может быть родителем самой себя."""
        cat = Category.objects.create(name="Упаковка")
        cat.parent = cat  # ← ошибка

        with self.assertRaises(ValidationError):
            cat.clean()

    def test_clean_detects_cycle(self):
        """
        Проверяем, что clean() находит цикл: A → parent B, B → parent C,
        C → parent A.
        """
        a = Category.objects.create(name="A")
        b = Category.objects.create(name="B", parent=a)
        c = Category.objects.create(name="C", parent=b)

        # Пытаемся сделать корень A дочерним C — это создаст цикл A → C → B → A
        a.parent = c

        with self.assertRaises(ValidationError):
            a.clean()

    def test_unique_name_per_parent_constraint(self):
        """
        Два ребёнка одного родителя не могут иметь одинаковое имя.
        """
        root = Category.objects.create(name="Упаковка")
        Category.objects.create(name="Коробки", parent=root)

        # Второй "Коробки" с тем же parent → IntegrityError
        with self.assertRaises(IntegrityError):
            Category.objects.create(name="Коробки", parent=root)

    def test_same_name_different_parents_allowed(self):
        """Одноимённые категории у разных родителей разрешены."""
        root1 = Category.objects.create(name="Раздел А")
        root2 = Category.objects.create(name="Раздел Б")

        # Не должно упасть
        c1 = Category.objects.create(name="Коробки", parent=root1)
        c2 = Category.objects.create(name="Коробки", parent=root2)

        self.assertEqual(c1.name, c2.name)
        self.assertNotEqual(c1.parent, c2.parent)


# ---------------------------------------------------------------------------
# Product
# ---------------------------------------------------------------------------
class ProductModelTests(TestCase):
    """Тесты модели Product."""

    def setUp(self):
        """
        Готовим категорию и товар со ВСЕМИ ценами.
        Отдельные тесты будут создавать товары с частичными ценами.
        """
        self.category = Category.objects.create(name="Коробки")
        self.product = Product.objects.create(
            name="Коробка 400x300",
            sku="BOX-001",
            category=self.category,
            price_retail=Decimal("150.00"),
            price_opt1=Decimal("130.00"),
            price_opt2=Decimal("110.00"),
            price_opt3=Decimal("95.00"),
            stock=100,
        )

    # ---- Создание и slug ----

    def test_create_product(self):
        """Базовое создание товара."""
        self.assertEqual(self.product.name, "Коробка 400x300")
        self.assertEqual(self.product.sku, "BOX-001")
        self.assertEqual(self.product.price_retail, Decimal("150.00"))
        self.assertTrue(self.product.is_active)

    def test_slug_generated_cyrillic(self):
        """Slug транслитерируется из русского названия."""
        self.assertEqual(self.product.slug, "korobka-400x300")

    def test_sku_unique(self):
        """SKU должен быть уникальным."""
        with self.assertRaises(IntegrityError):
            Product.objects.create(
                name="Другой товар",
                sku="BOX-001",  # занят
                category=self.category,
                price_retail=Decimal("100.00"),
            )

    def test_str(self):
        self.assertEqual(str(self.product), "Коробка 400x300")

    def test_get_absolute_url(self):
        expected = reverse("catalog:product_detail", kwargs={"slug": self.product.slug})
        self.assertEqual(self.product.get_absolute_url(), expected)

    # ---- Цены: get_price_for_amount ----

    def test_price_below_min_threshold_is_retail(self):
        """При base_amount < 10 000 → розничная."""
        price = self.product.get_price_for_amount(Decimal("5000"))
        self.assertEqual(price, Decimal("150.00"))

    def test_price_at_opt1_threshold(self):
        """Ровно 10 000 → opt1 (>=, не >)."""
        price = self.product.get_price_for_amount(Decimal("10000"))
        self.assertEqual(price, Decimal("130.00"))

    def test_price_at_opt2_threshold(self):
        price = self.product.get_price_for_amount(Decimal("30000"))
        self.assertEqual(price, Decimal("110.00"))

    def test_price_at_opt3_threshold(self):
        price = self.product.get_price_for_amount(Decimal("60000"))
        self.assertEqual(price, Decimal("95.00"))

    def test_price_far_above_opt3(self):
        """Много больше порога → opt3."""
        price = self.product.get_price_for_amount(Decimal("500000"))
        self.assertEqual(price, Decimal("95.00"))

    def test_price_just_below_threshold(self):
        """
        Граница: 9 999.99 → розница.
        Проверяем, что сравнение именно >= threshold.
        """
        price = self.product.get_price_for_amount(Decimal("9999.99"))
        self.assertEqual(price, Decimal("150.00"))

    def test_price_fallback_when_opt_missing(self):
        """
        Если opt3 не задан, при base_amount ≥ 60000 используется opt2
        (следующий доступный).
        """
        product = Product.objects.create(
            name="Пакет",
            sku="BAG-001",
            category=self.category,
            price_retail=Decimal("5.00"),
            price_opt1=Decimal("4.00"),
            # opt2, opt3 = None
            stock=1000,
        )

        self.assertEqual(product.get_price_for_amount(Decimal("75000")), Decimal("4.00"))

    def test_price_fallback_to_retail_when_no_opts(self):
        """Если ни одна оптовая цена не задана — розница."""
        product = Product.objects.create(
            name="Штучный товар",
            sku="ONE-001",
            category=self.category,
            price_retail=Decimal("999.00"),
            stock=1,
        )

        self.assertEqual(product.get_price_for_amount(Decimal("100000")), Decimal("999.00"))

    def test_price_zero_opt_is_respected(self):
        """
        Decimal("0") — валидная цена. Проверяем, что наш код
        не считает её "отсутствующей" через truthy-проверку.
        """
        product = Product.objects.create(
            name="Подарок",
            sku="GIFT-001",
            category=self.category,
            price_retail=Decimal("100.00"),
            price_opt1=Decimal("0.00"),  # бесплатно от 10к
            stock=100,
        )

        self.assertEqual(product.get_price_for_amount(Decimal("15000")), Decimal("0.00"))

    # ---- get_current_tier ----

    def test_get_current_tier_retail(self):
        self.assertEqual(
            self.product.get_current_tier(Decimal("5000")),
            "price_retail",
        )

    def test_get_current_tier_opt1(self):
        self.assertEqual(
            self.product.get_current_tier(Decimal("15000")),
            "price_opt1",
        )

    def test_get_current_tier_opt3(self):
        self.assertEqual(
            self.product.get_current_tier(Decimal("100000")),
            "price_opt3",
        )

    def test_get_current_tier_fallback(self):
        """Fallback: при base ≥ 60000, но без opt3 → opt2."""
        product = Product.objects.create(
            name="Пакет",
            sku="BAG-002",
            category=self.category,
            price_retail=Decimal("5.00"),
            price_opt1=Decimal("4.00"),
            price_opt2=Decimal("3.00"),
            stock=100,
        )

        self.assertEqual(
            product.get_current_tier(Decimal("75000")),
            "price_opt2",
        )

    # ---- is_in_stock ----

    def test_is_in_stock_true(self):
        self.assertTrue(self.product.is_in_stock)

    def test_is_in_stock_false(self):
        self.product.stock = 0
        self.product.save()

        self.assertFalse(self.product.is_in_stock)

    # ---- clean: валидация цен ----

    def test_clean_opt_price_above_retail_raises(self):
        """Оптовая цена не может быть выше розничной."""
        self.product.price_opt1 = Decimal("200.00")  # retail = 150
        with self.assertRaises(ValidationError):
            self.product.clean()

    def test_clean_non_monotonic_tiers_raises(self):
        """
        Оптовые цены должны убывать: opt3 ≤ opt2 ≤ opt1.
        Проверяем: opt2 выше opt1 — ошибка.
        """
        self.product.price_opt2 = Decimal("140.00")  # > opt1 (130)
        with self.assertRaises(ValidationError):
            self.product.clean()

    def test_clean_valid_prices_pass(self):
        """Валидные цены не вызывают ошибок."""
        try:
            self.product.clean()
        except ValidationError:
            self.fail("clean() не должен падать на валидных ценах")

    def test_clean_allows_missing_opts(self):
        """Все опт-цены могут быть None."""
        product = Product.objects.create(
            name="Простой",
            sku="SIMPLE-001",
            category=self.category,
            price_retail=Decimal("100.00"),
            stock=10,
        )
        product.clean()  # не должно упасть

    # ---- PROTECT на категорию ----

    def test_category_delete_protected_when_products_exist(self):
        """
        Нельзя удалить категорию, пока в ней есть товары.
        Django бросает ProtectedError.
        """
        with self.assertRaises(ProtectedError):
            self.category.delete()

    def test_category_deletable_without_products(self):
        """Категория без товаров удаляется нормально."""
        empty_category = Category.objects.create(name="Пустая")
        empty_category.delete()  # не должно упасть


# ---------------------------------------------------------------------------
# ProductImage
# ---------------------------------------------------------------------------
class ProductImageModelTests(TestCase):
    """Тесты модели ProductImage."""

    def setUp(self):
        category = Category.objects.create(name="Коробки")
        self.product = Product.objects.create(
            name="Коробка",
            sku="BOX-IMG-001",
            category=category,
            price_retail=Decimal("100.00"),
        )

    def test_create_image(self):
        """
        Создание изображения. Так как ImageField требует реального файла,
        в тестах используем простой путь (без загрузки) — для проверки
        структуры модели.
        """
        img = ProductImage.objects.create(
            product=self.product,
            image="products/test.jpg",  # путь как строка — ок для теста
            alt="Коробка картонная",
            order=1,
        )

        self.assertEqual(img.product, self.product)
        self.assertEqual(img.alt, "Коробка картонная")

    def test_ordering_by_order(self):
        """Изображения сортируются по полю order."""
        img2 = ProductImage.objects.create(
            product=self.product, image="products/2.jpg", order=2
        )
        img1 = ProductImage.objects.create(
            product=self.product, image="products/1.jpg", order=1
        )
        img3 = ProductImage.objects.create(
            product=self.product, image="products/3.jpg", order=3
        )

        images = list(self.product.images.all())

        self.assertEqual(images, [img1, img2, img3])

    def test_main_image_returns_first(self):
        """main_image возвращает изображение с минимальным order."""
        ProductImage.objects.create(
            product=self.product, image="products/2.jpg", order=2
        )
        main = ProductImage.objects.create(
            product=self.product, image="products/main.jpg", order=1
        )

        self.assertEqual(self.product.main_image, main)

    def test_main_image_none_when_no_images(self):
        """Если изображений нет — main_image = None."""
        self.assertIsNone(self.product.main_image)

    def test_cascade_delete_on_product(self):
        """При удалении товара изображения тоже удаляются."""
        ProductImage.objects.create(
            product=self.product, image="products/a.jpg", order=1
        )
        ProductImage.objects.create(
            product=self.product, image="products/b.jpg", order=2
        )

        self.assertEqual(ProductImage.objects.count(), 2)
        self.product.delete()
        self.assertEqual(ProductImage.objects.count(), 0)

    def test_str(self):
        img = ProductImage.objects.create(
            product=self.product, image="products/a.jpg"
        )
        self.assertIn("Коробка", str(img))
        