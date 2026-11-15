import hashlib
import json
import logging
import uuid

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, inline_serializer
from rest_framework import mixins, permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.accounts.permissions import CanAccessDeliveries, CanAccessKitchenKDS, HasRestaurantPermission
from .models import Order, OrderEvent
from .pricing import price_items, apply_promotion
from .serializers import (DeliveryStaffSerializer, OrderCreateSerializer, OrderSerializer, OrderQuoteSerializer,
                          OrderStatusSerializer, DeliveryAssignmentSerializer, CashCollectionSerializer)
from .tasks import process_new_order_notification

User = get_user_model()
logger = logging.getLogger(__name__)


@extend_schema_view(
    create=extend_schema(request=OrderCreateSerializer, responses={201: OrderSerializer, 200: OrderSerializer},
                         description='Guest or JWT customer checkout. Catalog prices and totals are server calculated. Cash only until a payment provider is configured. Reuse client_request_id UUID for safe retries of the identical request.'),
    list=extend_schema(description='JWT required. Customers see only their own orders; delivery staff only their assigned deliveries; operators require orders:view.'),
)
class OrderViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = Order.objects.prefetch_related('items', 'events').select_related('customer', 'assigned_delivery_staff').all()
    filterset_fields = ['status', 'dining_type', 'payment_status', 'table_number']
    search_fields = ['order_number', 'customer_name', 'customer_phone']
    ordering_fields = ['created_at', 'total_amount']

    def get_serializer_class(self):
        return {'create': OrderCreateSerializer, 'quote': OrderQuoteSerializer,
                'update_status': OrderStatusSerializer, 'assign_delivery': DeliveryAssignmentSerializer,
                'collect_cash': CashCollectionSerializer}.get(self.action, OrderSerializer)

    def get_permissions(self):
        if self.action in ['create', 'track', 'quote']:
            return [permissions.AllowAny()]
        if self.action == 'kitchen':
            return [CanAccessKitchenKDS()]
        if self.action == 'deliveries':
            return [CanAccessDeliveries()]
        if self.action in ['assign_delivery', 'delivery_staff']:
            return [HasRestaurantPermission('orders:update_status')]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Order.objects.none()
        queryset = super().get_queryset()
        if user.is_delivery_staff:
            return queryset.filter(dining_type='delivery', assigned_delivery_staff=user)
        if user.is_owner_or_admin or user.has_restaurant_permission('orders:view'):
            return queryset
        if user.has_restaurant_permission('kitchen:view_orders'):
            return queryset.filter(status__in=['pending', 'preparing', 'ready'])
        return queryset.filter(customer=user)

    def create(self, request, *args, **kwargs):
        request_id = request.data.get('clientRequestId', request.data.get('client_request_id'))
        fingerprint = hashlib.sha256(json.dumps(request.data, sort_keys=True).encode()).hexdigest()
        if request_id:
            try:
                request_id = uuid.UUID(str(request_id))
            except ValueError:
                raise ValidationError({'client_request_id': 'Must be a valid UUID.'})
            existing = Order.objects.filter(client_request_id=request_id).first()
            if existing:
                return self.replay(existing, fingerprint)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                order = serializer.save(request_fingerprint=fingerprint)
        except IntegrityError:
            existing = Order.objects.filter(client_request_id=request_id).first() if request_id else None
            if not existing:
                raise
            return self.replay(existing, fingerprint)
        try:
            process_new_order_notification.apply_async(args=[order.id], retry=False)
        except Exception:
            logger.warning('Order %s saved; notification could not be queued.', order.id)
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)

    def replay(self, order, fingerprint):
        customer_id = self.request.user.id if self.request.user.is_authenticated else None
        if order.request_fingerprint != fingerprint or order.customer_id != customer_id:
            return Response({'detail': 'This request ID has already been used. Start a new checkout.'}, status=409)
        return Response(OrderSerializer(order).data)

    @extend_schema(request=OrderQuoteSerializer, responses=inline_serializer('OrderQuoteResponse', fields={
        'subtotal': serializers.DecimalField(max_digits=10, decimal_places=2),
        'tax': serializers.DecimalField(max_digits=10, decimal_places=2),
        'deliveryFee': serializers.DecimalField(max_digits=10, decimal_places=2),
        'totalAmount': serializers.DecimalField(max_digits=10, decimal_places=2),
        'discountAmount': serializers.DecimalField(max_digits=10, decimal_places=2),
    }), description='Public. Validate dish IDs, portions and extras and calculate VAT-inclusive totals without saving an order.')
    @action(detail=False, methods=['post'])
    def quote(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        _, totals = price_items(serializer.validated_data['items'], serializer.validated_data['dining_type'])
        totals, _ = apply_promotion(totals, serializer.validated_data.get('coupon_code'), request.user)
        return Response({'subtotal': str(totals['subtotal']), 'tax': str(totals['tax']),
                         'deliveryFee': str(totals['delivery_fee']), 'totalAmount': str(totals['total_amount']), 'discountAmount': str(totals['discount_amount'])})

    @extend_schema(responses=OrderSerializer, description='Public capability link: use the full unguessable order number returned by checkout. Keep it private. Numeric IDs and phone-number searches are not accepted.')
    @action(detail=False, methods=['get'], url_path=r'track/(?P<order_number>[\w\-]+)')
    def track(self, request, order_number=None):
        order = get_object_or_404(self.queryset, order_number__iexact=order_number)
        return Response(OrderSerializer(order).data)

    @extend_schema(parameters=[OpenApiParameter('station', str)], responses=OrderSerializer(many=True))
    @action(detail=False, methods=['get'])
    def kitchen(self, request):
        orders = self.queryset.filter(status__in=['pending', 'preparing', 'ready']).filter(
            Q(scheduled_for__isnull=True) | Q(scheduled_for__lte=timezone.now()))
        station = request.query_params.get('station')
        if station and station != 'all':
            orders = orders.filter(items__station=station).distinct()
        return Response(OrderSerializer(orders, many=True).data)

    @extend_schema(responses=OrderSerializer(many=True))
    @action(detail=False, methods=['get'])
    def deliveries(self, request):
        return Response(OrderSerializer(self.get_queryset().filter(dining_type='delivery'), many=True).data)

    @extend_schema(responses=DeliveryStaffSerializer(many=True), description='JWT with orders:update_status. Active delivery user IDs for assignment.')
    @action(detail=False, methods=['get'], url_path='delivery-staff')
    def delivery_staff(self, request):
        staff = User.objects.filter(role=User.Role.DELIVERY_STAFF, is_active=True).order_by('first_name', 'id')
        return Response([{'id': user.id, 'name': user.get_full_name() or user.username, 'phone': user.phone} for user in staff])

    @extend_schema(request=OrderStatusSerializer, responses=OrderSerializer,
                   description='JWT and appropriate orders/kitchen/delivery update permission. Enforces pending to preparing to ready to out_for_delivery to delivered. Dispatch requires an assigned active driver. Terminal orders cannot change.')
    @action(detail=True, methods=['patch'])
    @transaction.atomic
    def update_status(self, request, pk=None):
        order = get_object_or_404(self.get_queryset().select_for_update(of=('self',)), pk=pk)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_status = serializer.validated_data['status']
        user = request.user
        general = user.has_restaurant_permission('orders:update_status')
        kitchen = user.has_restaurant_permission('kitchen:update_status') and new_status in ['preparing', 'ready']
        delivery = user.has_restaurant_permission('deliveries:update_status') and new_status in ['out_for_delivery', 'delivered'] and order.assigned_delivery_staff_id == user.id
        if not (general or kitchen or delivery):
            raise PermissionDenied('You cannot update this order status.')
        if new_status == order.status:
            return Response(OrderSerializer(order).data)
        transitions = {'pending': ['preparing', 'cancelled'], 'preparing': ['ready', 'cancelled'],
                       'ready': ['out_for_delivery' if order.dining_type == 'delivery' else 'delivered', 'cancelled'],
                       'out_for_delivery': ['delivered'], 'delivered': [], 'cancelled': []}
        if new_status not in transitions[order.status]:
            raise ValidationError({'status': f'Cannot change {order.status} to {new_status}.'})
        if new_status == 'cancelled' and not user.has_restaurant_permission('orders:cancel'):
            raise PermissionDenied('You cannot cancel orders.')
        if new_status == 'preparing' and order.scheduled_for and order.scheduled_for > timezone.now():
            raise ValidationError({'status': 'This order is scheduled for a later time.'})
        if new_status == 'out_for_delivery' and (not order.assigned_delivery_staff or not order.assigned_delivery_staff.is_active):
            raise ValidationError({'status': 'Assign an active delivery staff member before dispatch.'})
        order.status = new_status
        order.save(update_fields=['status', 'updated_at'])
        OrderEvent.objects.create(order=order, status=new_status)
        return Response(OrderSerializer(order).data)

    @extend_schema(request=DeliveryAssignmentSerializer, responses=inline_serializer('DeliveryAssignmentResponse', fields={
        'message': serializers.CharField(), 'order': OrderSerializer(),
    }), description='JWT with orders:update_status. Use an ID from GET delivery-staff. Only active delivery users and delivery orders before dispatch are accepted.')
    @action(detail=True, methods=['post'])
    @transaction.atomic
    def assign_delivery(self, request, pk=None):
        order = get_object_or_404(self.get_queryset().select_for_update(of=('self',)), pk=pk)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        staff = User.objects.filter(pk=serializer.validated_data['delivery_staff_id'], role=User.Role.DELIVERY_STAFF, is_active=True).first()
        if not staff:
            raise ValidationError({'delivery_staff_id': 'Select an active delivery staff user.'})
        if order.dining_type != 'delivery' or order.status not in ['pending', 'preparing', 'ready']:
            raise ValidationError({'detail': 'Only delivery orders before dispatch can be assigned.'})
        order.assigned_delivery_staff = staff
        order.save(update_fields=['assigned_delivery_staff', 'updated_at'])
        return Response({'message': 'Delivery staff assigned.', 'order': OrderSerializer(order).data})

    @extend_schema(request=CashCollectionSerializer, responses=OrderSerializer,
                   description='JWT with orders:update_status, or assigned delivery user with deliveries:update_status. Records cash collection after handover. Does not charge cards.')
    @action(detail=True, methods=['post'], url_path='collect-cash')
    @transaction.atomic
    def collect_cash(self, request, pk=None):
        order = get_object_or_404(self.get_queryset().select_for_update(of=('self',)), pk=pk)
        user = request.user
        if not (user.has_restaurant_permission('orders:update_status') or (order.assigned_delivery_staff_id == user.id and user.has_restaurant_permission('deliveries:update_status'))):
            raise PermissionDenied('You cannot record this payment.')
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if order.payment_method != 'cash' or order.status != 'delivered' or order.payment_status == 'refunded':
            raise ValidationError({'detail': 'Record cash only after delivery or collection handover.'})
        order.payment_status = 'paid'
        order.save(update_fields=['payment_status', 'updated_at'])
        return Response(OrderSerializer(order).data)
