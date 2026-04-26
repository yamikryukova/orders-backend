from django.contrib.auth.password_validation import validate_password
from django.db import IntegrityError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.models import ConfirmEmailToken, User


class RegisterAccount(APIView):
    """
    Класс-представление для регистрации новых пользователей.
    Принимает POST-запрос с данными пользователя, валидирует пароль
    и создает неактивного пользователя в базе.
    (Сигнал new_user_registered сработает автоматически)
    """

    def post(self, request, *args, **kwargs):
        # Проверяем, что переданы все нужные поля
        required_fields = {"first_name", "last_name", "email", "password", "company", "position"}
        if required_fields.issubset(request.data.keys()):
            # Проверяем сложность пароля средствами Django
            try:
                validate_password(request.data["password"])
            except Exception as password_error:
                error_array = list(password_error)
                return Response(
                    {"Status": False, "Errors": {"password": error_array}}, status=status.HTTP_400_BAD_REQUEST
                )
            else:
                # Пароль прошел проверку, пытаемся создать пользователя
                try:
                    user = User.objects.create(
                        first_name=request.data["first_name"],
                        last_name=request.data["last_name"],
                        email=request.data["email"],
                        username=request.data["email"],
                        company=request.data["company"],
                        position=request.data["position"],
                        type=request.data.get("type", "buyer"),
                    )
                    user.set_password(request.data["password"])
                    user.save()
                    return Response(
                        {"Status": True, "Message": "Пользователь успешно создан! Подтвердите email."},
                        status=status.HTTP_201_CREATED,
                    )
                except IntegrityError:
                    return Response(
                        {"Status": False, "Errors": f"Пользователь с email {request.data['email']} уже существует!"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

        return Response(
            {"Status": False, "Errors": "Не указаны все обязательные аргументы"}, status=status.HTTP_400_BAD_REQUEST
        )


class ConfirmAccount(APIView):
    """
    Класс-представление для подтверждения почты по токену.
    Мы отправляли этот токен письмом при регистрации.
    """

    def post(self, request, *args, **kwargs):
        # Ожидаем email и token
        if {"email", "token"}.issubset(request.data.keys()):
            token = ConfirmEmailToken.objects.filter(
                user__email=request.data["email"], key=request.data["token"]
            ).first()

            if token:
                # Если токен найден - активируем пользователя
                token.user.is_active = True
                token.user.save()
                token.delete()
                return Response({"Status": True, "Message": "Аккаунт успешно подтвержден!"})
            else:
                return Response(
                    {"Status": False, "Errors": "Неправильно указан токен или email"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return Response({"Status": False, "Errors": "Не указаны email и/или token"}, status=status.HTTP_400_BAD_REQUEST)
