from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.dispatch import Signal, receiver
from django_rest_passwordreset.signals import reset_password_token_created

from backend.models import ConfirmEmailToken, Order, OrderStatus, User

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
    Обработчик сигнала: Отправляем письмо-подтверждение покупателю
    и накладную на email администратора для исполнения заказа.
    """
    user = User.objects.get(id=user_id)

    # --- Письмо покупателю (подтверждение) ---
    msg = EmailMultiAlternatives(
        subject="Обновление статуса заказа",
        body="Ваш заказ успешно сформирован и ожидает обработки!",
        from_email=settings.EMAIL_HOST_USER,
        to=[user.email],
    )
    msg.send()

    # --- Накладная администратору ---
    # Находим последний оформленный заказ пользователя (статус 'new')
    order = (
        Order.objects.filter(user=user, state=OrderStatus.NEW)
        .prefetch_related("ordered_items__product_info__product")
        .order_by("-dt")
        .first()
    )

    if order:
        # Формируем текст накладной с перечнем товаров
        lines = [
            f"Накладная по заказу #{order.id}",
            f"Дата: {order.dt:%d.%m.%Y %H:%M}",
            f"Покупатель: {user.first_name} {user.last_name} ({user.email})",
            "",
        ]

        # Адрес доставки
        if order.contact:
            lines.append(
                f"Адрес доставки: г. {order.contact.city}, ул. {order.contact.street}, д. {order.contact.house}"
            )
            lines.append(f"Телефон: {order.contact.phone}")
            lines.append("")

        # Таблица позиций
        lines.append("Позиции заказа:")
        lines.append("-" * 40)
        total = 0
        for item in order.ordered_items.all():
            subtotal = item.quantity * item.product_info.price
            total += subtotal
            lines.append(
                f"  {item.product_info.product.name} — "
                f"{item.quantity} шт. x {item.product_info.price} руб. = {subtotal} руб."
            )
        lines.append("-" * 40)
        lines.append(f"ИТОГО: {total} руб.")

        admin_msg = EmailMultiAlternatives(
            subject=f"Новый заказ #{order.id} — накладная для исполнения",
            body="\n".join(lines),
            from_email=settings.EMAIL_HOST_USER,
            to=[settings.ADMIN_EMAIL],
        )
        admin_msg.send()


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
