from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from .delivery_serializers import KitchenHandoverSerializer, RiderItemSerializer
from .handover import KitchenHandover
from .models import Order


class TicketRiderSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    phone = serializers.CharField(allow_blank=True)


class KitchenTicketSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    orderNumber = serializers.CharField()
    customerName = serializers.CharField()
    customerPhone = serializers.CharField(allow_blank=True)
    deliveryAddress = serializers.CharField(allow_blank=True)
    deliveryPostalCode = serializers.CharField(allow_blank=True)
    notes = serializers.CharField(allow_blank=True)
    status = serializers.CharField()
    items = RiderItemSerializer(many=True)
    assignedRider = TicketRiderSerializer(allow_null=True)
    stage = serializers.CharField()
    canHandOver = serializers.BooleanField()
    bagCount = serializers.IntegerField()
    sealed = serializers.BooleanField()
    handoverAt = serializers.DateTimeField(allow_null=True)
    handedOverBy = serializers.CharField(allow_blank=True)
    ticketCode = serializers.CharField(allow_blank=True)
    pickupVerifiedAt = serializers.DateTimeField(allow_null=True)
    deliveryVerifiedAt = serializers.DateTimeField(allow_null=True)


def ticket_data(order, user):
    job = getattr(order, 'delivery_job', None)
    rider = order.assigned_delivery_staff
    actor = job.handed_over_by if job else None
    return {'id': order.id, 'orderNumber': order.order_number, 'customerName': order.customer_name,
            'customerPhone': order.customer_phone, 'deliveryAddress': order.delivery_address, 'deliveryPostalCode': order.delivery_postal_code,
            'notes': order.notes, 'status': order.status, 'items': order.items.all(),
            'assignedRider': {'id': rider.id, 'name': rider.get_full_name() or rider.username, 'phone': rider.phone or ''} if rider else None,
            'stage': job.stage if job else 'unassigned', 'canHandOver': KitchenHandover.can_release(order, user),
            'bagCount': job.bag_count if job else 0, 'sealed': job.bags_sealed if job else False,
            'handoverAt': job.handed_over_at if job else None, 'handedOverBy': (actor.get_full_name() or actor.username) if actor else '',
            'ticketCode': job.handover_code if job else '', 'pickupVerifiedAt': job.pickup_verified_at if job else None,
            'deliveryVerifiedAt': job.delivery_verified_at if job else None}


class CanUseKitchenHandover(permissions.BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated or not user.is_restaurant_staff or user.is_delivery_staff:
            return False
        return (user.has_restaurant_permission('kitchen:view_orders') or user.has_restaurant_permission('orders:view')) if request.method in permissions.SAFE_METHODS else KitchenHandover.can_manage(user)


class KitchenHandoverView(APIView):
    permission_classes = [CanUseKitchenHandover]

    def get_order(self, request, pk, locked=False):
        rows = Order.objects.select_related('assigned_delivery_staff', 'delivery_job__handed_over_by').prefetch_related('items')
        if not request.user.has_restaurant_permission('orders:view'):
            rows = rows.filter(status__in=['pending', 'preparing', 'ready'])
        if locked:
            rows = rows.select_for_update(of=('self',))
        order = get_object_or_404(rows, pk=pk, dining_type='delivery')
        return order

    @extend_schema(responses=KitchenTicketSerializer, tags=['Kitchen handover'], description='Kitchen/operations JWT with kitchen:view_orders or orders:view; rider/customer roles denied. Read actual order, customer, assigned rider, exact item IDs/quantities and private bag-ticket code. Attach the printed ticket to the sealed food bags. Ticket codes are never in public tracking or rider job responses.')
    def get(self, request, order_id):
        order = self.get_order(request, order_id)
        return Response(KitchenTicketSerializer(ticket_data(order, request.user)).data)

    @extend_schema(request=KitchenHandoverSerializer, responses=KitchenTicketSerializer, tags=['Kitchen handover'], description='Kitchen/operations JWT with kitchen:update_status or orders:update_status. Requires ready order, accepted assigned active rider and no issue. Supply assigned rider_id, bag_count 1–30, sealed=true and EVERY actual order item_id/quantity. Wrong/missing/duplicate items or rider fail. Same bag count is an idempotent retry; changing count before pickup reissues the private code and invalidates the previous ticket.')
    @transaction.atomic
    def post(self, request, order_id):
        order = self.get_order(request, order_id, locked=True)
        serializer = KitchenHandoverSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        KitchenHandover.release(order, request.user, **serializer.validated_data)
        order = self.get_order(request, order_id)
        return Response(KitchenTicketSerializer(ticket_data(order, request.user)).data)
