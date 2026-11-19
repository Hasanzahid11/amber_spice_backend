from django.urls import path
from .consumers import OperationsConsumer, KitchenConsumer

websocket_urlpatterns = [
    path('ws/operations/', OperationsConsumer.as_asgi()),
    path('ws/kitchen/', KitchenConsumer.as_asgi()),
]
