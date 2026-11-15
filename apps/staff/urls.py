from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import (
    StaffAttendanceViewSet,
    StaffMemberViewSet,
    StaffShiftViewSet,
)

router = DefaultRouter()
router.register('schedules', StaffShiftViewSet, basename='staff-schedule')
router.register('attendance', StaffAttendanceViewSet, basename='staff-attendance')
router.register('', StaffMemberViewSet, basename='staff')

urlpatterns = [
    path('', include(router.urls)),
]
