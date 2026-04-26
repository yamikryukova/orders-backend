import contextlib

from django.apps import AppConfig


class BackendConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend"

    def ready(self):
        """
        Метод ready() вызывается при старте приложения.
        Здесь мы импортируем файл с сигналами, чтобы Django знал об их существовании
        и навесил декораторы @receiver до того, как пользователи начнут регистрироваться.
        """
        with contextlib.suppress(ImportError):
            import backend.signals  # noqa: F401
