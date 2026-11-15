from decimal import Decimal
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import transaction
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.engagement.models import RestaurantProfile
from .delivery_serializers import (RiderSummarySerializer, RiderProfileUpdateSerializer,
                                   RiderJobSerializer, RiderNoteSerializer, RiderIssueSerializer)
from .delivery_workflow import DeliveryWorkflow
from .models import Order, RiderProfile


class CanUseRiderWorkspace(permissions.BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active and user.is_delivery_staff
                    and user.has_restaurant_permission('deliveries:view_assigned')
                    and (request.method in permissions.SAFE_METHODS or user.has_restaurant_permission('deliveries:update_status')))


def rider_summary(user, profile):
    zone = ZoneInfo(getattr(settings, 'RESTAURANT_TIME_ZONE', 'Europe/Dublin'))
    today = timezone.now().astimezone(zone).date()
    start = datetime.combine(today, time.min, tzinfo=zone)
    end = datetime.combine(today + timedelta(days=1), time.min, tzinfo=zone)
    orders = Order.objects.filter(assigned_delivery_staff=user, dining_type='delivery')
    location = RestaurantProfile.objects.order_by('id').first()
    return {
        'userId': user.id, 'name': user.get_full_name() or user.username, 'phone': user.phone or '',
        'onDuty': profile.on_duty, 'vehicleType': profile.vehicle_type, 'vehicleRegistration': profile.vehicle_registration,
        'timezone': str(zone), 'activeJobs': orders.exclude(status__in=['delivered', 'cancelled']).count(),
        'pendingAssignments': orders.filter(delivery_job__stage='assigned').exclude(status__in=['delivered', 'cancelled']).count(),
        'deliveredToday': orders.filter(status='delivered', delivery_job__delivered_at__gte=start, delivery_job__delivered_at__lt=end).count(),
        'cashCollectedToday': orders.filter(payment_method='cash', payment_status='paid', delivery_job__cash_collected_at__gte=start, delivery_job__cash_collected_at__lt=end).aggregate(total=Sum('total_amount'))['total'] or Decimal('0'),
        'cashOutstanding': orders.filter(status='delivered', payment_method='cash', payment_status='pending').aggregate(total=Sum('total_amount'))['total'] or Decimal('0'),
        'pickupLocation': {'name': location.name, 'address': ', '.join(filter(None, [location.address, location.city])), 'phone': location.phone} if location else None,
    }


class RiderProfileView(APIView):
    permission_classes = [CanUseRiderWorkspace]

    @extend_schema(responses=RiderSummarySerializer, tags=['Rider'], description='JWT delivery_staff with deliveries:view_assigned. Own shift, vehicle, assigned job counts, recorded cash totals and configured pickup address. New riders start off duty.')
    def get(self, request):
        profile, _ = RiderProfile.objects.get_or_create(user=request.user)
        return Response(RiderSummarySerializer(rider_summary(request.user, profile)).data)

    @extend_schema(request=RiderProfileUpdateSerializer, responses=RiderSummarySerializer, tags=['Rider'], description='JWT delivery_staff with deliveries:view_assigned and deliveries:update_status. Start/end shift or update vehicle. Cannot end shift with an accepted/in-transit delivery or delivered cash still uncollected.')
    @transaction.atomic
    def patch(self, request):
        profile, _ = RiderProfile.objects.select_for_update().get_or_create(user=request.user)
        serializer = RiderProfileUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if serializer.validated_data.get('on_duty') is False:
            outstanding = Order.objects.filter(assigned_delivery_staff=request.user, dining_type='delivery').filter(
                Q(delivery_job__stage__in=['accepted', 'picked_up', 'arrived', 'returning']) & ~Q(status__in=['delivered', 'cancelled'])
                | Q(status='delivered', payment_method='cash', payment_status='pending'))
            if outstanding.exists():
                raise ValidationError({'on_duty': 'Complete or decline accepted jobs and confirm outstanding cash before ending your shift.'})
        for key, value in serializer.validated_data.items():
            setattr(profile, key, value)
        profile.save()
        return Response(RiderSummarySerializer(rider_summary(request.user, profile)).data)


