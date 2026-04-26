from django.urls import include, path

from backend.views import (
    AccountDetails,
    BasketView,
    CategoryView,
    ConfirmAccount,
    ContactView,
    LoginAccount,
    OrderView,
    PartnerOrders,
    PartnerState,
    PartnerUpdate,
    ProductInfoView,
    RegisterAccount,
    ShopView,
)

app_name = "backend"

urlpatterns = [
    # Аутентификация, профиль и контакты
    path("user/register/", RegisterAccount.as_view(), name="user-register"),
    path("user/register/confirm/", ConfirmAccount.as_view(), name="user-register-confirm"),
    path("user/login/", LoginAccount.as_view(), name="user-login"),
    path("user/details/", AccountDetails.as_view(), name="user-details"),
    path("user/contact/", ContactView.as_view(), name="user-contact"),
    path("user/password_reset", include("django_rest_passwordreset.urls", namespace="password_reset")),
    # Каталог товаров
    path("categories/", CategoryView.as_view(), name="categories"),
    path("shops/", ShopView.as_view(), name="shops"),
    path("products/", ProductInfoView.as_view(), name="products"),
    # Корзина и заказы покупателя
    path("basket/", BasketView.as_view(), name="basket"),
    path("order/", OrderView.as_view(), name="order"),
    # Партнерский кабинет
    path("partner/update/", PartnerUpdate.as_view(), name="partner-update"),
    path("partner/state/", PartnerState.as_view(), name="partner-state"),
    path("partner/orders/", PartnerOrders.as_view(), name="partner-orders"),
]
