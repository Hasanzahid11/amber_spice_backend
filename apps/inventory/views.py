from decimal import Decimal
from django.db.models import F
from django.db import transaction
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, mixins
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import CanManageInventory, IsRestaurantStaff
from .models import InventoryCategory, InventoryItem, StockAlert, WastageRecord
from .serializers import InventoryCategorySerializer, InventoryItemSerializer, StockAlertSerializer, WastageSerializer
from apps.accounts.permissions import HasRestaurantPermission


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

    @extend_schema(request=inline_serializer('RestockRequest', fields={'amount': serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0.01'))}))
    @action(detail=True, methods=['post'])
    @transaction.atomic
    def restock(self, request, pk=None):
        item = self.get_queryset().select_for_update().get(pk=self.get_object().pk)
        raw_amount = request.data.get('amount') or request.data.get('addAmount') or request.data.get('add_amount')
        if raw_amount is None:
            return Response({'detail': 'Enter the amount to add to current stock.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            amount = Decimal(str(raw_amount))
            if not amount.is_finite() or amount <= Decimal('0') or amount.as_tuple().exponent < -2 or amount + item.current_stock > Decimal('99999999.99'):
                return Response({'detail': 'Restock amount must be greater than zero.'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response({'detail': 'Invalid restock amount.'}, status=status.HTTP_400_BAD_REQUEST)

        item.current_stock += amount
        item.save()
        return Response(self.get_serializer(item).data)


class StockAlertViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    queryset = StockAlert.objects.select_related('item', 'reported_by').all()
    serializer_class = StockAlertSerializer
    filterset_fields = ['resolved']

    def get_permissions(self):
        return [IsRestaurantStaff()] if self.action in ['list', 'create'] else [CanManageInventory()]

    def perform_create(self, serializer):
        serializer.save(reported_by=self.request.user, resolved=False)


class WastageViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    queryset = WastageRecord.objects.select_related('item').all()
    serializer_class = WastageSerializer
    permission_classes = [CanManageInventory]

    @transaction.atomic
    def perform_create(self, serializer):
        item = InventoryItem.objects.select_for_update().get(pk=serializer.validated_data['item'].pk)
        quantity = serializer.validated_data['quantity']
        if quantity > item.current_stock:
            raise serializers.ValidationError({'quantity': 'Wastage exceeds current stock.'})
        item.current_stock -= quantity
        item.save(update_fields=['current_stock', 'last_restocked'])
        serializer.save(reported_by=self.request.user)
