import os

from celery import Celery

# 1. Говорим Celery, где лежат настройки Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

## 2. Создаём экземпляр Celery с именем проект
app = Celery("albapack")
# 3. Читаем настройки Celery из settings.py (с префиксом CELERY_)
app.config_from_object("django.conf:settings", namespace="CELERY")
# 4. Автоматически находим задачи (tasks.py) во всех INSTALLED_APPS
app.autodiscover_tasks()
