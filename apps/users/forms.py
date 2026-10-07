"""
Формы для приложения users.

Здесь три формы:
1. RegisterForm       — регистрация (телефон + пароль)
2. PhoneLoginForm     — логин (телефон + пароль)
3. ProfileCompleteForm — заполнение профиля после регистрации
"""

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

# get_user_model() — правильный способ получить модель пользователя.
# НЕ импортируем User напрямую, потому что модель может быть переопределена.
User = get_user_model()


class RegisterForm(forms.ModelForm):
    """
    Форма регистрации.

    При регистрации запрашиваем ТОЛЬКО телефон и пароль.
    Email, имя, фамилию пользователь заполнит позже в личном кабинете.
    """

    # Пароли не хранятся в модели напрямую, поэтому объявляем их как поля формы.
    # PasswordInput — виджет, который скрывает вводимые символы.
    password1 = forms.CharField(
        label=_("Пароль"),
        widget=forms.PasswordInput(attrs={
            "class": "form-input",
            "placeholder": "Минимум 8 символов",
            "autocomplete": "new-password",
        }),
        help_text=_("Минимум 8 символов"),
    )
    password2 = forms.CharField(
        label=_("Повторите пароль"),
        widget=forms.PasswordInput(attrs={
            "class": "form-input",
            "placeholder": "Повторите пароль",
            "autocomplete": "new-password",
        }),
    )

    class Meta:
        model = User
        # Указываем, какие поля модели показывать в форме.
        # Только phone — остальное заполнится позже.
        fields = ("phone",)
        widgets = {
            "phone": forms.TextInput(attrs={
                "class": "form-input",
                "placeholder": "+7XXXXXXXXXX",
                "autocomplete": "tel",
            }),
        }

    def clean_phone(self):
        """
        Валидация телефона.

        Проверяем:
        1. Что такой телефон ещё не занят (уникальность).
        2. Базовая нормализация (убираем пробелы, скобки, дефисы).
        """
        phone = self.cleaned_data.get("phone", "").strip()

        # Простая нормализация: убираем всё, кроме цифр и знака +
        # Например: "+7 (999) 123-45-67" → "+79991234567"
        # Это черновая версия — позже сделаем нормальную через phonenumbers.
        normalized = "+" + "".join(c for c in phone if c.isdigit())

        # Проверяем, что телефон не занят
        if User.objects.filter(phone=normalized).exists():
            raise ValidationError(_("Пользователь с таким телефоном уже зарегистрирован"))

        return normalized

    def clean(self):
        """
        Общая валидация формы — вызывается после clean_<field>.

        Здесь проверяем, что password1 == password2.
        """
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")

        if password1 and password2 and password1 != password2:
            # add_error добавляет ошибку к конкретному полю,
            # чтобы пользователь видел её рядом с нужным input'ом.
            self.add_error("password2", _("Пароли не совпадают"))

        return cleaned_data

    def save(self, commit=True):
        """
        Сохраняем пользователя.

        Отличие от стандартного ModelForm.save():
        - Пароль нужно хэшировать через set_password(), а не сохранять как есть.
        - По умолчанию commit=True, но иногда нужно commit=False
          (например, чтобы добавить поля перед сохранением).
        """
        user = super().save(commit=False)
        # set_password хэширует пароль — НИКОГДА не сохраняем пароль открытым текстом!
        user.set_password(self.cleaned_data["password1"])

        if commit:
            user.save()

        return user


class PhoneLoginForm(AuthenticationForm):
    """
    Форма логина.

    Наследуемся от стандартной AuthenticationForm, но:
    - Меняем поле username на phone
    - Меняем label и widget
    """

    username = forms.CharField(
        label=_("Телефон"),
        widget=forms.TextInput(attrs={
            "class": "form-input",
            "placeholder": "+7XXXXXXXXXX",
            "autocomplete": "tel",
            "autofocus": True,
        }),
    )
    password = forms.CharField(
        label=_("Пароль"),
        widget=forms.PasswordInput(attrs={
            "class": "form-input",
            "placeholder": "Пароль",
            "autocomplete": "current-password",
        }),
    )

    def clean_username(self):
        """
        Нормализуем телефон перед проверкой.

        Django AuthenticationForm передаёт username в authenticate(),
        а наш backend ищет по точному совпадению phone.
        Поэтому нормализуем так же, как при регистрации.
        """
        username = self.cleaned_data.get("username", "").strip()
        normalized = "+" + "".join(c for c in username if c.isdigit())
        return normalized


class ProfileCompleteForm(forms.ModelForm):
    """
    Форма заполнения профиля после регистрации.

    Обязательные поля: email, first_name.
    Опциональные: last_name, birth_date.
    """

    class Meta:
        model = User
        fields = ("email", "first_name", "last_name", "birth_date")
        widgets = {
            "email": forms.EmailInput(attrs={
                "class": "form-input",
                "placeholder": "you@example.com",
                "autocomplete": "email",
            }),
            "first_name": forms.TextInput(attrs={
                "class": "form-input",
                "placeholder": "Иван",
                "autocomplete": "given-name",
            }),
            "last_name": forms.TextInput(attrs={
                "class": "form-input",
                "placeholder": "Иванов",
                "autocomplete": "family-name",
            }),
            "birth_date": forms.DateInput(attrs={
                "class": "form-input",
                "type": "date",  # HTML5 datepicker
            }),
        }
        labels = {
            "email": _("Email"),
            "first_name": _("Имя"),
            "last_name": _("Фамилия"),
            "birth_date": _("Дата рождения"),
        }

    def __init__(self, *args, **kwargs):
        """
        Делаем email и first_name обязательными НА УРОВНЕ ФОРМЫ.

        В модели они не обязательны (потому что при регистрации
        пользователь их не заполняет). Но когда он доходит до этой формы,
        мы требуем их заполнить.
        """
        super().__init__(*args, **kwargs)
        self.fields["email"].required = True
        self.fields["first_name"].required = True
        self.fields["last_name"].required = False
        self.fields["birth_date"].required = False

    def clean_email(self):
        """
        Проверяем, что email не занят другим пользователем.

        У поля в модели unique=True, но это работает только на уровне БД
        и бросает IntegrityError, а не понятную ошибку. Валидируем явно.
        """
        email = self.cleaned_data.get("email", "").strip().lower()

        # Исключаем самого пользователя (self.instance), чтобы он мог
        # сохранить форму без изменений
        qs = User.objects.filter(email__iexact=email)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise ValidationError(_("Этот email уже используется"))

        return email

    def save(self, commit=True):
        """
        Сохраняем профиль и обновляем флаг profile_completed.
        """
        user = super().save(commit=False)

        # Пересчитываем флаг: если email и first_name заполнены — True
        user.profile_completed = bool(user.email and user.first_name)

        if commit:
            user.save()

        return user
