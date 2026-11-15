from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import CartViewSet, CustomerAddressViewSet, OrderViewSet

router = DefaultRouter()
router.register('addresses', CustomerAddressViewSet, basename='customer-address')
router.register('cart', CartViewSet, basename='cart')
router.register('', OrderViewSet, basename='order')

urlpatterns = [
    path('', include(router.urls)),
]
