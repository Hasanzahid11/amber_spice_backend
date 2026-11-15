from decimal import Decimal
from django.db.models import F, Q
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsManagerOrAdmin
from apps.inventory.models import InventoryItem, StockMovement, Supplier
from .models import (
    PurchaseOrder,
    PurchaseOrderItem,
    StockWastage,
    StockTransfer,
    StockTransferItem,
    StockAuditCount,
    StockAuditItem,
)
from .serializers import (
    AddStockSerializer,
    RemoveStockSerializer,
    AdjustStockSerializer,
    StockWastageSerializer,
    StockTransferSerializer,
    StockAuditCountSerializer,
    PurchaseOrderSerializer,
    SupplierDetailSerializer,
)
from .services import (
    add_stock,
    remove_stock,
    adjust_stock,
    record_wastage,
    check_all_low_stock_and_notify,
    get_inventory_valuation,
    get_food_cost_and_profitability,
    receive_purchase_order_delivery,
    reconcile_stock_audit,
)


class StockOperationsView(APIView):
    """
    Central operational endpoints for Adding, Removing, Adjusting stock,
    and triggering low-stock notification alerts.
    """
    permission_classes = [IsManagerOrAdmin]

    def post(self, request, operation=None):
        if operation == 'add':
            ser = AddStockSerializer(data=request.data)
            ser.is_valid(raise_exception=True)
            vd = ser.validated_data
            item, m = add_stock(
                item_id=vd['item_id'],
                quantity=vd['quantity'],
                unit_cost=vd.get('unit_cost'),
                batch_number=vd.get('batch_number', ''),
                expiry_date=vd.get('expiry_date'),
                notes=vd.get('notes', ''),
                performed_by=request.user
            )
            return Response({
                'message': f"Added {vd['quantity']} {item.unit} to {item.name}.",
                'itemId': str(item.id),
                'name': item.name,
                'currentStock': float(item.current_stock),
                'unit': item.unit,
                'stockValue': float(item.stock_value),
            }, status=status.HTTP_200_OK)

        elif operation == 'remove':
            ser = RemoveStockSerializer(data=request.data)
            ser.is_valid(raise_exception=True)
            vd = ser.validated_data
            item, m = remove_stock(
                item_id=vd['item_id'],
                quantity=vd['quantity'],
                reason=vd.get('reason', 'manual_removal'),
                notes=vd.get('notes', ''),
                performed_by=request.user
            )
            return Response({
                'message': f"Removed {vd['quantity']} {item.unit} from {item.name}.",
                'itemId': str(item.id),
                'name': item.name,
                'currentStock': float(item.current_stock),
                'reorderNeeded': item.reorder_needed,
            }, status=status.HTTP_200_OK)

        elif operation == 'adjust':
            ser = AdjustStockSerializer(data=request.data)
            ser.is_valid(raise_exception=True)
            vd = ser.validated_data
            item, m = adjust_stock(
                item_id=vd['item_id'],
                new_quantity=vd['new_quantity'],
                reason=vd.get('reason', 'count_reconciliation'),
                notes=vd.get('notes', ''),
                performed_by=request.user
            )
            return Response({
                'message': f"Adjusted {item.name} stock to {vd['new_quantity']} {item.unit}.",
                'itemId': str(item.id),
                'name': item.name,
                'currentStock': float(item.current_stock),
                'variance': float(m.quantity),
            }, status=status.HTTP_200_OK)

        elif operation == 'wastage':
            item_id = request.data.get('item_id')
            qty = Decimal(str(request.data.get('quantity', 0)))
            reason = request.data.get('reason', StockWastage.Reason.SPOILED)
            notes = request.data.get('notes', '')
            w = record_wastage(item_id, qty, reason=reason, notes=notes, performed_by=request.user)
            return Response({
                'message': f"Recorded {qty} {w.unit} wastage for {w.inventory_item.name}.",
                'wastageId': str(w.id),
                'cost': float(w.total_waste_cost),
                'currentStock': float(w.inventory_item.current_stock),
            }, status=status.HTTP_201_CREATED)

        return Response({'error': f"Unknown operation '{operation}'"}, status=status.HTTP_400_BAD_REQUEST)


class StockValuationView(APIView):
    """
    GET /api/v1/stock/valuation/
    Total inventory asset value, category breakdown, high-value items, and reorder cost.
    """
    permission_classes = [IsManagerOrAdmin]

    def get(self, request):
        valuation = get_inventory_valuation()
        return Response(valuation)


class StockHistoryView(APIView):
    """
    GET /api/v1/stock/history/
    Full audit trail of all inventory additions, consumptions, adjustments, and wastage.
    """
    permission_classes = [IsManagerOrAdmin]

    def get(self, request):
        item_id = request.query_params.get('item_id', None)
        movement_type = request.query_params.get('type', None)

        qs = StockMovement.objects.select_related('inventory_item', 'performed_by').all()
        if item_id:
            qs = qs.filter(inventory_item_id=item_id)
        if movement_type:
            qs = qs.filter(movement_type=movement_type)

        history = [
            {
                'id': m.id,
                'itemId': str(m.inventory_item_id),
                'itemName': m.inventory_item.name,
                'movementType': m.movement_type,
                'movementTypeDisplay': m.get_movement_type_display(),
                'quantity': float(m.quantity),
                'unit': m.inventory_item.unit,
                'costPerUnit': float(m.cost_per_unit),
                'totalCost': float(m.total_cost),
                'batchNumber': m.batch_number,
                'performedBy': m.performed_by.username if m.performed_by else 'System',
                'notes': m.notes,
                'createdAt': m.created_at.isoformat(),
            }
            for m in qs[:100]
        ]
        return Response(history)


