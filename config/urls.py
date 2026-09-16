from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    # path("", include("apps.catalog.urls")),  # раскомментируем, когда создадим urls.py
    # path("users/", include("apps.users.urls")),
    # path("cart/", include("apps.cart.urls")),
    # path("orders/", include("apps.orders.urls")),
    # path("payments/", include("apps.payments.urls")),
    # path("api/", include("apps.api.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
