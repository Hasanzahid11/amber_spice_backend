from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import CategoryViewSet, DishViewSet

router = DefaultRouter()
router.register('categories', CategoryViewSet, basename='category')
router.register('dishes', DishViewSet, basename='dish')

urlpatterns = [
    path('', include(router.urls)),
]

