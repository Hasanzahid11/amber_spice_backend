from rest_framework import serializers
from datetime import datetime, time
from django.utils import timezone
from .models import Reservation, Table


class TableSerializer(serializers.ModelSerializer):
    currentOrder = serializers.CharField(source='current_order', required=False, allow_null=True, allow_blank=True)
    guestName = serializers.CharField(source='guest_name', required=False, allow_null=True, allow_blank=True)
    timeSlot = serializers.CharField(source='time_slot', required=False, allow_null=True, allow_blank=True)

    class Meta:
        model = Table
        fields = [
            'id',
            'number',
            'capacity',
            'status',
            'currentOrder',
            'guestName',
            'timeSlot',
        ]


class ReservationSerializer(serializers.ModelSerializer):
    guestName = serializers.CharField(source='guest_name')
    guestPhone = serializers.CharField(source='guest_phone')
    guestEmail = serializers.EmailField(source='guest_email', required=False, allow_blank=True)
    guestsCount = serializers.IntegerField(source='guests_count', min_value=1, max_value=100, default=2)
    reservationDate = serializers.DateField(source='reservation_date')
    timeSlot = serializers.CharField(source='time_slot')
    specialRequests = serializers.CharField(source='special_requests', required=False, allow_blank=True)
    tableDetails = TableSerializer(source='table', read_only=True)
    tableNumber = serializers.CharField(source='table.number', read_only=True)
    guestArrivedAt = serializers.DateTimeField(source='guest_arrived_at', read_only=True)

    class Meta:
        model = Reservation
        fields = [
            'id',
            'table',
            'tableNumber',
            'tableDetails',
            'customer',
            'guestName',
            'guestPhone',
            'guestEmail',
            'guestsCount',
            'reservationDate',
            'timeSlot',
            'status',
            'specialRequests',
            'created_at',
            'guestArrivedAt',
            'booking_reference',
        ]
        read_only_fields = ['customer', 'created_at', 'booking_reference', 'tableNumber', 'guestArrivedAt']
        validators = []

    def validate(self, attrs):
        day = attrs.get('reservation_date', self.instance.reservation_date if self.instance else None)
        slot = attrs.get('time_slot', self.instance.time_slot if self.instance else '')
        try:
            parsed = time.fromisoformat(slot)
            if parsed.second or parsed.microsecond:
                raise ValueError()
        except ValueError:
            raise serializers.ValidationError({'timeSlot': 'Use HH:MM format.'})
        if not self.instance and timezone.make_aware(datetime.combine(day, parsed)) <= timezone.now():
            raise serializers.ValidationError({'reservationDate': 'Select a future reservation time.'})
        attrs['time_slot'] = parsed.strftime('%H:%M')
        table = attrs.get('table', self.instance.table if self.instance else None)
        guests = attrs.get('guests_count', self.instance.guests_count if self.instance else 2)
        if table and table.capacity < guests:
            raise serializers.ValidationError({'table': 'This table does not have enough seats.'})
        if table and attrs.get('status', self.instance.status if self.instance else 'confirmed') in ['pending', 'confirmed']:
            conflict = Reservation.objects.filter(table=table, reservation_date=day, time_slot=attrs['time_slot'], status__in=['pending', 'confirmed'])
            if self.instance:
                conflict = conflict.exclude(pk=self.instance.pk)
            if conflict.exists():
                raise serializers.ValidationError({'table': 'This table is already booked for that time.'})
        return attrs

