from django.db.models import F
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import CanManageInventory, IsRestaurantStaff
from .models import InventoryItem
from .serializers import InventoryItemSerializer


class InventoryItemViewSet(viewsets.ModelViewSet):
    queryset = InventoryItem.objects.all()
    serializer_class = InventoryItemSerializer
    filterset_fields = ['category']
    search_fields = ['name', 'supplier']

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'low_stock']:
            return [IsRestaurantStaff()]
        return [CanManageInventory()]

    @action(detail=False, methods=['get'])
    def low_stock(self, request):
        low_items = self.get_queryset().filter(current_stock__lte=F('minimum_stock'))
        serializer = self.get_serializer(low_items, many=True)
        return Response(serializer.data)
