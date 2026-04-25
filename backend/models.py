from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

# Статусы, в которых может находиться заказанная корзина
STATE_CHOICES = (
    ("basket", "Статус корзины"),
    ("new", "Новый"),
    ("confirmed", "Подтвержден"),
    ("assembled", "Собран"),
    ("sent", "Отправлен"),
    ("delivered", "Доставлен"),
    ("canceled", "Отменен"),
)

# В нашей бизнес-логике всего 2 роли: поставщик и обычный покупатель
USER_TYPE_CHOICES = (
    ("shop", "Магазин"),
    ("buyer", "Покупатель"),
)


class UserManager(BaseUserManager):
    """
    Кастомный менеджер. Нужен для того, чтобы Django умел создавать
    пользователей (даже суперпользователя в консоли) не по логину, а строго по Email.
    """

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("Необходимо указать email")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Суперпользователь должен иметь is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Суперпользователь должен иметь is_superuser=True.")

        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    """
    Наша переопределенная модель Пользователя. Наследуемся от стандартного AbstractUser,
    чтобы не писать с нуля систему хеширования паролей и защищенных сессий.
    """

    REQUIRED_FIELDS = []
    objects = UserManager()
    USERNAME_FIELD = "email"

    email = models.EmailField(_("Электронная почта"), unique=True)
    company = models.CharField(verbose_name="Компания", max_length=40, blank=True)
    position = models.CharField(verbose_name="Должность", max_length=40, blank=True)

    username_validator = UnicodeUsernameValidator()
    username = models.CharField(
        _("Имя пользователя"),
        max_length=150,
        help_text=_("Обязательное поле. Не более 150 символов. Только буквы, цифры и символы @/./+/-/_."),
        validators=[username_validator],
        error_messages={
            "unique": _("Пользователь с таким именем уже существует."),
        },
    )

    # По умолчанию пользователь не активен
    # Он сможет войти в систему только после того, как перейдет по ссылке из Email-письма
    is_active = models.BooleanField(
        _("Активен"),
        default=False,
        help_text=_(
            "Указывает, следует ли считать этого пользователя активным. Снимите галочку вместо удаления аккаунтов."
        ),
    )
    type = models.CharField(verbose_name="Тип пользователя", choices=USER_TYPE_CHOICES, max_length=5, default="buyer")

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Список пользователей"
        ordering = ("email",)

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})"


class Shop(models.Model):
    name = models.CharField(max_length=50, verbose_name="Название")
    url = models.URLField(verbose_name="Ссылка", blank=True)

    user = models.OneToOneField(
        "User",
        verbose_name="Владелец",
        blank=True,
        null=True,
        on_delete=models.CASCADE,
    )
    state = models.BooleanField(verbose_name="Статус получения заказов", default=True)

    class Meta:
        verbose_name = "Магазин"
        verbose_name_plural = "Список магазинов"
        ordering = ("-name",)

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField(max_length=40, verbose_name="Название")
    shops = models.ManyToManyField(Shop, verbose_name="Магазины", related_name="categories", blank=True)

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Список категорий"
        ordering = ("-name",)

    def __str__(self):
        return self.name
