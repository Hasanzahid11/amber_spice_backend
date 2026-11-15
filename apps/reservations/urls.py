from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import (
    DiningAreaViewSet,
    ReservationScheduleViewSet,
    ReservationSettingViewSet,
    ReservationViewSet,
    TableViewSet,
)

router = DefaultRouter()
router.register('tables', TableViewSet, basename='table')
router.register('dining-areas', DiningAreaViewSet, basename='dining-area')
router.register('schedules', ReservationScheduleViewSet, basename='reservation-schedule')
router.register('settings', ReservationSettingViewSet, basename='reservation-setting')
router.register('', ReservationViewSet, basename='reservation')

urlpatterns = [
    path('', include(router.urls)),
]
