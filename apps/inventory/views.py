from datetime import date, timedelta
from decimal import Decimal
from django.db.models import F, Q
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import CanManageInventory, IsRestaurantStaff
from apps.orders.models import Order
from .models import (
    InventoryItem,
    Recipe,
    RecipeIngredient,
    StockMovement,
    Supplier,
)
from .serializers import (
    AdjustActionSerializer,
    CalculateConsumptionInputSerializer,
    InventoryItemSerializer,
    RecipeSerializer,
    RestockActionSerializer,
    StockMovementSerializer,
    SupplierSerializer,
    WasteActionSerializer,
)
from .services import (
    adjust_stock,
    calculate_order_consumption,
    deduct_order_inventory,
    record_waste,
    restock_inventory_item,
)


class SupplierViewSet(viewsets.ModelViewSet):
    """
    Suppliers & Vendors API:
    - Manage external suppliers for meat, produce, packaging, spices, and beverages.
    """
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    filterset_fields = ['is_active']
    search_fields = ['name', 'contact_name', 'email', 'phone']

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsRestaurantStaff()]
        return [CanManageInventory()]


class InventoryItemViewSet(viewsets.ModelViewSet):
    """
    Restaurant Stock & Inventory API:
    - Real-time stock levels for Chicken, Beef, Rice, Flour, Oil, Vegetables, Sauces, Spices, Drinks, Packaging.
    - Low stock alerts and reorder level thresholds.
    - Expiry tracking and batch/lot logging.
    - Restock, adjust, and waste operations.
    """
    queryset = InventoryItem.objects.select_related('supplier_ref').all()
    serializer_class = InventoryItemSerializer
    filterset_fields = ['category', 'is_active', 'unit', 'storage_location']
    search_fields = ['name', 'supplier', 'batch_number', 'storage_location']
    ordering_fields = ['name', 'current_stock', 'purchase_price', 'expiry_date', 'last_restocked']

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'low_stock', 'reorder_alerts', 'expiring_soon', 'movements']:
            return [IsRestaurantStaff()]
        return [CanManageInventory()]

    @action(detail=False, methods=['get'])
    def low_stock(self, request):
        """
        GET /api/v1/inventory/items/low_stock/ (and /api/v1/inventory/items/low-stock/)
        Returns items where current stock is at or below minimum stock level.
        Preserves 100% backward compatibility with existing tests and API callers.
        """
        low_items = self.get_queryset().filter(current_stock__lte=F('minimum_stock'))
        serializer = self.get_serializer(low_items, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='reorder-alerts')
    def reorder_alerts(self, request):
        """
        GET /api/v1/inventory/items/reorder-alerts/
        Returns items that have reached or breached their reorder threshold level.
        """
        items = [item for item in self.get_queryset().filter(is_active=True) if item.reorder_needed]
        serializer = self.get_serializer(items, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='expiring-soon')
    def expiring_soon(self, request):
        """
        GET /api/v1/inventory/items/expiring-soon/?days=7
        Lists items expiring within the specified number of days (default 7 days).
        """
        days = int(request.query_params.get('days', 7))
        cutoff = date.today() + timedelta(days=days)
        expiring_items = self.get_queryset().filter(
            is_active=True,
            expiry_date__isnull=False,
            expiry_date__lte=cutoff
        ).order_by('expiry_date')
        serializer = self.get_serializer(expiring_items, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[CanManageInventory])
    def restock(self, request, pk=None):
        """
        POST /api/v1/inventory/items/<id>/restock/
        Adds inventory quantity from supplier delivery and records the movement.
        """
        item = self.get_object()
        serializer = RestockActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        v = serializer.validated_data

        movement = restock_inventory_item(
            item=item,
            quantity=v['quantity'],
            purchase_price=v.get('purchase_price'),
            supplier=v.get('supplier'),
            batch_number=v.get('batch_number'),
            expiry_date=v.get('expiry_date'),
            performed_by=request.user if request.user.is_authenticated else None,
            notes=v.get('notes', '')
        )
        return Response({
            'message': f"Successfully restocked {v['quantity']} {item.unit} of {item.name}.",
            'movement': StockMovementSerializer(movement).data,
            'item': InventoryItemSerializer(item).data,
        })

    @action(detail=True, methods=['post'], permission_classes=[CanManageInventory])
    def adjust(self, request, pk=None):
        """
        POST /api/v1/inventory/items/<id>/adjust/
        Reconciles stock to an exact physical count audit.
        """
        item = self.get_object()
        serializer = AdjustActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        v = serializer.validated_data

        movement = adjust_stock(
            item=item,
            new_stock=v['new_stock'],
            reason=v.get('reason', ''),
            performed_by=request.user if request.user.is_authenticated else None
        )
        return Response({
            'message': f"Adjusted stock for {item.name} to {v['new_stock']} {item.unit}.",
            'movement': StockMovementSerializer(movement).data,
            'item': InventoryItemSerializer(item).data,
        })

    @action(detail=True, methods=['post'], permission_classes=[CanManageInventory])
    def waste(self, request, pk=None):
        """
        POST /api/v1/inventory/items/<id>/waste/
        Deducts damaged, expired, or spoiled kitchen stock and logs waste tracking.
        """
        item = self.get_object()
        serializer = WasteActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        v = serializer.validated_data

        movement = record_waste(
            item=item,
            quantity=v['quantity'],
            reason=v.get('reason', ''),
            performed_by=request.user if request.user.is_authenticated else None
        )
        return Response({
            'message': f"Logged waste of {v['quantity']} {item.unit} for {item.name}.",
            'movement': StockMovementSerializer(movement).data,
            'item': InventoryItemSerializer(item).data,
        })

    @action(detail=True, methods=['get'])
    def movements(self, request, pk=None):
        """
        GET /api/v1/inventory/items/<id>/movements/
        Audit log of all stock movements for this inventory item.
        """
        item = self.get_object()
        logs = item.movements.all()
        return Response(StockMovementSerializer(logs, many=True).data)


