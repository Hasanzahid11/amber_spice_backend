from django.contrib.auth import get_user_model
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import (
    CanAccessDeliveries,
    CanAccessKitchenKDS,
    IsRestaurantStaff,
)
from .models import Order
from .serializers import OrderCreateSerializer, OrderSerializer
from .tasks import process_new_order_notification

User = get_user_model()


class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.prefetch_related('items').select_related('customer', 'assigned_delivery_staff').all()
    filterset_fields = ['status', 'dining_type', 'payment_status', 'table_number']
    search_fields = ['order_number', 'customer_name', 'customer_phone']
    ordering_fields = ['created_at', 'total_amount']

    def get_serializer_class(self):
        if self.action == 'create':
            return OrderCreateSerializer
        return OrderSerializer

    def get_permissions(self):
        if self.action in ['create', 'track']:
            return [permissions.AllowAny()]
        if self.action == 'kitchen':
            return [CanAccessKitchenKDS()]
        if self.action == 'deliveries':
            return [CanAccessDeliveries()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Order.objects.none()

        # Owner/Admin, Manager, and Cashier/Front see all orders
        if user.is_owner_or_admin or user.has_restaurant_permission('orders:view'):
            return super().get_queryset()

        # Kitchen Staff sees active kitchen orders
        if user.is_kitchen_staff:
            return super().get_queryset().filter(
                status__in=[Order.Status.PENDING, Order.Status.PREPARING, Order.Status.READY]
            )

        # Delivery Staff sees deliveries assigned to them or unassigned delivery orders
        if user.is_delivery_staff:
            return super().get_queryset().filter(
                dining_type=Order.DiningType.DELIVERY,
                assigned_delivery_staff=user
            )

        # Regular customer only sees their own orders
        return super().get_queryset().filter(customer=user)

    def perform_create(self, serializer):
        order = serializer.save()
        try:
            process_new_order_notification.apply_async(args=[order.id], retry=False)
        except Exception:
            pass

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        order = serializer.instance
        read_serializer = OrderSerializer(order)
        headers = self.get_success_headers(serializer.data)
        return Response(read_serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    @action(detail=False, methods=['get'], url_path=r'track/(?P<order_number>[\w\-]+)', permission_classes=[permissions.AllowAny])
    def track(self, request, order_number=None):
        """
        Public order tracking for guest and authenticated customers by order number or ID.
        """
        order = Order.objects.filter(order_number__iexact=order_number).prefetch_related('items').first()
        if not order and order_number and order_number.isdigit():
            order = Order.objects.filter(id=int(order_number)).prefetch_related('items').first()
        if not order:
            return Response({'error': 'Order not found with the provided order number.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(OrderSerializer(order).data)

    @action(detail=False, methods=['get'])
    def kitchen(self, request):
        """
        Kitchen Display System (KDS):
        Kitchen staff only see pending, preparing, and ready orders.
        Supports filtering by station (biryani, curry, grill, breads, dessert).
        """
        station = request.query_params.get('station', None)
        active_statuses = [Order.Status.PENDING, Order.Status.PREPARING, Order.Status.READY]
        orders = Order.objects.filter(status__in=active_statuses).prefetch_related('items')

        if station and station != 'all':
            orders = orders.filter(items__station=station).distinct()

        serializer = OrderSerializer(orders, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def deliveries(self, request):
        """
        Delivery Staff View:
        Section 18: 'Delivery Staff: Assigned deliveries and delivery status.'
        """
        user = request.user
        orders = Order.objects.filter(dining_type=Order.DiningType.DELIVERY).prefetch_related('items')

        # If Delivery Staff, filter by assigned orders
        if user.is_delivery_staff:
            orders = orders.filter(assigned_delivery_staff=user)

        serializer = OrderSerializer(orders, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['patch'])
    def update_status(self, request, pk=None):
        """
        Granular status update based on role:
        - Kitchen Staff can set: preparing, ready
        - Delivery Staff can set: out_for_delivery, delivered
        - Cashier / Front / Manager / Admin can set any status
        """
        order = self.get_object()
        new_status = request.data.get('status')
        user = request.user

        if new_status not in Order.Status.values:
            return Response(
                {'error': f"Invalid status. Must be one of {Order.Status.values}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Role checks
        if user.is_kitchen_staff and new_status not in [Order.Status.PREPARING, Order.Status.READY]:
            return Response(
                {'error': 'Kitchen staff can only mark orders as preparing or ready.'},
                status=status.HTTP_403_FORBIDDEN
            )

        if user.is_delivery_staff and new_status not in [Order.Status.OUT_FOR_DELIVERY, Order.Status.DELIVERED]:
            return Response(
                {'error': 'Delivery staff can only update delivery status (out_for_delivery or delivered).'},
                status=status.HTTP_403_FORBIDDEN
            )

        order.status = new_status
        order.save(update_fields=['status', 'updated_at'])
        return Response(OrderSerializer(order).data)

    @action(detail=True, methods=['post'], permission_classes=[IsRestaurantStaff])
    def assign_delivery(self, request, pk=None):
        """
        Assign an order to a delivery staff member.
        """
        order = self.get_object()
        staff_id = request.data.get('delivery_staff_id')
        staff_user = User.objects.filter(id=staff_id, role=User.Role.DELIVERY_STAFF).first()

        if not staff_user:
            return Response(
                {'error': 'A valid Delivery Staff user ID is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        order.assigned_delivery_staff = staff_user
        order.save(update_fields=['assigned_delivery_staff', 'updated_at'])
        return Response({
            'message': f"Order #{order.order_number} assigned to {staff_user.get_full_name() or staff_user.username}.",
            'order': OrderSerializer(order).data
        })
