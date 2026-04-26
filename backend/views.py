from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.db import IntegrityError
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.models import ConfirmEmailToken, User
from backend.serializers import UserSerializer


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


class LoginAccount(APIView):
    """
    Класс-представление для авторизации пользователей.
    Принимает email и пароль, возвращает Token.
    """

    def post(self, request, *args, **kwargs):
        if {"email", "password"}.issubset(request.data.keys()):
            # Джанговский authenticate ожидает kwarg username (который у нас email)
            user = authenticate(request, username=request.data["email"], password=request.data["password"])

            if user is not None:
                if user.is_active:
                    token, _ = Token.objects.get_or_create(user=user)
                    return Response({"Status": True, "Token": token.key})
                else:
                    return Response(
                        {"Status": False, "Errors": "Аккаунт не подтвержден. Проверьте email."},
                        status=status.HTTP_403_FORBIDDEN,
                    )

            return Response(
                {"Status": False, "Errors": "Не удалось авторизоваться: неверный email или пароль"},
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response(
            {"Status": False, "Errors": "Не указаны обязательные поля email и password"},
            status=status.HTTP_400_BAD_REQUEST,
        )


class AccountDetails(APIView):
    """
    Класс-представление для работы с профилем самого пользователя.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        # Поскольку у нас стоит IsAuthenticated, request.user будет гарантированно существовать
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        # partial=True говорит сериализатору, что можно обновлять поля поштучно
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            # Это обновит только те поля, которые пришли в request.data
            serializer.save()
            # Если придет пароль, то его нужно будет хешировать (сейчас это упущено для простоты,
            # но в идеале смена пароля - это отдельный эндпоинт)
            return Response({"Status": True}, status=status.HTTP_200_OK)

        return Response({"Status": False, "Errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
