from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.dispatch import Signal, receiver
from django_rest_passwordreset.signals import reset_password_token_created

from backend.models import ConfirmEmailToken, User

# Создаем свои кастомные сигналы для бизнес-логики магазина
new_user_registered = Signal()
new_order = Signal()


@receiver(new_user_registered)
def new_user_registered_signal(user_id, **kwargs):
    """
    Обработчик сигнала: Отправляем письмо с подтверждением почты
    сразу после успешной регистрации пользователя.
    """
    # Получаем пользователя по ID, который прилетел в сигнале
    user = User.objects.get(id=user_id)
    # Генерируем новый токен
    token, _ = ConfirmEmailToken.objects.get_or_create(user_id=user.id)

    # Формируем и отправляем письмо
    msg = EmailMultiAlternatives(
        subject=f"Подтверждение электронной почты {user.email}",
        body=f"Для подтверждения почты используйте токен: {token.key}",
        from_email=settings.EMAIL_HOST_USER,
        to=[user.email],
    )
    msg.send()


@receiver(new_order)
def new_order_signal(user_id, **kwargs):
    """
    Обработчик сигнала: Отправляем письмо пользователю,
    когда он успешно оформил новый заказ.
    """
    user = User.objects.get(id=user_id)

    msg = EmailMultiAlternatives(
        subject="Обновление статуса заказа",
        body="Ваш заказ успешно сформирован и ожидает обработки!",
        from_email=settings.EMAIL_HOST_USER,
        to=[user.email],
    )
    msg.send()


@receiver(reset_password_token_created)
def password_reset_token_created(sender, instance, reset_password_token, **kwargs):
    """
    Отправляем письмо с токеном для сброса пароля.
    Сигнал встроен в библиотеку django_rest_passwordreset.
    """
    msg = EmailMultiAlternatives(
        subject=f"Сброс пароля для {reset_password_token.user.email}",
        body=f"Ваш токен для сброса пароля: {reset_password_token.key}",
        from_email=settings.EMAIL_HOST_USER,
        to=[reset_password_token.user.email],
    )
    msg.send()