class StockAlertsScanView(APIView):
    """
    POST /api/v1/stock/check-alerts/
    Triggers automated scan for items reaching reorder thresholds and dispatches notifications.
    """
    permission_classes = [IsManagerOrAdmin]

    def post(self, request):
        alert_count = check_all_low_stock_and_notify()
        return Response({
            'message': f"Scan complete. Dispatched {alert_count} low-stock notification alert(s).",
            'alertsGenerated': alert_count
        })


class FoodCostProfitabilityView(APIView):
    """
    GET /api/v1/stock/profitability/
    Strategic Menu Engineering & Profitability Dashboard:
    - Calculates Ingredient Cost, Selling Price, Gross Margin (€), and Food Cost % for every dish.
    - Highlights Most Profitable, Least Profitable, Best Sellers, Slow-Moving, and High-Cost Ingredients.
    """
    permission_classes = [IsManagerOrAdmin]

    def get(self, request):
        data = get_food_cost_and_profitability()
        return Response(data)


class SupplierManagementViewSet(viewsets.ModelViewSet):
    """
    Supplier Management ViewSet:
    Supplier profiles, contact info, products supplied with purchase prices, order history, and notes.
    """
    queryset = Supplier.objects.all()
    serializer_class = SupplierDetailSerializer
    permission_classes = [IsManagerOrAdmin]


class PurchaseOrderViewSet(viewsets.ModelViewSet):
    """
    Purchase Order Management & Delivery Receiving ViewSet.
    """
    queryset = PurchaseOrder.objects.select_related('supplier', 'created_by', 'received_by').prefetch_related('items__inventory_item').all()
    serializer_class = PurchaseOrderSerializer
    permission_classes = [IsManagerOrAdmin]

    def perform_create(self, serializer):
        po = serializer.save(created_by=self.request.user)
        # Parse items if provided in request body
        items_data = self.request.data.get('items', [])
        for it in items_data:
            PurchaseOrderItem.objects.create(
                purchase_order=po,
                inventory_item_id=it['inventory_item_id'],
                quantity_ordered=Decimal(str(it['quantity_ordered'])),
                unit_cost=Decimal(str(it.get('unit_cost', 0))),
                unit=it.get('unit', '')
            )
        po.recalculate_totals()

    @action(detail=True, methods=['post'])
    def receive(self, request, pk=None):
        """
        POST /api/v1/stock/purchase-orders/<id>/receive/
        Records incoming supplier deliveries, increments InventoryItem stock,
        and logs stock purchase movements.
        """
        po = self.get_object()
        received_items = request.data.get('received_items', [])
        invoice_num = request.data.get('invoice_number', '')

        updated_po = receive_purchase_order_delivery(
            po_id=po.id,
            received_items=received_items,
            invoice_number=invoice_num,
            received_by=request.user
        )

        return Response({
            'message': f"Delivery recorded for {updated_po.po_number}. Status: {updated_po.get_status_display()}.",
            'purchaseOrder': PurchaseOrderSerializer(updated_po).data
        })


class StockTransferViewSet(viewsets.ModelViewSet):
    """
    Stock Transfer between storage locations ViewSet.
    """
    queryset = StockTransfer.objects.select_related('transferred_by').prefetch_related('items__inventory_item').all()
    serializer_class = StockTransferSerializer
    permission_classes = [IsManagerOrAdmin]

    def perform_create(self, serializer):
        transfer = serializer.save(transferred_by=self.request.user)
        items_data = self.request.data.get('items', [])
        for it in items_data:
            StockTransferItem.objects.create(
                transfer=transfer,
                inventory_item_id=it['inventory_item_id'],
                quantity=Decimal(str(it['quantity'])),
                unit=it.get('unit', '')
            )


class StockAuditCountViewSet(viewsets.ModelViewSet):
    """
    Manual Stock Counts & Physical Inventory Audits ViewSet.
    """
    queryset = StockAuditCount.objects.select_related('performed_by').prefetch_related('items__inventory_item').all()
    serializer_class = StockAuditCountSerializer
    permission_classes = [IsManagerOrAdmin]

    def perform_create(self, serializer):
        audit = serializer.save(performed_by=self.request.user)
        items_data = self.request.data.get('items', [])
        for it in items_data:
            item_obj = InventoryItem.objects.get(id=it['inventory_item_id'])
            exp_stock = it.get('expected_stock', item_obj.current_stock)
            act_stock = it.get('actual_stock', exp_stock)
            StockAuditItem.objects.create(
                audit=audit,
                inventory_item=item_obj,
                expected_stock=Decimal(str(exp_stock)),
                actual_stock=Decimal(str(act_stock)),
                unit_cost=item_obj.purchase_price
            )
        audit.calculate_totals()

    @action(detail=True, methods=['post'])
    def reconcile(self, request, pk=None):
        """
        POST /api/v1/stock/audits/<id>/reconcile/
        1-Click Reconcile: Applies counted physical actuals to live inventory stock levels.
        """
        audit = self.get_object()
        updated_audit = reconcile_stock_audit(audit.id, performed_by=request.user)
        return Response({
            'message': f"Stock Audit {updated_audit.audit_number} reconciled. Inventory levels updated.",
            'audit': StockAuditCountSerializer(updated_audit).data
        })


class StockWastageViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only viewset for auditing damaged, spoiled, and expired stock losses.
    """
    queryset = StockWastage.objects.select_related('inventory_item', 'logged_by').all()
    serializer_class = StockWastageSerializer
    permission_classes = [IsManagerOrAdmin]

