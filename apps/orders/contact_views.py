import secrets

from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import permissions
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import HasRestaurantPermission
from .delivery_chat import (ConversationSerializer, DeliveryMessageSerializer, MessageCreateSerializer,
                            MessagePageSerializer, conversation, message_page, save_message)
from .models import Order

CONTACT_TOKEN = OpenApiParameter('X-Order-Contact-Token', str, location=OpenApiParameter.HEADER, description='Guest-only private contact credential returned by checkout. Never use the public order number as the chat credential. Logged-in owners use JWT instead.')
AFTER_ID = OpenApiParameter('after_id', int, description='Non-negative last message ID. Follow nextAfterId while hasMore is true; default 0.')


def customer_order(request, order_number, locked=False):
    rows = Order.objects.select_related('assigned_delivery_staff__rider_profile', 'delivery_job')
    if locked:
        rows = rows.select_for_update(of=('self',))
    order = get_object_or_404(rows, order_number=order_number, dining_type='delivery')
    if order.customer_id:
        if not request.user.is_authenticated or request.user.id != order.customer_id:
            raise NotFound()
    else:
        token = request.headers.get('X-Order-Contact-Token', '')
        if not token or not order.customer_chat_token or not secrets.compare_digest(token, str(order.customer_chat_token)):
            raise NotFound()
    return order


class CustomerContactView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(parameters=[CONTACT_TOKEN], responses=ConversationSerializer, tags=['Delivery contact'], description='Authenticated order owner JWT OR, for a guest order, the separate private X-Order-Contact-Token from checkout. A public tracking number alone is insufficient. Returns actual rider info and whether messaging is open after pickup. Other customers return 404.')
    def get(self, request, order_number):
        order = customer_order(request, order_number)
        return Response(ConversationSerializer(conversation(order, 'customer')).data)


class CustomerMessagesView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(parameters=[CONTACT_TOKEN, AFTER_ID], responses=MessagePageSerializer, tags=['Delivery contact'], description='Order owner JWT or guest private contact header. Persisted customer/rider messages, 100 per page, in message ID order. Saved messages remain readable after delivery closes.')
    def get(self, request, order_number):
        return Response(message_page(customer_order(request, order_number), request))

    @extend_schema(parameters=[CONTACT_TOKEN], request=MessageCreateSerializer, responses={201: DeliveryMessageSerializer, 200: DeliveryMessageSerializer}, tags=['Delivery contact'], description='Order owner JWT or guest private contact header. Required body (1–2000 characters) and client_message_id UUID. Only after rider pickup and before delivery/cancellation. Reuse the UUID for the identical text on retry; changed text with a reused UUID returns 409. Sender identity is set by the server.')
    @transaction.atomic
    def post(self, request, order_number):
        order = customer_order(request, order_number, locked=True)
        message, created = save_message(order, request.user, 'customer', request.data)
        return Response(DeliveryMessageSerializer(message).data, status=201 if created else 200)


class DispatchContactView(APIView):
    permission_classes = [HasRestaurantPermission]
    required_permission = 'orders:view'

    @extend_schema(responses=ConversationSerializer, tags=['Delivery contact'], description='Operations JWT with orders:view. Read-only delivery conversation oversight. No dispatch message impersonation.')
    def get(self, request, order_id):
        order = get_object_or_404(Order.objects.select_related('assigned_delivery_staff__rider_profile', 'delivery_job'), pk=order_id, dining_type='delivery')
        return Response(ConversationSerializer(conversation(order, 'dispatch')).data)


class DispatchMessagesView(APIView):
    permission_classes = [HasRestaurantPermission]
    required_permission = 'orders:view'

    @extend_schema(parameters=[AFTER_ID], responses=MessagePageSerializer, tags=['Delivery contact'], description='Operations JWT with orders:view. Read persisted rider/customer messages for support. Read-only; POST is not supported.')
    def get(self, request, order_id):
        order = get_object_or_404(Order, pk=order_id, dining_type='delivery')
        return Response(message_page(order, request))
