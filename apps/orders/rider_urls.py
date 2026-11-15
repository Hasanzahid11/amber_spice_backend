from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .rider_views import RiderJobViewSet, RiderProfileView

router = DefaultRouter()
router.register('jobs', RiderJobViewSet, basename='rider-job')

urlpatterns = [path('me/', RiderProfileView.as_view(), name='rider-me'), path('', include(router.urls))]
