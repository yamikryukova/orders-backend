from rest_framework import serializers

from backend.models import Category, Contact, Order, OrderItem, Product, ProductInfo, ProductParameter, Shop, User


class ContactSerializer(serializers.ModelSerializer):
    """Сериализатор для работы с контактами (адресами доставки) пользователя."""

    class Meta:
        model = Contact
        fields = ("id", "city", "street", "house", "structure", "building", "apartment", "phone")
        read_only_fields = ("id",)
        extra_kwargs = {"extracontent": {"write_only": True}}


class UserSerializer(serializers.ModelSerializer):
    """
    Сериализатор для пользователя. Включает в себя вложенные контакты,
    чтобы при запросе профиля сразу отдавать и адреса доставки.
    """

    contacts = ContactSerializer(read_only=True, many=True)

    class Meta:
        model = User
        fields = ("id", "first_name", "last_name", "email", "company", "position", "type", "contacts")
        read_only_fields = ("id",)


class CategorySerializer(serializers.ModelSerializer):
    """Сериализатор для категорий товаров."""

    class Meta:
        model = Category
        fields = ("id", "name")
        read_only_fields = ("id",)


class ShopSerializer(serializers.ModelSerializer):
    """Сериализатор для магазинов. Показывает статус приема заказов."""

    class Meta:
        model = Shop
        fields = ("id", "name", "state", "url")
        read_only_fields = ("id",)


class ProductSerializer(serializers.ModelSerializer):
    """Сериализатор базового продукта (названия)."""

    category = serializers.StringRelatedField()

    class Meta:
        model = Product
        fields = ("name", "category")


class ProductParameterSerializer(serializers.ModelSerializer):
    """Сериализатор параметров (характеристик) конкретного товара."""

    parameter = serializers.StringRelatedField()

    class Meta:
        model = ProductParameter
        fields = ("parameter", "value")


class ProductInfoSerializer(serializers.ModelSerializer):
    """
    Полная информация о товаре из конкретного магазина,
    включая цену, количество, магазин и вложенные характеристики.
    """

    product = ProductSerializer(read_only=True)
    product_parameters = ProductParameterSerializer(read_only=True, many=True)
    shop = serializers.StringRelatedField()

    class Meta:
        model = ProductInfo
        fields = ("id", "model", "product", "shop", "quantity", "price", "price_rrc", "product_parameters")
        read_only_fields = ("id",)


class OrderItemSerializer(serializers.ModelSerializer):
    """Сериализатор для работы с позициями корзины."""

    class Meta:
        model = OrderItem
        fields = ("id", "product_info", "quantity", "order")
        read_only_fields = ("id",)
        extra_kwargs = {"order": {"write_only": True}}


class OrderItemCreateSerializer(serializers.ModelSerializer):
    """
    Сериализатор для отображения элементов заказа.
    В отличии от базового возвращает вложенную подробную информацию о товаре.
    """

    product_info = ProductInfoSerializer(read_only=True)

    class Meta:
        model = OrderItem
        fields = ("id", "product_info", "quantity", "order")
        read_only_fields = ("id",)


class OrderSerializer(serializers.ModelSerializer):
    """
    Сериализатор отображения заказа.
    Содержит контакт доставки, все товарные позиции и общую сумму (которую мы аннотируем во View).
    """

    ordered_items = OrderItemCreateSerializer(read_only=True, many=True)
    total_sum = serializers.IntegerField(read_only=True)
    contact = ContactSerializer(read_only=True)

    class Meta:
        model = Order
        fields = ("id", "dt", "state", "contact", "ordered_items", "total_sum")
        read_only_fields = ("id",)
