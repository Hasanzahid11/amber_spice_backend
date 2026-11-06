from rest_framework import serializers
from .models import Reservation, Table


class TableSerializer(serializers.ModelSerializer):
    currentOrder = serializers.CharField(source='current_order', required=False, allow_null=True)
    guestName = serializers.CharField(source='guest_name', required=False, allow_null=True)
    timeSlot = serializers.CharField(source='time_slot', required=False, allow_null=True)

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
    guestsCount = serializers.IntegerField(source='guests_count', default=2)
    reservationDate = serializers.DateField(source='reservation_date')
    timeSlot = serializers.CharField(source='time_slot')
    specialRequests = serializers.CharField(source='special_requests', required=False, allow_blank=True)
    tableDetails = TableSerializer(source='table', read_only=True)

    class Meta:
        model = Reservation
        fields = [
            'id',
            'table',
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
        ]

