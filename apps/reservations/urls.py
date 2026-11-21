from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import ReservationViewSet, TableViewSet

router = DefaultRouter()
router.register('tables', TableViewSet, basename='table')
router.register('bookings', ReservationViewSet, basename='reservation-booking')
router.register('', ReservationViewSet, basename='reservation')

urlpatterns = [
    path('', include(router.urls)),
]
