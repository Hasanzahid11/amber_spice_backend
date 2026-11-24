from decimal import Decimal
from django.db.models import F, Sum
from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, mixins
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import CanManageInventory, IsRestaurantStaff, HasRestaurantPermission
from apps.menu.models import Dish
from .models import InventoryCategory, InventoryItem, StockAlert, WastageRecord, DishRecipe, StockTransaction
from .serializers import (
    InventoryCategorySerializer,
    InventoryItemSerializer,
    StockAlertSerializer,
    WastageSerializer,
    DishRecipeSerializer,
    DishCostSummarySerializer,
    StockTransactionSerializer,
    ManualStockAdjustmentSerializer,
)
from .services import calculate_dish_cost_data


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

        # Audit stock transaction
        unit_cost = item.cost_per_unit or Decimal('0.0000')
        StockTransaction.objects.create(
            item=item,
            transaction_type=StockTransaction.TransactionType.PURCHASE,
            quantity_delta=amount,
            unit_cost=unit_cost,
            total_cost=(amount * unit_cost).quantize(Decimal('0.01')),
            balance_after=item.current_stock,
            created_by=request.user if request.user.is_authenticated else None,
            notes='Restocked via admin inventory',
        )

        return Response(self.get_serializer(item).data)


class StockAlertViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    queryset = StockAlert.objects.select_related('item', 'reported_by').all()
    serializer_class = StockAlertSerializer
    filterset_fields = ['resolved']

    def get_permissions(self):
        return [IsRestaurantStaff()] if self.action in ['list', 'create'] else [CanManageInventory()]

    def perform_create(self, serializer):
        alert = serializer.save(reported_by=self.request.user, resolved=False)
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            from apps.notifications.models import Notification
            channel_layer = get_channel_layer()
            if channel_layer:
                alert_payload = {
                    'id': str(alert.id),
                    'ingredientName': alert.item.name if alert.item else 'Ingredient',
                    'stockRemainingPercent': alert.stock_remaining_percent,
                    'note': alert.note,
                    'reporterName': alert.reported_by.username if alert.reported_by else 'Chef',
                    'createdAt': alert.created_at.isoformat(),
                }
                notif = Notification.objects.create(
                    type=Notification.NotificationType.STOCK_ALERT,
                    target_role='admin',
                    title=f"Low Stock: {alert_payload['ingredientName']}",
                    message=f"{alert_payload['ingredientName']} is at {alert.stock_remaining_percent}% stock. Note: {alert.note}",
                    data=alert_payload,
                )
                async_to_sync(channel_layer.group_send)(
                    'admin_operations',
                    {
                        'type': 'stock.alert',
                        'alert': alert_payload,
                        'notification': {
                            'id': notif.id,
                            'type': notif.type,
                            'title': notif.title,
                            'message': notif.message,
                            'createdAt': notif.created_at.isoformat(),
                        },
                    }
                )
        except Exception:
            pass


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
        wastage = serializer.save(reported_by=self.request.user)

        # Audit stock transaction
        unit_cost = item.cost_per_unit or Decimal('0.0000')
        StockTransaction.objects.create(
            item=item,
            transaction_type=StockTransaction.TransactionType.WASTAGE,
            quantity_delta=-quantity,
            unit_cost=unit_cost,
            total_cost=(quantity * unit_cost).quantize(Decimal('0.01')),
            balance_after=item.current_stock,
            created_by=self.request.user if self.request.user.is_authenticated else None,
            notes=f"Wastage: {serializer.validated_data.get('reason', '')}",
        )


