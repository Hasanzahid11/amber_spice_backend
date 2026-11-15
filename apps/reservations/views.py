from datetime import date, time
from django.db.models import Q
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import CanManageReservations, IsRestaurantStaff
from .models import (
    DiningArea,
    Table,
    RestaurantTable,
    ReservationSchedule,
    ReservationSetting,
    Reservation,
    ReservationNotification,
)
from .serializers import (
    DiningAreaSerializer,
    TableSerializer,
    ReservationScheduleSerializer,
    ReservationSettingSerializer,
    ReservationNotificationSerializer,
    ReservationSerializer,
)
from .services import (
    get_guest_token,
    get_available_tables,
    send_reservation_notification,
)

STANDARD_TIME_SLOTS = [
    '12:00', '12:30', '13:00', '13:30', '14:00', '14:30',
    '17:00', '17:30', '18:00', '18:30', '19:00', '19:30', '20:00', '20:30', '21:00', '21:30'
]


class DiningAreaViewSet(viewsets.ModelViewSet):
    """
    Dining Areas & Dining Rooms API:
    - Lists restaurant sections (Main Dining Room, Conservatory / Terrace, Private Dining).
    - Staff management for dining zones and layout arrangements.
    """
    queryset = DiningArea.objects.all()
    serializer_class = DiningAreaSerializer
    filterset_fields = ['is_active']
    search_fields = ['name', 'description']

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        return [CanManageReservations()]


class TableViewSet(viewsets.ModelViewSet):
    """
    Table & Floor Plan Management API:
    - View all tables, capacities, shapes, floor zones, and live status.
    - Seat guests or release tables with 1-click staff actions.
    """
    queryset = Table.objects.filter(is_active=True).select_related('dining_area')
    serializer_class = TableSerializer
    filterset_fields = ['status', 'capacity', 'section', 'dining_area', 'shape']
    search_fields = ['number', 'guest_name', 'current_order']

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        return [CanManageReservations()]

    @action(detail=True, methods=['post'], permission_classes=[CanManageReservations])
    def seat(self, request, pk=None):
        """
        POST /api/v1/reservations/tables/<id>/seat/
        Seats a party at this table, marking it occupied.
        """
        table = self.get_object()
        guest_name = request.data.get('guest_name') or request.data.get('guestName') or 'Walk-in Guest'
        current_order = request.data.get('current_order') or request.data.get('currentOrder') or ''
        time_slot = request.data.get('time_slot') or request.data.get('timeSlot') or ''

        table.seat_party(guest_name=guest_name, current_order=current_order, time_slot=time_slot)
        return Response({
            'message': f"Table {table.number} is now seated for {guest_name}.",
            'table': TableSerializer(table).data
        })

    @action(detail=True, methods=['post'], permission_classes=[CanManageReservations])
    def release(self, request, pk=None):
        """
        POST /api/v1/reservations/tables/<id>/release/
        Clears table back to available status.
        """
        table = self.get_object()
        table.release()
        return Response({
            'message': f"Table {table.number} released and is now available.",
            'table': TableSerializer(table).data
        })


class ReservationScheduleViewSet(viewsets.ModelViewSet):
    """
    Weekly Service Hours & Shifts API (Lunch & Dinner shifts per day).
    """
    queryset = ReservationSchedule.objects.all()
    serializer_class = ReservationScheduleSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        return [CanManageReservations()]


