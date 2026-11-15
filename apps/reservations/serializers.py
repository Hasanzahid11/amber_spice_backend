import uuid
from datetime import date, time
from rest_framework import serializers

try:
    from apps.accounts.utils import normalize_phone_number
except ImportError:
    def normalize_phone_number(val):
        return val

from .models import (
    DiningArea,
    Table,
    RestaurantTable,
    ReservationSchedule,
    ReservationSetting,
    Reservation,
    ReservationNotification,
)
from .services import get_available_tables, send_reservation_notification


class DiningAreaSerializer(serializers.ModelSerializer):
    isActive = serializers.BooleanField(source='is_active', required=False)
    displayOrder = serializers.IntegerField(source='display_order', required=False)
    tablesCount = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = DiningArea
        fields = [
            'id',
            'name',
            'description',
            'is_active',
            'isActive',
            'display_order',
            'displayOrder',
            'tablesCount',
            'created_at',
            'updated_at',
        ]

    def get_tablesCount(self, obj) -> int:
        return obj.tables.filter(is_active=True).count()

    def to_internal_value(self, data):
        normalized = dict(data)
        if 'isActive' in normalized and 'is_active' not in normalized:
            normalized['is_active'] = normalized['isActive']
        if 'displayOrder' in normalized and 'display_order' not in normalized:
            normalized['display_order'] = normalized['displayOrder']
        return super().to_internal_value(normalized)


class TableSerializer(serializers.ModelSerializer):
    # Old API compatibility fields
    sectionDisplay = serializers.CharField(source='get_section_display', read_only=True)
    currentOrder = serializers.CharField(source='current_order', required=False, allow_null=True, allow_blank=True)
    guestName = serializers.CharField(source='guest_name', required=False, allow_null=True, allow_blank=True)
    timeSlot = serializers.CharField(source='time_slot', required=False, allow_null=True, allow_blank=True)
    isActive = serializers.BooleanField(source='is_active', required=False)

    # Modern floor plan fields
    tableNumber = serializers.CharField(source='number', required=False)
    minCapacity = serializers.IntegerField(source='min_capacity', required=False)
    maxCapacity = serializers.IntegerField(source='max_capacity', required=False)
    shapeDisplay = serializers.CharField(source='get_shape_display', read_only=True)
    isCombinable = serializers.BooleanField(source='is_combinable', required=False)
    diningArea = serializers.PrimaryKeyRelatedField(
        source='dining_area',
        queryset=DiningArea.objects.all(),
        required=False,
        allow_null=True
    )
    diningAreaDetails = DiningAreaSerializer(source='dining_area', read_only=True)

    class Meta:
        model = Table
        fields = [
            # Legacy fields (preserved 100%)
            'id',
            'number',
            'capacity',
            'section',
            'sectionDisplay',
            'status',
            'currentOrder',
            'guestName',
            'timeSlot',
            'isActive',
            # Modern fields
            'tableNumber',
            'dining_area',
            'diningArea',
            'diningAreaDetails',
            'min_capacity',
            'minCapacity',
            'max_capacity',
            'maxCapacity',
            'shape',
            'shapeDisplay',
            'is_combinable',
            'isCombinable',
            'priority',
        ]

    def to_internal_value(self, data):
        normalized = dict(data)
        mappings = {
            'table_number': 'number',
            'tableNumber': 'number',
            'isActive': 'is_active',
            'currentOrder': 'current_order',
            'guestName': 'guest_name',
            'timeSlot': 'time_slot',
            'minCapacity': 'min_capacity',
            'maxCapacity': 'max_capacity',
            'isCombinable': 'is_combinable',
            'diningArea': 'dining_area',
        }
        for src, target in mappings.items():
            if src in normalized and target not in normalized:
                normalized[target] = normalized[src]

        return super().to_internal_value(normalized)


class ReservationScheduleSerializer(serializers.ModelSerializer):
    dayName = serializers.CharField(source='get_day_of_week_display', read_only=True)
    lunchStart = serializers.TimeField(source='lunch_start', required=False, allow_null=True)
    lunchEnd = serializers.TimeField(source='lunch_end', required=False, allow_null=True)
    dinnerStart = serializers.TimeField(source='dinner_start', required=False, allow_null=True)
    dinnerEnd = serializers.TimeField(source='dinner_end', required=False, allow_null=True)
    isClosed = serializers.BooleanField(source='is_closed', required=False)

    class Meta:
        model = ReservationSchedule
        fields = [
            'id',
            'day_of_week',
            'dayName',
            'lunch_start',
            'lunchStart',
            'lunch_end',
            'lunchEnd',
            'dinner_start',
            'dinnerStart',
            'dinner_end',
            'dinnerEnd',
            'is_closed',
            'isClosed',
        ]


