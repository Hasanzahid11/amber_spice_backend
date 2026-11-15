from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    RestaurantProfileView,
    RestaurantOverviewView,
    RestaurantLiveStatusView,
    DeliveryCheckView,
    RestaurantLocationViewSet,
    OperatingHourViewSet,
    SpecialHolidayClosureViewSet,
    DeliveryZoneViewSet,
)

router = DefaultRouter()
router.register("locations", RestaurantLocationViewSet, basename="restaurant-location")
router.register("hours", OperatingHourViewSet, basename="restaurant-hours")
router.register("holidays", SpecialHolidayClosureViewSet, basename="restaurant-holidays")
router.register("delivery-zones", DeliveryZoneViewSet, basename="restaurant-delivery-zones")

urlpatterns = [
    # Singleton Profile & Overview
    path("profile/", RestaurantProfileView.as_view(), name="restaurant-profile"),
    path("overview/", RestaurantOverviewView.as_view(), name="restaurant-overview"),

    # Live Real-Time Operating Status
    path("status/", RestaurantLiveStatusView.as_view(), name="restaurant-status"),

    # Delivery Radius & Postal Eligibility Check
    path("check-delivery/", DeliveryCheckView.as_view(), name="restaurant-check-delivery"),

    # ViewSets (Locations, Weekly Hours, Holiday Closures, Delivery Zones)
    path("", include(router.urls)),
]

