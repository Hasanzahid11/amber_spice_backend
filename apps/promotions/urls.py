from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import PromotionViewSet, PromotionUsageViewSet

router = DefaultRouter()
router.register(r'usages', PromotionUsageViewSet, basename='promotion-usages')
router.register(r'', PromotionViewSet, basename='promotions')

urlpatterns = [
    path('', include(router.urls)),
]

