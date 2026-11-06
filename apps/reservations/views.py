from rest_framework import permissions, viewsets
from apps.accounts.permissions import CanManageReservations, IsRestaurantStaff
from .models import Reservation, Table
from .serializers import ReservationSerializer, TableSerializer


class TableViewSet(viewsets.ModelViewSet):
    queryset = Table.objects.all()
    serializer_class = TableSerializer
    filterset_fields = ['status', 'capacity']
    search_fields = ['number', 'guest_name', 'current_order']

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        return [CanManageReservations()]


class ReservationViewSet(viewsets.ModelViewSet):
    queryset = Reservation.objects.select_related('table', 'customer').all()
    serializer_class = ReservationSerializer
    filterset_fields = ['status', 'reservation_date', 'table']
    search_fields = ['guest_name', 'guest_phone', 'guest_email']

    def get_permissions(self):
        if self.action in ['create']:
            return [permissions.AllowAny()]
        return [IsRestaurantStaff()]

    def perform_create(self, serializer):
        customer = self.request.user if self.request.user.is_authenticated else None
        serializer.save(customer=customer)