class ReservationSettingSerializer(serializers.ModelSerializer):
    standardDurationMinutes = serializers.IntegerField(source='standard_duration_minutes', required=False)
    largePartyDurationMinutes = serializers.IntegerField(source='large_party_duration_minutes', required=False)
    minPartySize = serializers.IntegerField(source='min_party_size', required=False)
    maxPartySize = serializers.IntegerField(source='max_party_size', required=False)
    minAdvanceMinutes = serializers.IntegerField(source='min_advance_minutes', required=False)
    maxAdvanceDays = serializers.IntegerField(source='max_advance_days', required=False)
    autoConfirmMaxGuests = serializers.IntegerField(source='auto_confirm_max_guests', required=False)
    cancellationDeadlineHours = serializers.IntegerField(source='cancellation_deadline_hours', required=False)

    class Meta:
        model = ReservationSetting
        fields = [
            'id',
            'standard_duration_minutes',
            'standardDurationMinutes',
            'large_party_duration_minutes',
            'largePartyDurationMinutes',
            'min_party_size',
            'minPartySize',
            'max_party_size',
            'maxPartySize',
            'min_advance_minutes',
            'minAdvanceMinutes',
            'max_advance_days',
            'maxAdvanceDays',
            'auto_confirm_max_guests',
            'autoConfirmMaxGuests',
            'cancellation_deadline_hours',
            'cancellationDeadlineHours',
        ]


class ReservationNotificationSerializer(serializers.ModelSerializer):
    notificationTypeDisplay = serializers.CharField(source='get_notification_type_display', read_only=True)
    channelDisplay = serializers.CharField(source='get_channel_display', read_only=True)
    sentAt = serializers.DateTimeField(source='sent_at', read_only=True)

    class Meta:
        model = ReservationNotification
        fields = [
            'id',
            'reservation',
            'recipient',
            'notification_type',
            'notificationTypeDisplay',
            'channel',
            'channelDisplay',
            'title',
            'message',
            'is_sent',
            'sentAt',
        ]


