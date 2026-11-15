import uuid
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import (
    CanAccessDeliveries,
    CanAccessKitchenKDS,
    IsRestaurantStaff,
)
from apps.menu.models import Dish, DishExtraOption, DishPortionOption
from .models import Cart, CartItem, CustomerAddress, Order, OrderItem
from .serializers import (
    CartItemAddSerializer,
    CartItemSerializer,
    CartSerializer,
    CheckoutPreviewSerializer,
    CustomerAddressSerializer,
    OrderCreateSerializer,
    OrderSerializer,
)
from .tasks import process_new_order_notification

User = get_user_model()


def get_or_create_cart(request) -> Cart:
    """
    Retrieves or initializes a shopping cart for an authenticated user or guest session.
    """
    user = request.user if request.user.is_authenticated else None
    if user:
        cart, _ = Cart.objects.get_or_create(user=user)
        return cart

    # Guest session identifier from header, query param, or payload
    session_id = (
        request.headers.get('X-Session-ID')
        or request.query_params.get('session_id')
        or (request.data.get('session_id') if isinstance(request.data, dict) else None)
    )

    if not session_id and hasattr(request, 'session'):
        if not request.session.session_key:
            request.session.create()
        session_id = request.session.session_key

    if not session_id:
        session_id = uuid.uuid4().hex

    cart, _ = Cart.objects.get_or_create(session_id=session_id, user=None)
    return cart


