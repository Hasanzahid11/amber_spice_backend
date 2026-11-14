from decimal import Decimal
from django.db.models import F
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import CanManageInventory, IsRestaurantStaff
from .models import InventoryCategory, InventoryItem
from .serializers import InventoryCategorySerializer, InventoryItemSerializer


class InventoryCategoryViewSet(viewsets.ModelViewSet):
    queryset = InventoryCategory.objects.all()
    serializer_class = InventoryCategorySerializer
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsRestaurantStaff()]
        return [CanManageInventory()]


class InventoryItemViewSet(viewsets.ModelViewSet):
    queryset = InventoryItem.objects.all()
    serializer_class = InventoryItemSerializer
    filterset_fields = ['category']
    search_fields = ['name', 'supplier', 'category']
    ordering_fields = ['name', 'current_stock', 'minimum_stock', 'category', 'last_restocked']
    ordering = ['name']

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'low_stock']:
            return [IsRestaurantStaff()]
        return [CanManageInventory()]

    @action(detail=False, methods=['get'])
    def low_stock(self, request):
        low_items = self.get_queryset().filter(current_stock__lte=F('minimum_stock'))
        serializer = self.get_serializer(low_items, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def restock(self, request, pk=None):
        item = self.get_object()
        raw_amount = request.data.get('amount') or request.data.get('addAmount') or request.data.get('add_amount')
        if raw_amount is None:
            return Response({'detail': 'Enter the amount to add to current stock.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            amount = Decimal(str(raw_amount))
            if amount <= Decimal('0'):
                return Response({'detail': 'Restock amount must be greater than zero.'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response({'detail': 'Invalid restock amount.'}, status=status.HTTP_400_BAD_REQUEST)

        item.current_stock += amount
        item.save()
        return Response(self.get_serializer(item).data)