class ReservationSerializer(serializers.ModelSerializer):
    # Old API fields
    referenceCode = serializers.CharField(source='reference_code', read_only=True)
    guestName = serializers.CharField(source='guest_name', required=False)
    guestPhone = serializers.CharField(source='guest_phone', required=False)
    guestEmail = serializers.EmailField(source='guest_email', required=False, allow_blank=True, allow_null=True)
    guestsCount = serializers.IntegerField(source='guests_count', default=2, min_value=1)
    reservationDate = serializers.DateField(source='reservation_date', required=False)
    timeSlot = serializers.CharField(source='time_slot', required=False)
    specialRequests = serializers.CharField(source='special_requests', required=False, allow_blank=True)
    cancellationReason = serializers.CharField(source='cancellation_reason', required=False, allow_blank=True)
    tableDetails = TableSerializer(source='table', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)

    # Modern API fields (aliases & rich dining features)
    reservationNumber = serializers.CharField(source='reference_code', read_only=True)
    customerName = serializers.CharField(source='guest_name', required=False)
    customerPhone = serializers.CharField(source='guest_phone', required=False)
    customerEmail = serializers.EmailField(source='guest_email', required=False, allow_blank=True, allow_null=True)
    partySize = serializers.IntegerField(source='guests_count', required=False)
    reservationTime = serializers.TimeField(source='reservation_time', required=False, allow_null=True)
    durationMinutes = serializers.IntegerField(source='duration_minutes', default=90, required=False)
    endTime = serializers.TimeField(source='end_time', read_only=True)
    diningArea = serializers.PrimaryKeyRelatedField(
        source='dining_area',
        queryset=DiningArea.objects.all(),
        required=False,
        allow_null=True
    )
    diningAreaDetails = DiningAreaSerializer(source='dining_area', read_only=True)
    seatingPreference = serializers.CharField(source='seating_preference', default='NO_PREFERENCE', required=False)
    seatingPreferenceDisplay = serializers.CharField(source='get_seating_preference_display', read_only=True)
    occasionDisplay = serializers.CharField(source='get_occasion_display', read_only=True)
    dietaryNotes = serializers.CharField(source='dietary_notes', required=False, allow_blank=True)
    guestToken = serializers.UUIDField(source='guest_token', read_only=True)

    class Meta:
        model = Reservation
        fields = [
            'id',
            'referenceCode',
            'reservationNumber',
            'table',
            'tableDetails',
            'customer',
            'guestName',
            'customerName',
            'guestPhone',
            'customerPhone',
            'guestEmail',
            'customerEmail',
            'guestsCount',
            'partySize',
            'reservationDate',
            'timeSlot',
            'reservationTime',
            'durationMinutes',
            'endTime',
            'dining_area',
            'diningArea',
            'diningAreaDetails',
            'seating_preference',
            'seatingPreference',
            'seatingPreferenceDisplay',
            'occasion',
            'occasionDisplay',
            'specialRequests',
            'dietary_notes',
            'dietaryNotes',
            'guestToken',
            'status',
            'cancellationReason',
            'createdAt',
            'updatedAt',
            'created_at',
        ]
        read_only_fields = [
            'id',
            'referenceCode',
            'reservationNumber',
            'customer',
            'endTime',
            'guestToken',
            'createdAt',
            'updatedAt',
            'created_at',
        ]

    def to_internal_value(self, data):
        # Support both camelCase and snake_case for seamless client integration
        normalized = dict(data)
        mappings = {
            'guest_name': 'guestName',
            'customer_name': 'guestName',
            'customerName': 'guestName',
            'guest_phone': 'guestPhone',
            'customer_phone': 'guestPhone',
            'customerPhone': 'guestPhone',
            'guest_email': 'guestEmail',
            'customer_email': 'guestEmail',
            'customerEmail': 'guestEmail',
            'guests_count': 'guestsCount',
            'party_size': 'guestsCount',
            'partySize': 'guestsCount',
            'reservation_date': 'reservationDate',
            'time_slot': 'timeSlot',
            'reservation_time': 'timeSlot',
            'reservationTime': 'timeSlot',
            'special_requests': 'specialRequests',
            'cancellation_reason': 'cancellationReason',
            'dietary_notes': 'dietaryNotes',
            'seating_preference': 'seatingPreference',
            'dining_area': 'diningArea',
            'duration_minutes': 'durationMinutes',
        }
        for snake, camel in mappings.items():
            if snake in normalized and camel not in normalized:
                normalized[camel] = normalized[snake]

        return super().to_internal_value(normalized)

    def validate_guest_phone(self, value):
        if value:
            return normalize_phone_number(value)
        return value

    def validate_reservation_date(self, value):
        # Prevent booking past dates
        if value < date.today():
            raise serializers.ValidationError("Reservation date cannot be in the past.")
        return value

    def create(self, validated_data):
        # Smart Auto-Table Assignment if table is not manually selected
        table = validated_data.get('table')
        if not table:
            res_date = validated_data.get('reservation_date')
            slot = validated_data.get('time_slot')
            guests = validated_data.get('guests_count', 2)
            dining_area = validated_data.get('dining_area')

            # Parse start time if slot is provided
            start_time = None
            if slot:
                try:
                    parts = str(slot).strip().split(':')
                    if len(parts) >= 2:
                        start_time = time(int(parts[0]), int(parts[1]))
                except Exception:
                    pass

            duration = validated_data.get('duration_minutes', 90)

            # 1. Try slot-aware table lookup first
            if start_time:
                available = get_available_tables(
                    res_date=res_date,
                    start_time=start_time,
                    duration_minutes=duration,
                    party_size=guests,
                    dining_area_id=dining_area.id if dining_area else None
                )
                if available:
                    validated_data['table'] = available[0]

            # 2. Fallback to basic capacity & exclusion check for backward compatibility
            if not validated_data.get('table'):
                busy_table_ids = Reservation.objects.filter(
                    reservation_date=res_date,
                    time_slot=slot,
                    status__in=[Reservation.Status.CONFIRMED, Reservation.Status.SEATED, 'confirmed', 'seated']
                ).values_list('table_id', flat=True)

                query = Table.objects.filter(
                    is_active=True,
                    capacity__gte=guests
                ).exclude(
                    id__in=busy_table_ids
                )
                if dining_area:
                    query = query.filter(dining_area=dining_area)

                optimal_table = query.order_by('capacity').first()
                if optimal_table:
                    validated_data['table'] = optimal_table

        instance = super().create(validated_data)

        # Send confirmation notification
        try:
            send_reservation_notification(
                instance,
                ReservationNotification.NotificationType.CONFIRMATION
            )
        except Exception:
            pass

        return instance
