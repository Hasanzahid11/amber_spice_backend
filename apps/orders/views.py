import hashlib
import json
import logging
import uuid

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Q, Count
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
                          OrderStatusSerializer, DeliveryAssignmentSerializer, CashCollectionSerializer, CheckoutResponseSerializer)
from .tasks import process_new_order_notification
from .delivery_workflow import DeliveryWorkflow
from .delivery_serializers import DeliveryProgressSerializer, RiderNoteSerializer

User = get_user_model()
logger = logging.getLogger(__name__)


@extend_schema_view(
    create=extend_schema(request=OrderCreateSerializer, responses={201: CheckoutResponseSerializer, 200: CheckoutResponseSerializer},
                         description='Guest or JWT customer checkout. Catalog prices and totals are server calculated. Cash only until a payment provider is configured. Reuse client_request_id UUID for safe retries of the identical request.'),
    list=extend_schema(description='JWT required. Customers see only their own orders; delivery staff only their assigned deliveries; operators require orders:view.'),
)
class OrderViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = Order.objects.prefetch_related('items', 'events').select_related('customer', 'assigned_delivery_staff', 'delivery_job').all()
    filterset_fields = ['status', 'dining_type', 'payment_status', 'table_number']
    search_fields = ['order_number', 'customer_name', 'customer_phone']
    ordering_fields = ['created_at', 'total_amount']

    def get_serializer_class(self):
        return {'create': OrderCreateSerializer, 'quote': OrderQuoteSerializer,
                'update_status': OrderStatusSerializer, 'assign_delivery': DeliveryAssignmentSerializer,
                'collect_cash': CashCollectionSerializer}.get(self.action, OrderSerializer)

    def get_permissions(self):
        if self.action in ['create', 'track', 'track_arrived', 'quote']:
            return [permissions.AllowAny()]
        if self.action == 'kitchen':
            return [CanAccessKitchenKDS()]
        if self.action == 'deliveries':
            return [CanAccessDeliveries()]
        if self.action in ['assign_delivery', 'delivery_staff']:
            return [HasRestaurantPermission('orders:update_status')]
        if self.action == 'delivery_progress':
            return [HasRestaurantPermission('orders:view')]
        if self.action in ['resolve_delivery_issue', 'request_delivery_return']:
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
        try:
            from apps.notifications.broadcaster import broadcast_order_created
            broadcast_order_created(order)
        except Exception as e:
            logger.warning('Order %s real-time broadcast failed: %s', order.id, e)
        return Response(self.checkout_response(order), status=status.HTTP_201_CREATED)

    @staticmethod
    def checkout_response(order):
        data = dict(OrderSerializer(order).data)
        if order.customer_id is None:
            data['customerContactToken'] = str(order.customer_chat_token)
        return data

    def replay(self, order, fingerprint):
        customer_id = self.request.user.id if self.request.user.is_authenticated else None
        if order.request_fingerprint != fingerprint or order.customer_id != customer_id:
            return Response({'detail': 'This request ID has already been used. Start a new checkout.'}, status=409)
        return Response(self.checkout_response(order))

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
        totals, promotion = apply_promotion(totals, serializer.validated_data.get('coupon_code'), request.user)
        return Response({
            'subtotal': str(totals['subtotal']),
            'tax': str(totals['tax']),
            'deliveryFee': str(totals['delivery_fee']),
            'totalAmount': str(totals['total_amount']),
            'discountAmount': str(totals['discount_amount']),
            'couponCode': promotion.code if promotion else '',
            'promotionTitle': promotion.title if promotion else '',
        })

    @extend_schema(responses=OrderSerializer, description='Public capability link: use the full unguessable order number returned by checkout. Keep it private. Numeric IDs and phone-number searches are not accepted.')
    @action(detail=False, methods=['get'], url_path=r'track/(?P<order_number>[\w\-]+)')
    def track(self, request, order_number=None):
        order = get_object_or_404(self.queryset, order_number__iexact=order_number)
        return Response(OrderSerializer(order).data)

    @extend_schema(
        responses=inline_serializer('TakeawayArrivalResponse', fields={
            'message': serializers.CharField(),
            'orderNumber': serializers.CharField(),
            'pickupCode': serializers.CharField(),
            'customerArrivedAt': serializers.DateTimeField(),
        }),
        description='Customer announces arrival at the restaurant counter for takeaway collection.'
    )
    @action(detail=False, methods=['post'], url_path=r'track/(?P<order_number>[\w\-]+)/arrived')
    @transaction.atomic
    def track_arrived(self, request, order_number=None):
        order = get_object_or_404(self.queryset.select_for_update(of=('self',)), order_number__iexact=order_number)
        if order.dining_type != Order.DiningType.TAKEAWAY:
            raise ValidationError({'detail': 'Arrival check-in is only applicable for takeaway orders.'})
        if order.status == Order.Status.DELIVERED:
            raise ValidationError({'detail': 'This order has already been collected.'})
        if order.status == Order.Status.CANCELLED:
            raise ValidationError({'detail': 'This order was cancelled.'})

        now = timezone.now()
        order.customer_arrived_at = now
        order.save(update_fields=['customer_arrived_at', 'updated_at'])

        try:
            from apps.notifications.broadcaster import broadcast_customer_arrived
            broadcast_customer_arrived(order)
        except Exception as e:
            logger.warning('Customer arrival broadcast failed for %s: %s', order.order_number, e)

        return Response({
            'message': 'Counter staff has been notified of your arrival.',
            'orderNumber': order.order_number,
            'pickupCode': order.display_pickup_code,
            'customerArrivedAt': order.customer_arrived_at,
        })

    @extend_schema(
        request=inline_serializer('CompleteTakeawayRequest', fields={
            'paymentMethod': serializers.ChoiceField(choices=['cash', 'card'], required=False),
            'counterNotes': serializers.CharField(max_length=255, required=False),
        }),
        responses=OrderSerializer,
        description='JWT with orders:update_status or kitchen:update_status. Fast counter completion for ready takeaway orders. Verifies handover, settles payment, marks delivered, and records audit trail.'
    )
    @action(detail=True, methods=['post'], url_path='complete-takeaway')
    @transaction.atomic
    def complete_takeaway(self, request, pk=None):
        order = get_object_or_404(self.get_queryset().select_for_update(of=('self',)), pk=pk)
        user = request.user
        if not (user.has_restaurant_permission('orders:update_status') or user.has_restaurant_permission('kitchen:update_status')):
            raise PermissionDenied('You cannot complete this order.')
        if order.dining_type != Order.DiningType.TAKEAWAY:
            raise ValidationError({'detail': 'This endpoint is for takeaway orders only.'})
        if order.status in ['delivered', 'cancelled']:
            raise ValidationError({'detail': f'Order is already {order.status}.'})

        now = timezone.now()
        order.status = Order.Status.DELIVERED
        order.picked_up_at = now
        update_fields = ['status', 'picked_up_at', 'updated_at']

        chosen_method = request.data.get('paymentMethod') or request.data.get('payment_method')
        if chosen_method in ['cash', 'card']:
            order.payment_method = chosen_method
            update_fields.append('payment_method')

        counter_notes = str(request.data.get('counterNotes') or request.data.get('counter_notes') or '').strip()
        if counter_notes:
            order.counter_notes = counter_notes
            update_fields.append('counter_notes')

        if order.payment_status != Order.PaymentStatus.PAID:
            order.payment_status = Order.PaymentStatus.PAID
            order.payment_collected_at = now
            order.payment_collected_by = user
            update_fields.extend(['payment_status', 'payment_collected_at', 'payment_collected_by'])

        order.save(update_fields=update_fields)
        OrderEvent.objects.create(order=order, status=Order.Status.DELIVERED)

        try:
            from apps.notifications.broadcaster import broadcast_order_status_updated
            actor_name = user.get_full_name() or user.username
            broadcast_order_status_updated(order, actor_name=actor_name)
        except Exception as e:
            logger.warning('Order %s real-time status broadcast failed: %s', order.id, e)

        return Response(OrderSerializer(order).data)

    @extend_schema(
        request=inline_serializer('PickupRackRequest', fields={'pickupRack': serializers.CharField(max_length=64)}),
        responses=OrderSerializer,
        description='Assigns or updates the warming shelf / pickup rack location (e.g. "Warm Shelf A", "Front Counter").'
    )
    @action(detail=True, methods=['patch'], url_path='pickup-rack')
    @transaction.atomic
    def assign_pickup_rack(self, request, pk=None):
        order = get_object_or_404(self.get_queryset().select_for_update(of=('self',)), pk=pk)
        user = request.user
        if not (user.has_restaurant_permission('orders:update_status') or user.has_restaurant_permission('kitchen:update_status')):
            raise PermissionDenied('You cannot update shelf location.')
        rack = request.data.get('pickupRack') or request.data.get('pickup_rack') or 'Front Counter'
        order.pickup_rack = str(rack).strip()
        order.save(update_fields=['pickup_rack', 'updated_at'])

        try:
            from apps.notifications.broadcaster import broadcast_order_status_updated
            broadcast_order_status_updated(order, actor_name=user.get_full_name() or user.username)
        except Exception as e:
            logger.warning('Order %s rack broadcast failed: %s', order.id, e)

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
        staff = User.objects.filter(role=User.Role.DELIVERY_STAFF, is_active=True).select_related('rider_profile').annotate(
            active_jobs=Count('assigned_deliveries', filter=~Q(assigned_deliveries__status__in=['delivered', 'cancelled']) & Q(assigned_deliveries__dining_type='delivery')),
        ).order_by('first_name', 'id')
        return Response([{'id': user.id, 'name': user.get_full_name() or user.username, 'phone': user.phone or '',
                          'onDuty': bool(getattr(user, 'rider_profile', None) and user.rider_profile.on_duty),
                          'activeJobs': user.active_jobs} for user in staff])

    @extend_schema(request=OrderStatusSerializer, responses=OrderSerializer,
                   description='JWT and appropriate orders/kitchen update permission. Kitchen: pending to preparing to ready. Ready takeaway/dine-in orders may be handed over as delivered. Delivery pickup/completion must use the assigned rider ticket-verification endpoints; generic dispatch/completion is blocked. Terminal orders cannot change.')
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
        if user.is_delivery_staff:
            if not delivery:
                raise PermissionDenied('Riders can only progress their assigned deliveries.')
            DeliveryWorkflow.progress(order, user, 'pickup' if new_status == 'out_for_delivery' else 'complete')
            return Response(OrderSerializer(self.get_queryset().get(pk=order.pk)).data)
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
        DeliveryWorkflow.sync_operator_status(order, user, new_status)
        update_fields = ['status', 'updated_at']
        if new_status == 'delivered' and order.dining_type == 'takeaway':
            order.picked_up_at = timezone.now()
            update_fields.append('picked_up_at')
            if order.payment_status != 'paid':
                order.payment_status = 'paid'
                update_fields.append('payment_status')
        order.status = new_status
        order.save(update_fields=update_fields)
        OrderEvent.objects.create(order=order, status=new_status)
        try:
            from apps.notifications.broadcaster import broadcast_order_status_updated, broadcast_kitchen_ticket
            actor_name = user.get_full_name() or user.username
            broadcast_order_status_updated(order, actor_name=actor_name)
            if new_status == 'preparing':
                broadcast_kitchen_ticket(order, action='received')
        except Exception as e:
            logger.warning('Order %s real-time status broadcast failed: %s', order.id, e)
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
        DeliveryWorkflow.assign(order, staff, request.user)
        return Response({'message': 'Delivery staff assigned.', 'order': OrderSerializer(self.get_queryset().get(pk=order.pk)).data})

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
        DeliveryWorkflow.record_cash(order, user)
        return Response(OrderSerializer(self.get_queryset().get(pk=order.pk)).data)

    @extend_schema(responses=DeliveryProgressSerializer, description='JWT with orders:view. Delivery stage, open issue and actor-stamped delivery activity. Internal notes are not exposed through public order tracking.')
    @action(detail=True, methods=['get'], url_path='delivery')
    def delivery_progress(self, request, pk=None):
        order = self.get_object()
        if order.dining_type != 'delivery':
            raise ValidationError({'detail': 'This is not a delivery order.'})
        job = getattr(order, 'delivery_job', None)
        return Response(DeliveryProgressSerializer(job).data if job else None)

    @extend_schema(request=RiderNoteSerializer, responses=DeliveryProgressSerializer, description='JWT with orders:update_status. Required resolution note. Clears an open delivery issue so the assigned rider can resume. Audit event is saved. A repeated resolution is safe.')
    @action(detail=True, methods=['post'], url_path='delivery/resolve-issue')
    @transaction.atomic
    def resolve_delivery_issue(self, request, pk=None):
        order = get_object_or_404(self.get_queryset().select_for_update(of=('self',)), pk=pk)
        if order.dining_type != 'delivery':
            raise ValidationError({'detail': 'This is not a delivery order.'})
        serializer = RiderNoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        DeliveryWorkflow.resolve_issue(order, request.user, serializer.validated_data['note'])
        order = self.get_queryset().get(pk=order.pk)
        return Response(DeliveryProgressSerializer(order.delivery_job).data)

    @extend_schema(request=RiderNoteSerializer, responses=DeliveryProgressSerializer, description='JWT operations with orders:update_status. Required instruction note. Approves return of an in-transit order with a reported issue. Rider must confirm actual return before the order is cancelled. No automatic charge/refund.')
    @action(detail=True, methods=['post'], url_path='delivery/request-return')
    @transaction.atomic
    def request_delivery_return(self, request, pk=None):
        order = get_object_or_404(self.get_queryset().select_for_update(of=('self',)), pk=pk)
        if order.dining_type != 'delivery':
            raise ValidationError({'detail': 'This is not a delivery order.'})
        serializer = RiderNoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        DeliveryWorkflow.request_return(order, request.user, serializer.validated_data['note'])
        order = self.get_queryset().get(pk=order.pk)
        return Response(DeliveryProgressSerializer(order.delivery_job).data)
