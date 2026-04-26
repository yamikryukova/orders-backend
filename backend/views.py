from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.db import IntegrityError
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.models import Category, ConfirmEmailToken, ProductInfo, Shop, User
from backend.serializers import CategorySerializer, ProductInfoSerializer, ShopSerializer, UserSerializer


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


class CategoryView(ListAPIView):
    """
    Класс-представление для просмотра списка категорий.
    Используем встроенный ListAPIView, так как это просто GET-список без сложной логики.
    """

    queryset = Category.objects.all()
    serializer_class = CategorySerializer


class ShopView(ListAPIView):
    """
    Класс-представление для просмотра списка магазинов.
    Возвращаем только те магазины, где state=True (они принимают заказы).
    """

    queryset = Shop.objects.filter(state=True)
    serializer_class = ShopSerializer


class ProductInfoView(APIView):
    """
    Класс-представление для поиска товаров.
    Тут мы используем APIView, чтобы удобно вручную прописать фильтры по GET-параметрам.
    """

    def get(self, request, *args, **kwargs):
        # Стартовый QuerySet — выдаем информацию о товарах только из активных магазинов
        query = ProductInfo.objects.filter(shop__state=True)

        shop_id = request.query_params.get("shop_id")
        category_id = request.query_params.get("category_id")

        # Применяем фильтры, если юзер передал их в URL
        if shop_id:
            query = query.filter(shop_id=shop_id)

        if category_id:
            query = query.filter(product__category_id=category_id)

        # ОПТИМИЗАЦИЯ БД (чтобы не было проблемы N+1 запросов):
        # Подтягиваем связанные таблицы в один SQL-запрос
        query = (
            query.select_related("shop", "product__category")
            .prefetch_related("product_parameters__parameter")
            .distinct()
        )

        serializer = ProductInfoSerializer(query, many=True)
        return Response(serializer.data)