class OrderViewSet(viewsets.ModelViewSet):
    """
    Online Ordering API:
    - Supports Delivery, Collection/Takeaway, Dine-In.
    - Supports ASAP and Scheduled orders.
    - Supports Guest checkout and Customer accounts.
    - Supports 1-click reordering, saved favorite orders, and order history.
    - Supports Kitchen KDS and Delivery Staff workflows.
    """
    queryset = Order.objects.prefetch_related('items').select_related('customer', 'assigned_delivery_staff').all()
    filterset_fields = ['status', 'dining_type', 'schedule_type', 'payment_status', 'is_saved_order']
    search_fields = ['order_number', 'customer_name', 'customer_phone', 'customer_email', 'delivery_address']
    ordering_fields = ['created_at', 'total_amount', 'scheduled_for']

    def get_serializer_class(self):
        if self.action == 'create':
            return OrderCreateSerializer
        return OrderSerializer

    def get_permissions(self):
        if self.action in ['create', 'lookup', 'preview']:
            return [permissions.AllowAny()]
        if self.action == 'kitchen':
            return [CanAccessKitchenKDS()]
        if self.action == 'deliveries':
            return [CanAccessDeliveries()]
        if self.action in ['history', 'reorder', 'toggle_save', 'saved_orders']:
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Order.objects.none()

        # Owner/Admin, Manager, and Staff with orders:view see all orders
        if user.is_owner_or_admin or user.has_restaurant_permission('orders:view'):
            return super().get_queryset()

        # Kitchen Staff sees active orders on the KDS
        if user.has_restaurant_permission('kitchen:view_orders') and not user.has_restaurant_permission('orders:view'):
            return super().get_queryset().filter(
                status__in=[Order.Status.PENDING, Order.Status.PREPARING, Order.Status.READY]
            )

        # Delivery Staff sees assigned deliveries
        if user.has_restaurant_permission('deliveries:view_assigned') and not user.has_restaurant_permission('orders:view'):
            return super().get_queryset().filter(
                dining_type=Order.DiningType.DELIVERY,
                assigned_delivery_staff=user
            )

        # Authenticated Customer only sees their own orders
        return super().get_queryset().filter(customer=user)

    def perform_create(self, serializer):
        order = serializer.save()
        try:
            process_new_order_notification.delay(order.id)
        except Exception:
            pass

    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def preview(self, request):
        """
        POST /api/v1/orders/preview/
        Calculates exact subtotal, delivery fee, taxes, and total before checkout.
        """
        serializer = CheckoutPreviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        dining_type = data.get('dining_type', Order.DiningType.DELIVERY)
        items = data.get('items', [])

        subtotal = Decimal('0.00')
        for it in items:
            q = it.get('quantity', 1)
            p = Decimal(str(it.get('price', 0.00)))
            subtotal += p * q

        delivery_fee = Decimal('3.50') if dining_type == Order.DiningType.DELIVERY else Decimal('0.00')
        tax = Decimal('0.00')
        total_amount = subtotal + delivery_fee + tax
        estimated_time = 35 if dining_type == Order.DiningType.DELIVERY else 20

        return Response({
            'diningType': dining_type,
            'scheduleType': data.get('schedule_type', Order.ScheduleType.ASAP),
            'scheduledFor': data.get('scheduled_for'),
            'itemsCount': sum(it.get('quantity', 1) for it in items),
            'subtotal': float(subtotal),
            'deliveryFee': float(delivery_fee),
            'tax': float(tax),
            'totalAmount': float(total_amount),
            'estimatedTimeMinutes': estimated_time,
        })

    @action(detail=False, methods=['get'], permission_classes=[permissions.AllowAny])
    def lookup(self, request):
        """
        GET /api/v1/orders/lookup/?order_number=ORD-20261114-XYZ&phone=+353871234567
        Order tracking for guest checkout and customer inquiries.
        """
        order_number = request.query_params.get('order_number')
        phone = request.query_params.get('phone')

        if not order_number:
            return Response(
                {'error': 'Query parameter "order_number" is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        query = Order.objects.filter(order_number__iexact=order_number.strip())
        if phone:
            query = query.filter(customer_phone__icontains=phone.strip()[-7:])

        order = query.first()
        if not order:
            return Response(
                {'error': f"Order '{order_number}' not found. Please verify order number and phone."},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = OrderSerializer(order)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def history(self, request):
        """
        GET /api/v1/orders/history/
        Returns full past order history for the authenticated customer.
        """
        orders = Order.objects.filter(customer=request.user).order_by('-created_at')
        serializer = OrderSerializer(orders, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def reorder(self, request, pk=None):
        """
        POST /api/v1/orders/<id>/reorder/
        1-Click Reorder: Clones past order items, portions, extras, and customizations into a new order.
        """
        past_order = self.get_object()
        user = request.user

        # Optional overrides from request body
        dining_type = request.data.get('dining_type', past_order.dining_type)
        schedule_type = request.data.get('schedule_type', Order.ScheduleType.ASAP)
        scheduled_for = request.data.get('scheduled_for', None)
        payment_method = request.data.get('payment_method', past_order.payment_method)
        delivery_address = request.data.get('delivery_address', past_order.delivery_address)

        # Calculate current prices from menu
        items_payload = []
        for it in past_order.items.all():
            items_payload.append({
                'dish_id': it.dish_id,
                'name': it.name,
                'quantity': it.quantity,
                'price': it.price,
                'station': it.station,
                'customizations': it.customizations,
                'special_instructions': it.special_instructions,
            })

        order_data = {
            'customer_name': user.get_full_name() or user.username or past_order.customer_name,
            'customer_phone': user.phone or past_order.customer_phone,
            'customer_email': user.email or past_order.customer_email,
            'dining_type': dining_type,
            'schedule_type': schedule_type,
            'scheduled_for': scheduled_for,
            'delivery_address': delivery_address,
            'payment_method': payment_method,
            'notes': request.data.get('notes', past_order.notes),
            'items': items_payload,
        }

        serializer = OrderCreateSerializer(data=order_data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        new_order = serializer.save()

        return Response({
            'message': f"Order #{new_order.order_number} created via 1-click reorder.",
            'order': OrderSerializer(new_order).data
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def toggle_save(self, request, pk=None):
        """
        POST /api/v1/orders/<id>/toggle-save/
        Saves or unsaves an order as a favorite for quick reordering.
        """
        order = self.get_object()
        name = request.data.get('name', order.saved_order_name or 'Favorite Order')

        order.is_saved_order = not order.is_saved_order
        if order.is_saved_order:
            order.saved_order_name = name
        order.save(update_fields=['is_saved_order', 'saved_order_name'])

        status_text = 'saved to favorites' if order.is_saved_order else 'removed from favorites'
        return Response({
            'message': f"Order #{order.order_number} {status_text}.",
            'isSavedOrder': order.is_saved_order,
            'savedOrderName': order.saved_order_name,
        })

    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def saved_orders(self, request):
        """
        GET /api/v1/orders/saved-orders/
        Lists all favorite saved orders for the customer.
        """
        orders = Order.objects.filter(customer=request.user, is_saved_order=True).order_by('-updated_at')
        serializer = OrderSerializer(orders, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def kitchen(self, request):
        """
        Kitchen Display System (KDS):
        Kitchen staff only see pending, preparing, and ready orders.
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
        Assigned deliveries and delivery status tracking.
        """
        user = request.user
        orders = Order.objects.filter(dining_type=Order.DiningType.DELIVERY).prefetch_related('items')

        if user.is_delivery_staff:
            orders = orders.filter(assigned_delivery_staff=user)

        serializer = OrderSerializer(orders, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['patch'])
    def update_status(self, request, pk=None):
        order = self.get_object()
        new_status = request.data.get('status')
        user = request.user

        if new_status not in Order.Status.values:
            return Response(
                {'error': f"Invalid status. Must be one of {Order.Status.values}"},
                status=status.HTTP_400_BAD_REQUEST
            )

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

        # Auto-deduct recipe-based inventory when order moves to preparing or ready
        if new_status in [Order.Status.PREPARING, Order.Status.READY]:
            try:
                from apps.inventory.services import deduct_order_inventory
                deduct_order_inventory(order, performed_by=user)
            except Exception:
                pass

        return Response(OrderSerializer(order).data)

    @action(detail=True, methods=['post'], permission_classes=[IsRestaurantStaff], url_path='deduct-inventory')
    def deduct_inventory(self, request, pk=None):
        """
        POST /api/v1/orders/<id>/deduct-inventory/
        Manually triggers or re-verifies recipe ingredient consumption for this order.
        """
        order = self.get_object()
        from apps.inventory.services import deduct_order_inventory
        from apps.inventory.serializers import StockMovementSerializer
        movements = deduct_order_inventory(order, performed_by=request.user)
        return Response({
            'message': f"Inventory deducted for order #{order.order_number}.",
            'movements_count': len(movements),
            'movements': StockMovementSerializer(movements, many=True).data
        })

    @action(detail=True, methods=['post'], permission_classes=[IsRestaurantStaff])
    def assign_delivery(self, request, pk=None):
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


class CustomerAddressViewSet(viewsets.ModelViewSet):
    """
    CRUD saved delivery addresses for registered customers.
    """
    serializer_class = CustomerAddressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return CustomerAddress.objects.filter(user=self.request.user)

    @action(detail=True, methods=['post'])
    def set_default(self, request, pk=None):
        addr = self.get_object()
        CustomerAddress.objects.filter(user=request.user).update(is_default=False)
        addr.is_default = True
        addr.save(update_fields=['is_default', 'updated_at'])
        return Response({'message': f"Address '{addr.label}' is now default."})


class CartViewSet(viewsets.ViewSet):
    """
    Online Shopping Cart API for Guests and Registered Customers:
    - Add to cart with portion sizes, extras, ingredients, and special instructions.
    - Update quantities and see real-time price calculations.
    - Direct checkout from cart.
    """
    permission_classes = [permissions.AllowAny]

    def list(self, request):
        """
        GET /api/v1/orders/cart/
        Retrieves active cart and computed totals.
        """
        cart = get_or_create_cart(request)
        serializer = CartSerializer(cart)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='items')
    def add_item(self, request):
        """
        POST /api/v1/orders/cart/items/
        Add product to cart with portion, extras, customizations, and special instructions.
        """
        cart = get_or_create_cart(request)
        serializer = CartItemAddSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        dish = Dish.objects.get(id=data['dish_id'])
        portion = None
        if data.get('portion_option_id'):
            portion = DishPortionOption.objects.filter(id=data['portion_option_id'], dish=dish).first()

        item = CartItem.objects.create(
            cart=cart,
            dish=dish,
            quantity=data.get('quantity', 1),
            portion_option=portion,
            customizations=data.get('customizations', {}),
            special_instructions=data.get('special_instructions', '')
        )

        extra_ids = data.get('extra_option_ids', [])
        if extra_ids:
            extras = DishExtraOption.objects.filter(id__in=extra_ids, dish=dish)
            item.extra_options.set(extras)

        cart.save(update_fields=['updated_at'])
        return Response(CartSerializer(cart).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['patch', 'put'], url_path='items/(?P<item_id>[0-9]+)')
    def update_item(self, request, item_id=None):
        """
        PATCH /api/v1/orders/cart/items/<item_id>/
        Update item quantity or special instructions.
        """
        cart = get_or_create_cart(request)
        item = CartItem.objects.filter(id=item_id, cart=cart).first()
        if not item:
            return Response({'error': 'Cart item not found.'}, status=status.HTTP_404_NOT_FOUND)

        new_qty = request.data.get('quantity')
        if new_qty is not None:
            if int(new_qty) <= 0:
                item.delete()
            else:
                item.quantity = int(new_qty)
                item.save(update_fields=['quantity'])

        if 'special_instructions' in request.data:
            item.special_instructions = request.data['special_instructions']
            item.save(update_fields=['special_instructions'])

        cart.save(update_fields=['updated_at'])
        return Response(CartSerializer(cart).data)

    @action(detail=False, methods=['delete'], url_path='items/(?P<item_id>[0-9]+)/remove')
    def remove_item(self, request, item_id=None):
        """
        DELETE /api/v1/orders/cart/items/<item_id>/remove/
        Remove item from cart.
        """
        cart = get_or_create_cart(request)
        item = CartItem.objects.filter(id=item_id, cart=cart).first()
        if item:
            item.delete()
            cart.save(update_fields=['updated_at'])
        return Response(CartSerializer(cart).data)

    @action(detail=False, methods=['post'])
    def clear(self, request):
        """
        POST /api/v1/orders/cart/clear/
        """
        cart = get_or_create_cart(request)
        cart.clear()
        return Response(CartSerializer(cart).data)

    @action(detail=False, methods=['patch'])
    def options(self, request):
        """
        PATCH /api/v1/orders/cart/options/
        Update delivery vs collection, scheduled time, and order notes.
        """
        cart = get_or_create_cart(request)
        if 'dining_type' in request.data:
            cart.dining_type = request.data['dining_type']
        if 'schedule_type' in request.data:
            cart.schedule_type = request.data['schedule_type']
        if 'scheduled_for' in request.data:
            cart.scheduled_for = request.data['scheduled_for']
        if 'notes' in request.data:
            cart.notes = request.data['notes']
        cart.save()
        return Response(CartSerializer(cart).data)

    @action(detail=False, methods=['post'])
    def checkout(self, request):
        """
        POST /api/v1/orders/cart/checkout/
        Direct checkout of the active cart into an Order.
        Supports Guest Checkout and Authenticated Checkout.
        """
        cart = get_or_create_cart(request)
        if not cart.items.exists():
            return Response(
                {'error': 'Your cart is empty. Add items before checking out.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = request.user if request.user.is_authenticated else None

        # Build items payload from cart
        items_payload = []
        for item in cart.items.select_related('dish', 'portion_option').prefetch_related('extra_options'):
            customs = dict(item.customizations)
            if item.portion_option:
                customs['portion'] = {
                    'name': item.portion_option.name,
                    'price_delta': float(item.portion_option.price_delta)
                }
            if item.extra_options.exists():
                customs['extras'] = [
                    {'name': e.name, 'price': float(e.price)}
                    for e in item.extra_options.all()
                ]

            items_payload.append({
                'dish_id': item.dish_id,
                'name': item.dish.name,
                'quantity': item.quantity,
                'price': item.unit_price,
                'station': item.dish.station,
                'customizations': customs,
                'special_instructions': item.special_instructions,
            })

        order_data = {
            'customer_name': request.data.get('customer_name') or (user.get_full_name() or user.username if user else ''),
            'customer_phone': request.data.get('customer_phone') or (user.phone if user else ''),
            'customer_email': request.data.get('customer_email') or (user.email if user else ''),
            'dining_type': request.data.get('dining_type') or cart.dining_type,
            'schedule_type': request.data.get('schedule_type') or cart.schedule_type,
            'scheduled_for': request.data.get('scheduled_for') or cart.scheduled_for,
            'delivery_address': request.data.get('delivery_address', ''),
            'saved_address_id': request.data.get('saved_address_id'),
            'payment_method': request.data.get('payment_method', Order.PaymentMethod.CARD),
            'notes': request.data.get('notes') or cart.notes,
            'items': items_payload,
        }

        serializer = OrderCreateSerializer(data=order_data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        order = serializer.save()

        # Clear cart on successful checkout
        cart.clear()

        return Response({
            'message': 'Order placed successfully!',
            'order': OrderSerializer(order).data
        }, status=status.HTTP_201_CREATED)
