from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    UserAddressViewSet,
    UserPreferencesView,
    UserProfileView,
)

router = DefaultRouter()
router.register('addresses', UserAddressViewSet, basename='user-address')

urlpatterns = [
    path('me/', UserProfileView.as_view(), name='profile_me'),
    path('preferences/', UserPreferencesView.as_view(), name='profile_preferences'),
    path('', include(router.urls)),
]