class ReservationSettingViewSet(viewsets.ViewSet):
    """
    Global Reservation Settings API:
    - GET /api/v1/reservations/settings/
    - PATCH /api/v1/reservations/settings/
    """
    def get_permissions(self):
        if self.action == 'list':
            return [permissions.AllowAny()]
        return [CanManageReservations()]

    def list(self, request):
        settings_obj = ReservationSetting.get_settings()
        return Response(ReservationSettingSerializer(settings_obj).data)

    def partial_update(self, request, pk=None):
        settings_obj = ReservationSetting.get_settings()
        serializer = ReservationSettingSerializer(settings_obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class ReservationViewSet(viewsets.ModelViewSet):
    """
    Table Reservation API:
    - Public booking with smart auto-table assignment and Irish phone support.
    - Slot availability calculation for date and party size.
    - Customer history and self-service cancellation.
    - Front-of-House lifecycle: confirm, seat, complete, no-show.
    - Notification history tracking.
    """
    queryset = Reservation.objects.select_related('table', 'customer', 'dining_area').all()
    serializer_class = ReservationSerializer
    filterset_fields = ['status', 'reservation_date', 'table', 'time_slot', 'dining_area']
    search_fields = ['guest_name', 'guest_phone', 'guest_email', 'reference_code']

    def get_permissions(self):
        if self.action in ['create', 'lookup', 'available_slots', 'cancel']:
            return [permissions.AllowAny()]
        if self.action in ['confirm', 'seat', 'complete', 'no_show', 'assign_table', 'notifications']:
            return [IsRestaurantStaff()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Reservation.objects.none()

        # Restaurant Staff, Manager, and Owner/Admin can view all reservations
        if getattr(user, 'is_restaurant_staff', False) or getattr(user, 'is_owner_or_admin', False) or user.is_staff:
            return super().get_queryset()

        # Customers see only their own bookings
        return super().get_queryset().filter(customer=user)

    def perform_create(self, serializer):
        customer = self.request.user if self.request.user.is_authenticated else None
        guest_token = get_guest_token(self.request) if not customer else None
        serializer.save(customer=customer, guest_token=guest_token)

    @action(detail=False, methods=['get'], permission_classes=[permissions.AllowAny], url_path='available-slots')
    def available_slots(self, request):
        """
        GET /api/v1/reservations/available-slots/?date=YYYY-MM-DD&guests=2&dining_area=<id>
        Calculates available time slots based on active tables, schedule shifts, and reservations.
        """
        date_str = request.query_params.get('date')
        guests = int(request.query_params.get('guests') or request.query_params.get('party_size') or 2)
        dining_area_id = request.query_params.get('dining_area') or request.query_params.get('diningArea')

        target_date = date.fromisoformat(date_str) if date_str else date.today()

        # Eligible tables with capacity >= guests
        eligible_tables_qs = Table.objects.filter(is_active=True, capacity__gte=guests)
        if dining_area_id:
            eligible_tables_qs = eligible_tables_qs.filter(dining_area_id=dining_area_id)
        eligible_tables = list(eligible_tables_qs)
        total_eligible = len(eligible_tables)

        # Existing active reservations for the date
        busy_reservations = Reservation.objects.filter(
            reservation_date=target_date,
            status__in=[Reservation.Status.CONFIRMED, Reservation.Status.SEATED, 'confirmed', 'seated']
        ).values('time_slot', 'table_id')

        # Map occupied table counts per slot
        booked_by_slot = {}
        for r in busy_reservations:
            slot = r['time_slot']
            if slot:
                booked_by_slot.setdefault(slot, set()).add(r['table_id'])

        slot_results = []
        for slot in STANDARD_TIME_SLOTS:
            booked_table_ids = booked_by_slot.get(slot, set())
            free_tables = [t for t in eligible_tables if t.id not in booked_table_ids]
            is_available = len(free_tables) > 0

            try:
                parts = slot.split(':')
                slot_time = time(int(parts[0]), int(parts[1]))
            except Exception:
                slot_time = time(12, 0)

            slot_results.append({
                'timeSlot': slot,
                'time': slot,
                'isAvailable': is_available,
                'is_available': is_available,
                'availableTablesCount': len(free_tables),
                'available_tables_count': len(free_tables),
                'suggestedTable': free_tables[0].number if free_tables else None,
                'service': 'Lunch' if slot_time < time(16, 0) else 'Dinner',
            })

        return Response({
            'date': target_date.isoformat(),
            'guestsCount': guests,
            'party_size': guests,
            'totalEligibleTables': total_eligible,
            'slots': slot_results,
        })

    @action(detail=False, methods=['get'], permission_classes=[permissions.AllowAny])
    def lookup(self, request):
        """
        GET /api/v1/reservations/lookup/?reference=RES-20261114-XYZ&phone=+353871234567
        Customer self-service reservation tracking by reference code or phone.
        """
        ref = (
            request.query_params.get('reference')
            or request.query_params.get('reference_code')
            or request.query_params.get('reservation_number')
        )
        phone = request.query_params.get('phone') or request.query_params.get('guest_phone')

        if not ref and not phone:
            return Response(
                {'error': 'Provide either "reference" or "phone" to lookup reservation.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        query = Reservation.objects.all()
        if ref:
            query = query.filter(reference_code__iexact=ref.strip())
        if phone:
            query = query.filter(guest_phone__icontains=phone.strip()[-7:])

        res = query.order_by('-reservation_date').first()
        if not res:
            return Response(
                {'error': 'Reservation not found. Please check reference code or phone number.'},
                status=status.HTTP_404_NOT_FOUND
            )

        return Response(ReservationSerializer(res).data)

    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated], url_path='my-reservations')
    def my_reservations(self, request):
        """
        GET /api/v1/reservations/my-reservations/
        Retrieves all past and upcoming reservations for the authenticated customer.
        """
        reservations = Reservation.objects.filter(customer=request.user).order_by('-reservation_date', '-time_slot')
        serializer = ReservationSerializer(reservations, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[permissions.AllowAny])
    def cancel(self, request, pk=None):
        """
        POST /api/v1/reservations/<id>/cancel/
        Cancels a reservation. If unauthenticated, validates reference code or phone.
        """
        reservation = self.get_object()
        user = request.user

        # Security check for guest callers
        if not (user.is_authenticated and (getattr(user, 'is_restaurant_staff', False) or user.is_staff or reservation.customer == user)):
            ref = (
                request.data.get('reference')
                or request.data.get('reference_code')
                or request.data.get('reservation_number')
                or request.query_params.get('reference')
            )
            phone = request.data.get('phone') or request.query_params.get('phone')
            if not ref and not phone:
                return Response(
                    {'error': 'Reference code or phone is required to cancel this reservation.'},
                    status=status.HTTP_403_FORBIDDEN
                )
            if ref and reservation.reference_code.lower() != ref.strip().lower():
                return Response({'error': 'Invalid reservation reference.'}, status=status.HTTP_403_FORBIDDEN)

        reason = request.data.get('reason', 'Customer requested cancellation')
        reservation.mark_cancelled(reason=reason)

        # If table was occupied/reserved for this party, release it
        if reservation.table and reservation.table.guest_name == reservation.guest_name:
            reservation.table.release()

        # Dispatch cancellation notification
        try:
            send_reservation_notification(
                reservation,
                ReservationNotification.NotificationType.CANCELLATION
            )
        except Exception:
            pass

        return Response({
            'message': f"Reservation #{reservation.reference_code} has been cancelled.",
            'reservation': ReservationSerializer(reservation).data
        })

    @action(detail=True, methods=['post'], permission_classes=[IsRestaurantStaff])
    def confirm(self, request, pk=None):
        """POST /api/v1/reservations/<id>/confirm/"""
        reservation = self.get_object()
        reservation.mark_confirmed()
        return Response({
            'message': f"Reservation #{reservation.reference_code} confirmed.",
            'reservation': ReservationSerializer(reservation).data
        })

    @action(detail=True, methods=['post'], permission_classes=[IsRestaurantStaff])
    def seat(self, request, pk=None):
        """
        POST /api/v1/reservations/<id>/seat/
        Marks reservation as SEATED and sets assigned table to OCCUPIED.
        """
        reservation = self.get_object()
        reservation.mark_seated()

        if reservation.table:
            reservation.table.seat_party(
                guest_name=reservation.guest_name,
                time_slot=reservation.time_slot
            )

        return Response({
            'message': f"Guest {reservation.guest_name} seated at Table {reservation.table.number if reservation.table else 'Unassigned'}.",
            'reservation': ReservationSerializer(reservation).data
        })

    @action(detail=True, methods=['post'], permission_classes=[IsRestaurantStaff])
    def complete(self, request, pk=None):
        """
        POST /api/v1/reservations/<id>/complete/
        Completes dining and releases the table.
        """
        reservation = self.get_object()
        reservation.mark_completed()

        if reservation.table:
            reservation.table.release()

        return Response({
            'message': f"Reservation #{reservation.reference_code} completed. Table released.",
            'reservation': ReservationSerializer(reservation).data
        })

    @action(detail=True, methods=['post'], permission_classes=[IsRestaurantStaff], url_path='no-show')
    def no_show(self, request, pk=None):
        """POST /api/v1/reservations/<id>/no-show/"""
        reservation = self.get_object()
        reservation.mark_no_show()

        if reservation.table and reservation.table.guest_name == reservation.guest_name:
            reservation.table.release()

        return Response({
            'message': f"Reservation #{reservation.reference_code} marked as no-show.",
            'reservation': ReservationSerializer(reservation).data
        })

    @action(detail=True, methods=['post'], permission_classes=[IsRestaurantStaff], url_path='assign-table')
    def assign_table(self, request, pk=None):
        """
        POST /api/v1/reservations/<id>/assign-table/
        Assigns or transfers a reservation to another table.
        """
        reservation = self.get_object()
        table_id = request.data.get('table_id') or request.data.get('tableId')
        table = Table.objects.filter(id=table_id, is_active=True).first()

        if not table:
            return Response({'error': 'Valid active table_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        reservation.table = table
        reservation.save(update_fields=['table', 'updated_at'])

        return Response({
            'message': f"Reservation #{reservation.reference_code} assigned to Table {table.number}.",
            'reservation': ReservationSerializer(reservation).data
        })

    @action(detail=True, methods=['get'], permission_classes=[IsRestaurantStaff])
    def notifications(self, request, pk=None):
        """
        GET /api/v1/reservations/<id>/notifications/
        Logs and history of notifications sent for this booking.
        """
        reservation = self.get_object()
        logs = reservation.notifications.all()
        return Response(ReservationNotificationSerializer(logs, many=True).data)