class RecipeViewSet(viewsets.ModelViewSet):
    """
    Recipe / Bill of Materials (BOM) API:
    - Connects menu Dishes to raw Inventory Items (e.g. 200g chicken, 100g rice, 20g sauce).
    - Calculates food cost per portion, overall food cost percentage, and gross margins.
    - Simulates ingredient consumption for multi-portion batches.
    """
    queryset = Recipe.objects.select_related('dish').prefetch_related('ingredients__inventory_item').all()
    serializer_class = RecipeSerializer
    filterset_fields = ['dish', 'is_active']
    search_fields = ['name', 'dish__name']

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'simulate']:
            return [IsRestaurantStaff()]
        return [CanManageInventory()]

    @action(detail=True, methods=['post'])
    def simulate(self, request, pk=None):
        """
        POST /api/v1/inventory/recipes/<id>/simulate/
        Simulates ingredient consumption, cost, and stock impact for N portions:
        {"portions": 10}
        """
        recipe = self.get_object()
        portions = int(request.data.get('portions') or request.data.get('quantity') or 1)

        result = calculate_order_consumption([{
            'dish': recipe.dish,
            'quantity': portions
        }])
        return Response({
            'recipe_id': recipe.id,
            'recipe_name': recipe.name,
            'dish_name': recipe.dish.name,
            'portions': portions,
            'total_cost': result['total_food_cost'],
            'can_fulfill': result['can_fulfill'],
            'consumed_ingredients': result['consumed_ingredients'],
            'insufficient_items': result['insufficient_items'],
        })


class StockMovementViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Inventory Stock Movement & Transaction History API:
    - Read-only historical log of purchases, sales consumption, waste, and adjustments.
    """
    queryset = StockMovement.objects.select_related('inventory_item', 'order', 'performed_by').all()
    serializer_class = StockMovementSerializer
    filterset_fields = ['movement_type', 'inventory_item', 'order']
    search_fields = ['reference', 'inventory_item__name', 'notes']
    permission_classes = [IsRestaurantStaff]


class CalculateConsumptionView(APIView):
    """
    POST /api/v1/inventory/calculate-consumption/
    Calculates recipe-based ingredient consumption for an order or prospective batch:
    Payload:
    {
        "items": [
            {"dish_id": 1, "quantity": 10},
            {"dish_id": 2, "quantity": 5}
        ]
    }
    Returns:
    - Breakdown of all ingredients used (in item units, e.g. 200g x 10 = 2.0 kg)
    - Total food cost
    - Projected remaining stock
    - Any shortage warnings
    """
    permission_classes = [IsRestaurantStaff]

    def post(self, request):
        serializer = CalculateConsumptionInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        items = serializer.validated_data['items']

        result = calculate_order_consumption(items)
        return Response(result)


class DeductOrderInventoryView(APIView):
    """
    POST /api/v1/inventory/deduct-order/
    Executes recipe-based inventory deductions for an existing order.
    Payload:
    {"order_id": 12} or {"order_number": "ORD-20261114-XYZ"}
    """
    permission_classes = [IsRestaurantStaff]

    def post(self, request):
        order_id = request.data.get('order_id') or request.data.get('orderId')
        order_number = request.data.get('order_number') or request.data.get('orderNumber')

        if not order_id and not order_number:
            return Response(
                {'error': 'Provide order_id or order_number to deduct inventory.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        order_qs = Order.objects.prefetch_related('items__dish').all()
        if order_id:
            order = order_qs.filter(id=order_id).first()
        else:
            order = order_qs.filter(order_number__iexact=order_number.strip()).first()

        if not order:
            return Response({'error': 'Order not found.'}, status=status.HTTP_404_NOT_FOUND)

        movements = deduct_order_inventory(
            order=order,
            performed_by=request.user if request.user.is_authenticated else None
        )

        return Response({
            'message': f"Deducted inventory for order {order.order_number}.",
            'order_number': order.order_number,
            'movements_count': len(movements),
            'movements': StockMovementSerializer(movements, many=True).data
        })