@extend_schema_view(
    list=extend_schema(tags=['Rider'], parameters=[OpenApiParameter('scope', str, enum=['active', 'completed', 'all'])],
                       description='JWT delivery_staff with deliveries:view_assigned. Paginated own assigned deliveries only. active includes delivered cash orders awaiting collection; completed includes paid/non-cash delivered and cancelled. All writes require deliveries:update_status.'),
    retrieve=extend_schema(tags=['Rider'], description='JWT delivery_staff. Own assigned order, package list, customer contact, delivery address, issue/audit history and server-calculated availableActions. Other riders’ order IDs return 404.'),
)
class RiderJobViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [CanUseRiderWorkspace]
    serializer_class = RiderJobSerializer
    queryset = Order.objects.all()

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False) or not self.request.user.is_authenticated:
            return Order.objects.none()
        rows = Order.objects.filter(dining_type='delivery', assigned_delivery_staff=self.request.user).select_related(
            'delivery_job', 'assigned_delivery_staff__rider_profile').prefetch_related('items', 'delivery_events__actor')
        if self.action == 'list':
            scope = self.request.query_params.get('scope', 'active')
            if scope not in ['active', 'completed', 'all']:
                raise ValidationError({'scope': 'Use active, completed or all.'})
            active = ~Q(status__in=['delivered', 'cancelled']) | Q(status='delivered', payment_method='cash', payment_status='pending')
            if scope == 'active':
                rows = rows.filter(active)
            elif scope == 'completed':
                rows = rows.exclude(active)
        return rows.order_by('-created_at', '-id')

    def locked_order(self, pk):
        return get_object_or_404(self.get_queryset().select_for_update(of=('self',)), pk=pk)

    def saved_response(self, order):
        order = self.get_queryset().get(pk=order.pk)
        return Response(self.get_serializer(order).data)

    def progress(self, request, pk, action):
        order = self.locked_order(pk)
        DeliveryWorkflow.progress(order, request.user, action)
        return self.saved_response(order)

    @extend_schema(request=None, responses=RiderJobSerializer, tags=['Rider'], description='JWT assigned rider on duty. Accept assignment. Safe to retry; does not dispatch food.')
    @action(detail=True, methods=['post'])
    @transaction.atomic
    def accept(self, request, pk=None):
        return self.progress(request, pk, 'accept')

    @extend_schema(request=None, responses=RiderJobSerializer, tags=['Rider'], description='JWT assigned rider on duty. Requires accepted assignment and ready kitchen status. Records pickup and changes order to out_for_delivery. Safe to retry.')
    @action(detail=True, methods=['post'])
    @transaction.atomic
    def pickup(self, request, pk=None):
        return self.progress(request, pk, 'pickup')

    @extend_schema(request=None, responses=RiderJobSerializer, tags=['Rider'], description='JWT assigned rider on duty. Requires pickup. Records arrival at the delivery address. Safe to retry.')
    @action(detail=True, methods=['post'])
    @transaction.atomic
    def arrive(self, request, pk=None):
        return self.progress(request, pk, 'arrive')

    @extend_schema(request=None, responses=RiderJobSerializer, tags=['Rider'], description='JWT assigned rider on duty. Requires recorded arrival and no unresolved issue. Confirm actual handover, then cash collection separately. Safe to retry.')
    @action(detail=True, methods=['post'])
    @transaction.atomic
    def complete(self, request, pk=None):
        return self.progress(request, pk, 'complete')

    @extend_schema(request=RiderNoteSerializer, responses={204: None}, tags=['Rider'], description='JWT assigned rider. Required note. Before pickup only; returns order to restaurant for reassignment. Does not cancel the order. Reload the queue after success.')
    @action(detail=True, methods=['post'])
    @transaction.atomic
    def decline(self, request, pk=None):
        order = self.locked_order(pk)
        serializer = RiderNoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        DeliveryWorkflow.decline(order, request.user, serializer.validated_data['note'])
        return Response(status=204)

    @extend_schema(request=RiderIssueSerializer, responses=RiderJobSerializer, tags=['Rider'], description='JWT assigned rider. Required code and note. Pauses progress until restaurant operations resolve the issue; never marks an unsuccessful delivery completed.')
    @action(detail=True, methods=['post'], url_path='report-issue')
    @transaction.atomic
    def report_issue(self, request, pk=None):
        order = self.locked_order(pk)
        serializer = RiderIssueSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        DeliveryWorkflow.report_issue(order, request.user, **serializer.validated_data)
        return self.saved_response(order)

    @extend_schema(request=None, responses=RiderJobSerializer, tags=['Rider'], description='JWT assigned rider. Confirm actual receipt of the full cash total after delivery. Records one cash receipt; replay returns saved state. Does not charge a card or calculate rider earnings.')
    @action(detail=True, methods=['post'], url_path='collect-cash')
    @transaction.atomic
    def collect_cash(self, request, pk=None):
        order = self.locked_order(pk)
        DeliveryWorkflow.record_cash(order, request.user)
        return self.saved_response(order)

    @extend_schema(request=None, responses=RiderJobSerializer, tags=['Rider'], description='JWT assigned rider on duty. Only after dispatch approves return. Confirm actual handover back to restaurant staff. Cancels the undelivered order; performs no payment/refund. Safe to retry.')
    @action(detail=True, methods=['post'], url_path='confirm-return')
    @transaction.atomic
    def confirm_return(self, request, pk=None):
        order = self.locked_order(pk)
        DeliveryWorkflow.confirm_return(order, request.user)
        return self.saved_response(order)
