from django.db import transaction, IntegrityError
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiParameter, inline_serializer
from rest_framework import permissions, viewsets, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from apps.accounts.permissions import HasRestaurantPermission
from .models import Reservation, Table
from .serializers import ReservationSerializer, TableSerializer


class TableViewSet(viewsets.ModelViewSet):
    queryset = Table.objects.all()
    serializer_class = TableSerializer
    filterset_fields = ['status', 'capacity']
    search_fields = ['number', 'guest_name', 'current_order']

    def get_permissions(self):
        if self.action == 'availability':
            return [permissions.AllowAny()]
        return [HasRestaurantPermission('reservations:view' if self.action in ['list', 'retrieve'] else 'reservations:manage')]

    @extend_schema(parameters=[OpenApiParameter('date', str), OpenApiParameter('time', str), OpenApiParameter('guests', int)],
                   responses=inline_serializer('AvailableTable', fields={'id': serializers.IntegerField(), 'number': serializers.CharField(), 'capacity': serializers.IntegerField()}, many=True),
                   description='Public table IDs and capacities without guest details. Optional date/time/guest count for reservation selection; without a slot lists available walk-in tables.')
    @action(detail=False, methods=['get'])
    def availability(self, request):
        tables = Table.objects.all()
        try:
            guests = int(request.query_params.get('guests', 1))
            if guests < 1:
                raise ValueError()
        except ValueError:
            raise serializers.ValidationError({'guests': 'Enter a positive guest count.'})
        tables = tables.filter(capacity__gte=guests)
        day, slot = request.query_params.get('date'), request.query_params.get('time')
        if day and slot:
            from datetime import date, time
            try:
                day = date.fromisoformat(day)
                slot = time.fromisoformat(slot).strftime('%H:%M')
            except ValueError:
                raise serializers.ValidationError({'date': 'Use a valid date and HH:MM time.'})
            booked = Reservation.objects.filter(reservation_date=day, time_slot=slot, status__in=['pending', 'confirmed']).values('table_id')
            tables = tables.exclude(id__in=booked)
        else:
            tables = tables.filter(status='available')
        return Response(list(tables.values('id', 'number', 'capacity')))

    def perform_update(self, serializer):
        if serializer.validated_data.get('status') == 'available':
            serializer.save(guest_name=None, current_order=None, time_slot=None)
        else:
            serializer.save()


class ReservationViewSet(viewsets.ModelViewSet):
    queryset = Reservation.objects.select_related('table', 'customer').all()
    serializer_class = ReservationSerializer
    filterset_fields = ['status', 'reservation_date', 'table']
    search_fields = ['guest_name', 'guest_phone', 'guest_email']
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_permissions(self):
        if self.action in ['create', 'track']:
            return [permissions.AllowAny()]
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated()]
        return [HasRestaurantPermission('reservations:manage')]

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return self.queryset.none()
        if self.request.user.has_restaurant_permission('reservations:view'):
            return self.queryset
        return self.queryset.filter(customer=self.request.user)

    @transaction.atomic
    def perform_create(self, serializer):
        data = serializer.validated_data
        tables = Table.objects.select_for_update().filter(capacity__gte=data.get('guests_count', 2)).order_by('capacity', 'id')
        if data.get('table'):
            tables = tables.filter(pk=data['table'].pk)
        selected = None
        for table in tables:
            if not Reservation.objects.filter(table=table, reservation_date=data['reservation_date'], time_slot=data['time_slot'], status__in=['pending', 'confirmed']).exists():
                selected = table
                break
        if not selected:
            raise serializers.ValidationError({'timeSlot': 'No table is available for this party at that time. Choose another slot.'})
        customer = self.request.user if self.request.user.is_authenticated else None
        try:
            with transaction.atomic():
                serializer.save(customer=customer, table=selected, status='confirmed')
        except IntegrityError:
            raise serializers.ValidationError({'timeSlot': 'This slot was just booked. Please choose another.'})

    @extend_schema(responses=ReservationSerializer, description='Public capability link: full random booking reference returned by creation. Keep it private.')
    @action(detail=False, methods=['get'], url_path=r'track/(?P<reference>[a-f0-9]{32})')
    def track(self, request, reference=None):
        return Response(ReservationSerializer(get_object_or_404(self.queryset, booking_reference=reference)).data)
