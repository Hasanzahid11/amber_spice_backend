from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import OrderViewSet
from .handover_views import KitchenHandoverView
from .contact_views import CustomerContactView, CustomerMessagesView, DispatchContactView, DispatchMessagesView

router = DefaultRouter()
router.register('', OrderViewSet, basename='order')

urlpatterns = [
    path('track/<str:order_number>/contact/', CustomerContactView.as_view()),
    path('track/<str:order_number>/contact/messages/', CustomerMessagesView.as_view()),
    path('<int:order_id>/handover/', KitchenHandoverView.as_view()),
    path('<int:order_id>/delivery/contact/', DispatchContactView.as_view()),
    path('<int:order_id>/delivery/contact/messages/', DispatchMessagesView.as_view()),
    path('', include(router.urls)),
]

