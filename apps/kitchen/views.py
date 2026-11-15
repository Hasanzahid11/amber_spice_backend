from datetime import timedelta
from django.db.models import Avg, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import CanAccessKitchenKDS, IsManagerOrAdmin
from apps.orders.models import Order, OrderItem
from .models import KitchenStation, KitchenScreen, KitchenBumpLog
from .serializers import (
    KitchenStationSerializer,
    KitchenScreenSerializer,
    KitchenBumpLogSerializer,
    KitchenTicketSerializer,
    KitchenOrderItemSerializer,
    KitchenSummarySerializer,
)


class KitchenStationViewSet(viewsets.ModelViewSet):
    """
    CRUD for Kitchen Stations (e.g. Grill, Curry, Biryani, Tandoor, Expeditor).
    """
    queryset = KitchenStation.objects.all()
    serializer_class = KitchenStationSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [CanAccessKitchenKDS()]
        return [IsManagerOrAdmin()]


class KitchenScreenViewSet(viewsets.ModelViewSet):
    """
    CRUD for Kitchen Screen configurations and terminal monitors.
    """
    queryset = KitchenScreen.objects.all()
    serializer_class = KitchenScreenSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [CanAccessKitchenKDS()]
        return [IsManagerOrAdmin()]


class KitchenDisplayViewSet(viewsets.ViewSet):
    """
    Kitchen Display System (KDS) ViewSet:
    Provides incoming order queues, active tickets, status progression (New -> Preparing -> Ready),
    station filtering, delayed order monitoring, priority controls, and bump logs.
    """
    permission_classes = [CanAccessKitchenKDS]

    def list(self, request):
        """
        GET /api/v1/kitchen/tickets/ or /api/v1/kitchen/orders/
        Returns incoming and active kitchen tickets for display screens.
        Supports query params:
        - station: filter dishes/orders by station slug (e.g. 'curry', 'grill')
        - status: 'pending', 'preparing', 'ready', or 'all'
        - priority: 'normal', 'high', 'urgent'
        - dining_type: 'dine_in', 'takeaway', 'delivery'
        - delayed_only: 'true' (returns only orders that exceeded their prep target)
        - screen_id: UUID of KitchenScreen to load terminal-specific configuration
        """
        station = request.query_params.get('station', None)
        status_param = request.query_params.get('status', None)
        priority_param = request.query_params.get('priority', None)
        dining_type = request.query_params.get('dining_type', None)
        delayed_only = request.query_params.get('delayed_only', '').lower() in ['true', '1']
        screen_id = request.query_params.get('screen_id', None)

        # Screen configuration overrides
        screen = None
        if screen_id:
            screen = KitchenScreen.objects.filter(id=screen_id, is_active=True).first()
            if screen and screen.station and not station:
                station = screen.station.slug

        active_statuses = [Order.Status.PENDING, Order.Status.PREPARING, Order.Status.READY]
        if status_param and status_param in Order.Status.values:
            orders_qs = Order.objects.filter(status=status_param)
        elif status_param == 'all':
            orders_qs = Order.objects.all()
        else:
            orders_qs = Order.objects.filter(status__in=active_statuses)

        if priority_param and priority_param in Order.Priority.values:
            orders_qs = orders_qs.filter(priority=priority_param)

        if dining_type and dining_type in Order.DiningType.values:
            orders_qs = orders_qs.filter(dining_type=dining_type)

        orders_qs = orders_qs.prefetch_related('items__dish').select_related('customer')

        if station and station != 'all':
            orders_qs = orders_qs.filter(items__station=station).distinct()

        orders_list = list(orders_qs)
        if delayed_only:
            orders_list = [o for o in orders_list if o.is_delayed]

        # Sort: Urgent first, High second, Normal third; within same priority, oldest first
        priority_weight = {Order.Priority.URGENT: 0, Order.Priority.HIGH: 1, Order.Priority.NORMAL: 2}
        orders_list.sort(key=lambda o: (priority_weight.get(o.priority, 2), o.created_at))

        serializer = KitchenTicketSerializer(
            orders_list,
            many=True,
            context={'station_filter': station, 'screen': screen}
        )
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """
        GET /api/v1/kitchen/tickets/summary/ or /api/v1/kitchen/summary/
        Header counters for active, new, preparing, ready, delayed, and urgent orders.
        """
        active_statuses = [Order.Status.PENDING, Order.Status.PREPARING, Order.Status.READY]
        active_orders = list(Order.objects.filter(status__in=active_statuses))

        new_count = sum(1 for o in active_orders if o.status == Order.Status.PENDING)
        prep_count = sum(1 for o in active_orders if o.status == Order.Status.PREPARING)
        ready_count = sum(1 for o in active_orders if o.status == Order.Status.READY)
        delayed_count = sum(1 for o in active_orders if o.is_delayed)
        critical_count = sum(1 for o in active_orders if o.delay_severity == 'critical')
        urgent_count = sum(1 for o in active_orders if o.priority == Order.Priority.URGENT)

        # Average prep time calculation for completed/ready orders today
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        ready_orders_today = Order.objects.filter(
            ready_at__gte=today_start,
            prepared_at__isnull=False
        )
        avg_minutes = 0.0
        if ready_orders_today.exists():
            diffs = [
                (o.ready_at - o.created_at).total_seconds() / 60.0
                for o in ready_orders_today
                if o.ready_at and o.created_at
            ]
            if diffs:
                avg_minutes = round(sum(diffs) / len(diffs), 1)

        data = {
            'totalActiveOrders': len(active_orders),
            'newOrdersCount': new_count,
            'preparingOrdersCount': prep_count,
            'readyOrdersCount': ready_count,
            'delayedOrdersCount': delayed_count,
            'criticalDelayedOrdersCount': critical_count,
            'urgentPriorityCount': urgent_count,
            'averagePrepTimeMinutes': avg_minutes,
            'timestamp': timezone.now().isoformat(),
        }
        return Response(data)

    @action(detail=True, methods=['post'])
    def bump(self, request, pk=None):
        """
        POST /api/v1/kitchen/tickets/<id>/bump/
        1-Click Status Progression: PENDING (New) -> PREPARING -> READY.
        """
        try:
            order = Order.objects.get(pk=pk)
        except Order.DoesNotExist:
            return Response({'error': 'Order not found.'}, status=status.HTTP_404_NOT_FOUND)

        old_status = order.status
        if old_status == Order.Status.PENDING:
            order.mark_preparing(user=request.user)
            KitchenBumpLog.objects.create(
                order=order,
                action=KitchenBumpLog.Action.START_PREP,
                performed_by=request.user if request.user.is_authenticated else None,
                from_status=old_status,
                to_status=order.status,
                notes="Bumped to preparing on KDS"
            )
        elif old_status == Order.Status.PREPARING:
            order.mark_ready(user=request.user)
            KitchenBumpLog.objects.create(
                order=order,
                action=KitchenBumpLog.Action.MARK_READY,
                performed_by=request.user if request.user.is_authenticated else None,
                from_status=old_status,
                to_status=order.status,
                notes="Bumped to ready on KDS"
            )
        else:
            return Response({
                'message': f"Order #{order.order_number} is already in status '{order.status}'.",
                'status': order.status,
                'order': KitchenTicketSerializer(order).data,
            })

        return Response({
            'message': f"Order #{order.order_number} progressed from {old_status} to {order.status}.",
            'status': order.status,
            'order': KitchenTicketSerializer(order).data,
        })

    @action(detail=True, methods=['post'], url_path='start-prep')
    def start_prep(self, request, pk=None):
        """
        POST /api/v1/kitchen/tickets/<id>/start-prep/
        Marks order as PREPARING and logs recipe inventory consumption.
        """
        try:
            order = Order.objects.get(pk=pk)
        except Order.DoesNotExist:
            return Response({'error': 'Order not found.'}, status=status.HTTP_404_NOT_FOUND)

        old_status = order.status
        order.mark_preparing(user=request.user)
        KitchenBumpLog.objects.create(
            order=order,
            action=KitchenBumpLog.Action.START_PREP,
            performed_by=request.user if request.user.is_authenticated else None,
            from_status=old_status,
            to_status=order.status,
            notes="Chef started preparation"
        )
        return Response({
            'message': f"Order #{order.order_number} is now PREPARING in the kitchen.",
            'status': order.status,
            'order': KitchenTicketSerializer(order).data,
        })

    @action(detail=True, methods=['post'], url_path='mark-ready')
    def mark_ready(self, request, pk=None):
        """
        POST /api/v1/kitchen/tickets/<id>/mark-ready/
        Marks order as READY and completes all ticket items.
        """
        try:
            order = Order.objects.get(pk=pk)
        except Order.DoesNotExist:
            return Response({'error': 'Order not found.'}, status=status.HTTP_404_NOT_FOUND)

        old_status = order.status
        order.mark_ready(user=request.user)
        KitchenBumpLog.objects.create(
            order=order,
            action=KitchenBumpLog.Action.MARK_READY,
            performed_by=request.user if request.user.is_authenticated else None,
            from_status=old_status,
            to_status=order.status,
            notes="Order marked ready for pickup / delivery"
        )
        return Response({
            'message': f"Order #{order.order_number} is READY for service.",
            'status': order.status,
            'order': KitchenTicketSerializer(order).data,
        })

    @action(detail=True, methods=['post'])
    def recall(self, request, pk=None):
        """
        POST /api/v1/kitchen/tickets/<id>/recall/
        Recalls a bumped order back to PREPARING if marked ready prematurely.
        """
        try:
            order = Order.objects.get(pk=pk)
        except Order.DoesNotExist:
            return Response({'error': 'Order not found.'}, status=status.HTTP_404_NOT_FOUND)

        old_status = order.status
        order.status = Order.Status.PREPARING
        order.ready_at = None
        order.save(update_fields=['status', 'ready_at', 'updated_at'])

        KitchenBumpLog.objects.create(
            order=order,
            action=KitchenBumpLog.Action.RECALL,
            performed_by=request.user if request.user.is_authenticated else None,
            from_status=old_status,
            to_status=order.status,
            notes=request.data.get('reason', 'Ticket recalled by kitchen staff')
        )

        return Response({
            'message': f"Order #{order.order_number} recalled back to PREPARING.",
            'status': order.status,
            'order': KitchenTicketSerializer(order).data,
        })

    @action(detail=True, methods=['post'], url_path='toggle-item')
    def toggle_item(self, request, pk=None):
        """
        POST /api/v1/kitchen/tickets/<id>/toggle-item/
        Body: {"item_id": "<item_uuid_or_int>", "is_ready": true/false (optional)}
        Toggles item readiness on the station display.
        """
        try:
            order = Order.objects.get(pk=pk)
        except Order.DoesNotExist:
            return Response({'error': 'Order not found.'}, status=status.HTTP_404_NOT_FOUND)

        item_id = request.data.get('item_id')
        if not item_id:
            return Response({'error': 'item_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            item = order.items.get(pk=item_id)
        except OrderItem.DoesNotExist:
            return Response({'error': f"Item {item_id} not found in this order."}, status=status.HTTP_404_NOT_FOUND)

        explicit_ready = request.data.get('is_ready')
        if explicit_ready is not None:
            item.is_ready = bool(explicit_ready)
        else:
            item.is_ready = not item.is_ready

        if item.is_ready:
            item.prepared_at = timezone.now()
            action_code = KitchenBumpLog.Action.ITEM_READY
        else:
            item.prepared_at = None
            action_code = KitchenBumpLog.Action.ITEM_UNREADY

        item.save(update_fields=['is_ready', 'prepared_at'])

        KitchenBumpLog.objects.create(
            order=order,
            item=item,
            action=action_code,
            performed_by=request.user if request.user.is_authenticated else None,
            from_status=order.status,
            to_status=order.status,
            notes=f"Item '{item.name}' marked {'ready' if item.is_ready else 'reopened'}"
        )

        # Check if all items in order are now ready
        all_ready = order.items.filter(is_ready=False).count() == 0

        return Response({
            'message': f"Item '{item.name}' is now {'READY' if item.is_ready else 'PENDING'}.",
            'itemId': item.id,
            'isReady': item.is_ready,
            'allReady': all_ready,
            'order': KitchenTicketSerializer(order).data,
        })

    @action(detail=True, methods=['post'], url_path='set-priority')
    def set_priority(self, request, pk=None):
        """
        POST /api/v1/kitchen/tickets/<id>/set-priority/
        Body: {"priority": "urgent" | "high" | "normal"}
        Updates preparation urgency on the KDS board.
        """
        try:
            order = Order.objects.get(pk=pk)
        except Order.DoesNotExist:
            return Response({'error': 'Order not found.'}, status=status.HTTP_404_NOT_FOUND)

        priority = request.data.get('priority', '').lower()
        if priority not in Order.Priority.values:
            return Response({
                'error': f"Invalid priority '{priority}'. Valid options: {Order.Priority.values}"
            }, status=status.HTTP_400_BAD_REQUEST)

        old_priority = order.priority
        order.priority = priority
        order.save(update_fields=['priority', 'updated_at'])

        KitchenBumpLog.objects.create(
            order=order,
            action=KitchenBumpLog.Action.SET_PRIORITY,
            performed_by=request.user if request.user.is_authenticated else None,
            from_status=order.status,
            to_status=order.status,
            notes=f"Priority updated from {old_priority} to {order.priority}"
        )

        return Response({
            'message': f"Order #{order.order_number} priority updated to {order.priority.upper()}.",
            'priority': order.priority,
            'order': KitchenTicketSerializer(order).data,
        })

    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        """
        GET /api/v1/kitchen/tickets/<id>/history/
        Returns complete audit log of bump events for this ticket.
        """
        try:
            order = Order.objects.get(pk=pk)
        except Order.DoesNotExist:
            return Response({'error': 'Order not found.'}, status=status.HTTP_404_NOT_FOUND)

        logs = order.kitchen_bump_logs.select_related('performed_by', 'station', 'item').all()
        serializer = KitchenBumpLogSerializer(logs, many=True)
        return Response(serializer.data)


class KitchenBumpLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only viewset for auditing all kitchen bump logs across all stations.
    """
    queryset = KitchenBumpLog.objects.select_related('order', 'performed_by', 'station', 'item').all()
    serializer_class = KitchenBumpLogSerializer
    permission_classes = [CanAccessKitchenKDS]