class DishRecipeViewSet(viewsets.ModelViewSet):
    queryset = DishRecipe.objects.select_related('dish', 'ingredient', 'dish__category').all()
    serializer_class = DishRecipeSerializer
    filterset_fields = ['dish', 'ingredient']
    search_fields = ['dish__name', 'ingredient__name']
    ordering_fields = ['dish__name', 'created_at']
    ordering = ['dish__name', 'ingredient__name']

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'cost_summary']:
            return [IsRestaurantStaff()]
        return [CanManageInventory()]

    @action(detail=False, methods=['get'], url_path='cost-summary')
    def cost_summary(self, request):
        dish_id = request.query_params.get('dish') or request.query_params.get('dish_id')
        dishes_qs = Dish.objects.select_related('category').prefetch_related('recipe_items__ingredient').all()
        if dish_id:
            dishes_qs = dishes_qs.filter(pk=dish_id)

        summaries = []
        for dish in dishes_qs:
            data = calculate_dish_cost_data(dish)
            summaries.append({
                'dishId': dish.id,
                'dishName': dish.name,
                'dishCategory': dish.category.name if dish.category else '',
                'dishPrice': dish.price,
                'isAvailable': dish.is_available,
                'recipeItems': DishRecipeSerializer(data['recipe_items'], many=True).data,
                'totalFoodCost': data['total_food_cost'],
                'foodCostPercent': data['food_cost_percent'],
                'grossProfit': data['gross_profit'],
                'grossMarginPercent': data['gross_margin_percent'],
                'maxPortionsAvailable': data['max_portions_available'],
            })
        return Response(summaries)


class StockTransactionViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = StockTransaction.objects.select_related('item', 'order', 'created_by').all()
    serializer_class = StockTransactionSerializer
    filterset_fields = ['item', 'transaction_type', 'order']
    search_fields = ['item__name', 'order__order_number', 'notes']
    ordering_fields = ['created_at', 'quantity_delta', 'total_cost']
    ordering = ['-created_at']

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'summary']:
            return [IsRestaurantStaff()]
        return [CanManageInventory()]

    @action(detail=False, methods=['post'], url_path='adjust')
    @transaction.atomic
    def adjust(self, request):
        serializer = ManualStockAdjustmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = serializer.validated_data['item']
        item = InventoryItem.objects.select_for_update().get(pk=item.pk)
        ttype = serializer.validated_data['transactionType']
        delta = serializer.validated_data['quantityDelta']
        custom_unit_cost = serializer.validated_data.get('unitCost')
        unit_cost = custom_unit_cost if custom_unit_cost is not None else (item.cost_per_unit or Decimal('0.0000'))
        notes = serializer.validated_data.get('notes', '')

        new_stock = max(Decimal('0.00'), item.current_stock + delta)
        item.current_stock = new_stock
        if custom_unit_cost is not None and custom_unit_cost > Decimal('0'):
            item.cost_per_unit = custom_unit_cost
        item.save(update_fields=['current_stock', 'cost_per_unit', 'last_restocked'])

        tx = StockTransaction.objects.create(
            item=item,
            transaction_type=ttype,
            quantity_delta=delta,
            unit_cost=unit_cost,
            total_cost=(abs(delta) * unit_cost).quantize(Decimal('0.01')),
            balance_after=new_stock,
            created_by=request.user if request.user.is_authenticated else None,
            notes=notes or f"Manual adjustment ({ttype})",
        )
        return Response(StockTransactionSerializer(tx).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        total_valuation = sum(
            (item.current_stock * (item.cost_per_unit or Decimal('0.0000')))
            for item in InventoryItem.objects.all()
        ).quantize(Decimal('0.01'))

        now = timezone.now()
        thirty_days_ago = now - timezone.timedelta(days=30)
        
        consumption_30d = StockTransaction.objects.filter(
            transaction_type=StockTransaction.TransactionType.CONSUMPTION,
            created_at__gte=thirty_days_ago
        ).aggregate(total=Sum('total_cost'))['total'] or Decimal('0.00')

        wastage_30d = StockTransaction.objects.filter(
            transaction_type=StockTransaction.TransactionType.WASTAGE,
            created_at__gte=thirty_days_ago
        ).aggregate(total=Sum('total_cost'))['total'] or Decimal('0.00')

        return Response({
            'totalInventoryValuation': total_valuation,
            'totalConsumption30Days': consumption_30d,
            'totalWastage30Days': wastage_30d,
            'totalItemsCount': InventoryItem.objects.count(),
            'lowStockCount': InventoryItem.objects.filter(current_stock__lte=F('minimum_stock')).count(),
        })

