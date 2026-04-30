import requests
import yaml
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import IntegrityError
from django.db.models import F, Sum
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from yaml import Loader

from backend.models import (
    Category,
    ConfirmEmailToken,
    Contact,
    Order,
    OrderItem,
    OrderStatus,
    Parameter,
    Product,
    ProductInfo,
    ProductParameter,
    Shop,
    User,
    UserType,
)
from backend.serializers import (
    CategorySerializer,
    ContactSerializer,
    OrderItemSerializer,
    OrderSerializer,
    ProductInfoSerializer,
    ShopSerializer,
    UserSerializer,
)
from backend.signals import new_user_registered


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
                        type=request.data.get("type", UserType.BUYER),
                    )
                    user.set_password(request.data["password"])
                    user.save()

                    new_user_registered.send(sender=self.__class__, user_id=user.id)

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


class ContactView(APIView):
    """
    Класс-представление для работы с адресами доставки (контактами) пользователя.
    Поддерживает полный CRUD (Создание, Чтение, Обновление, Удаление).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        # Отдаем контакты только текущего пользователя
        contacts = Contact.objects.filter(user=request.user)
        serializer = ContactSerializer(contacts, many=True)
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        serializer = ContactSerializer(data=request.data)
        if serializer.is_valid():
            # Привязываем контакт к текущему авторизованному юзеру
            serializer.save(user=request.user)
            return Response({"Status": True}, status=status.HTTP_201_CREATED)
        return Response({"Status": False, "Errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, *args, **kwargs):
        contact_id = request.data.get("id")
        if not contact_id:
            return Response(
                {"Status": False, "Errors": "Не указан id контакта (поле id)"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Проверяем, что чужой контакт не редактируют
            contact = Contact.objects.get(id=contact_id, user=request.user)
        except Contact.DoesNotExist:
            return Response({"Status": False, "Errors": "Контакт не найден"}, status=status.HTTP_404_NOT_FOUND)

        serializer = ContactSerializer(contact, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({"Status": True}, status=status.HTTP_200_OK)
        return Response({"Status": False, "Errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, *args, **kwargs):
        # Удаление может приходить списком id, например items="1,2,3"
        items = request.data.get("items")
        if items:
            items_list = items.split(",")
            # Фильтруем по user=request.user, защита от хакеров
            deleted_count, _ = Contact.objects.filter(id__in=items_list, user=request.user).delete()
            if deleted_count > 0:
                return Response({"Status": True, "Удалено": deleted_count}, status=status.HTTP_200_OK)
            return Response({"Status": False, "Errors": "Контакты не найдены"}, status=status.HTTP_404_NOT_FOUND)

        return Response(
            {"Status": False, "Errors": "Не переданы id контактов (поле items)"}, status=status.HTTP_400_BAD_REQUEST
        )


class BasketView(APIView):
    """
    Класс-представление для работы с корзиной пользователя.
    Корзина — это просто объект Order со статусом 'basket'.
    Поддерживает добавление/удаление/изменение товаров в корзине.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        # Находим корзину юзера и считаем общую сумму через annotate
        basket = (
            Order.objects.filter(user=request.user, state=OrderStatus.BASKET)
            .prefetch_related(
                "ordered_items__product_info__product__category",
                "ordered_items__product_info__product_parameters__parameter",
            )
            .annotate(total_sum=Sum(F("ordered_items__quantity") * F("ordered_items__product_info__price")))
            .distinct()
        )

        serializer = OrderSerializer(basket, many=True)
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        items = request.data.get("items")
        if items:
            basket, _ = Order.objects.get_or_create(user=request.user, state=OrderStatus.BASKET)
            # Проходим по всем переданным позициям (items - это список словарей)
            created_count = 0
            for item in items:
                item.update({"order": basket.id})
                serializer = OrderItemSerializer(data=item)
                if serializer.is_valid():
                    try:
                        serializer.save()
                        created_count += 1
                    except IntegrityError:
                        return Response(
                            {"Status": False, "Errors": "Товар уже есть в корзине"}, status=status.HTTP_400_BAD_REQUEST
                        )
                else:
                    return Response({"Status": False, "Errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

            return Response({"Status": True, "Создано": created_count}, status=status.HTTP_201_CREATED)
        return Response(
            {"Status": False, "Errors": "Не переданы товары для добавления (поле items)"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def put(self, request, *args, **kwargs):
        items = request.data.get("items")
        if items:
            basket, _ = Order.objects.get_or_create(user=request.user, state=OrderStatus.BASKET)
            updated_count = 0
            for item in items:
                # Ищем позицию в корзине и обновляем количество
                order_item = OrderItem.objects.filter(order=basket, product_info_id=item["product_info"]).first()
                if order_item:
                    order_item.quantity = item["quantity"]
                    order_item.save()
                    updated_count += 1
            return Response({"Status": True, "Обновлено": updated_count}, status=status.HTTP_200_OK)
        return Response(
            {"Status": False, "Errors": "Не переданы товары (поле items)"}, status=status.HTTP_400_BAD_REQUEST
        )

    def delete(self, request, *args, **kwargs):
        items = request.data.get("items")
        if items:
            items_list = str(items).split(",")
            basket, _ = Order.objects.get_or_create(user=request.user, state=OrderStatus.BASKET)
            deleted_count, _ = OrderItem.objects.filter(order=basket, product_info_id__in=items_list).delete()
            return Response({"Status": True, "Удалено": deleted_count}, status=status.HTTP_200_OK)
        return Response(
            {"Status": False, "Errors": "Не переданы id товаров (поле items)"}, status=status.HTTP_400_BAD_REQUEST
        )


class OrderView(APIView):
    """
    Класс-представление для получения оформленных заказов
    и конвертации открытой "корзины" в реальный заказ.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        # Отдаем все заказы пользователя, ИСКЛЮЧАЯ текущую корзину (state='basket')
        orders = (
            Order.objects.filter(user=request.user)
            .exclude(state=OrderStatus.BASKET)
            .prefetch_related(
                "ordered_items__product_info__product__category",
                "ordered_items__product_info__product_parameters__parameter",
            )
            .annotate(total_sum=Sum(F("ordered_items__quantity") * F("ordered_items__product_info__price")))
            .distinct()
        )

        serializer = OrderSerializer(orders, many=True)
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        contact_id = request.data.get("contact")
        if contact_id:
            try:
                # Шаг 1. Находим открытую корзину пользователя
                basket = Order.objects.get(user=request.user, state=OrderStatus.BASKET)
            except Order.DoesNotExist:
                return Response(
                    {"Status": False, "Errors": "Нет открытой корзины для оформления"}, status=status.HTTP_404_NOT_FOUND
                )

            # Шаг 2. Оформляем: привязываем адрес(contact) и меняем статус
            basket.contact_id = contact_id
            basket.state = OrderStatus.NEW
            basket.save()

            # Шаг 3. Инициируем сигнал new_order
            from backend.signals import new_order

            new_order.send(sender=self.__class__, user_id=request.user.id)

            return Response({"Status": True, "Message": "Заказ успешно оформлен!"}, status=status.HTTP_200_OK)

        return Response(
            {"Status": False, "Errors": "Не передан контакт(адрес) доставки (поле contact)"},
            status=status.HTTP_400_BAD_REQUEST,
        )


class PartnerUpdate(APIView):
    """
    Класс для обновления прайса от поставщика (импорт товаров из YAML-файла).
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        # Только магазины могут загружать прайсы
        if request.user.type != UserType.SHOP:
            return Response({"Status": False, "Errors": "Только для магазинов"}, status=status.HTTP_403_FORBIDDEN)

        url = request.data.get("url")
        if url:
            validate_url = URLValidator()
            try:
                validate_url(url)
            except ValidationError as e:
                return Response({"Status": False, "Errors": str(e)}, status=status.HTTP_400_BAD_REQUEST)
            else:
                try:
                    stream = requests.get(url).content
                    data = yaml.load(stream, Loader=Loader)
                except Exception as e:
                    return Response(
                        {"Status": False, "Errors": f"Не удалось загрузить или распарсить YAML: {e!s}"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # Создаем или обновляем магазин
                shop, _ = Shop.objects.get_or_create(name=data["shop"], user_id=request.user.id)

                # Обработка категорий
                for category in data["categories"]:
                    category_obj, _ = Category.objects.get_or_create(id=category["id"], name=category["name"])
                    category_obj.shops.add(shop.id)
                    category_obj.save()

                # Очищаем старые товары магазина, так как это полное обновление прайса
                ProductInfo.objects.filter(shop_id=shop.id).delete()

                # Обработка товаров
                for item in data["goods"]:
                    product, _ = Product.objects.get_or_create(name=item["name"], category_id=item["category"])

                    product_info = ProductInfo.objects.create(
                        product_id=product.id,
                        external_id=item["id"],
                        model=item["model"],
                        price=item["price"],
                        price_rrc=item["price_rrc"],
                        quantity=item["quantity"],
                        shop_id=shop.id,
                    )

                    # Обработка характеристик
                    for name, value in item["parameters"].items():
                        parameter_obj, _ = Parameter.objects.get_or_create(name=name)
                        ProductParameter.objects.create(
                            product_info_id=product_info.id, parameter_id=parameter_obj.id, value=value
                        )

                return Response({"Status": True, "Message": "Прайс-лист успешно обновлен!"}, status=status.HTTP_200_OK)

        return Response({"Status": False, "Errors": "Не указан URL"}, status=status.HTTP_400_BAD_REQUEST)


class PartnerState(APIView):
    """
    Класс для управления статусом приема заказов магазином.
    Поставщик может временно выключить магазин, чтобы товары пропали из каталога.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        if request.user.type != UserType.SHOP:
            return Response({"Status": False, "Errors": "Только для магазинов"}, status=status.HTTP_403_FORBIDDEN)

        shop = request.user.shop
        serializer = ShopSerializer(shop)
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        if request.user.type != UserType.SHOP:
            return Response({"Status": False, "Errors": "Только для магазинов"}, status=status.HTTP_403_FORBIDDEN)

        state = request.data.get("state")
        if state is not None:
            # Приводим к boolean (на случай, если с фронта пришла строка 'true' или 'false')
            request.user.shop.state = str(state).lower() == "true"
            request.user.shop.save()
            return Response({"Status": True}, status=status.HTTP_200_OK)

        return Response({"Status": False, "Errors": "Не передан статус (state)"}, status=status.HTTP_400_BAD_REQUEST)


class PartnerOrders(APIView):
    """
    Класс для просмотра заказов конкретным магазином.
    Показывает только те заказы, в которых присутствуют товары этого магазина.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        if request.user.type != UserType.SHOP:
            return Response({"Status": False, "Errors": "Только для магазинов"}, status=status.HTTP_403_FORBIDDEN)

        # Фильтруем заказы, доставая только те, где фигурирует текущий магазин
        orders = (
            Order.objects.filter(ordered_items__product_info__shop__user=request.user)
            .exclude(state=OrderStatus.BASKET)
            .prefetch_related(
                "ordered_items__product_info__product__category",
                "ordered_items__product_info__product_parameters__parameter",
            )
            .annotate(total_sum=Sum(F("ordered_items__quantity") * F("ordered_items__product_info__price")))
            .distinct()
        )

        serializer = OrderSerializer(orders, many=True)
        return Response(serializer.data)
