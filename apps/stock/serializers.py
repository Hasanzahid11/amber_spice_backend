from decimal import Decimal
from rest_framework import serializers

from apps.inventory.models import InventoryItem, StockMovement, Supplier
from apps.menu.models import Dish
from .models import (
    PurchaseOrder,
    PurchaseOrderItem,
    StockWastage,
    StockTransfer,
    StockTransferItem,
    StockAuditCount,
    StockAuditItem,
)


class AddStockSerializer(serializers.Serializer):
    item_id = serializers.UUIDField(required=True)
    quantity = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal('0.001'), required=True)
    unit_cost = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    batch_number = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    expiry_date = serializers.DateField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, default='')


class RemoveStockSerializer(serializers.Serializer):
    item_id = serializers.UUIDField(required=True)
    quantity = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal('0.001'), required=True)
    reason = serializers.CharField(max_length=100, required=False, default='kitchen_prep')
    notes = serializers.CharField(required=False, allow_blank=True, default='')


class AdjustStockSerializer(serializers.Serializer):
    item_id = serializers.UUIDField(required=True)
    new_quantity = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal('0.000'), required=True)
    reason = serializers.CharField(max_length=150, required=False, default='Manual reconciliation')
    notes = serializers.CharField(required=False, allow_blank=True, default='')


class StockWastageSerializer(serializers.ModelSerializer):
    itemName = serializers.CharField(source='inventory_item.name', read_only=True)
    itemCategory = serializers.CharField(source='inventory_item.category', read_only=True)
    reasonDisplay = serializers.CharField(source='get_reason_display', read_only=True)
    loggedByName = serializers.SerializerMethodField()

    class Meta:
        model = StockWastage
        fields = [
            'id',
            'inventory_item',
            'itemName',
            'itemCategory',
            'quantity',
            'unit',
            'cost_per_unit',
            'total_waste_cost',
            'reason',
            'reasonDisplay',
            'notes',
            'logged_by',
            'loggedByName',
            'created_at',
        ]
        read_only_fields = ['id', 'unit', 'cost_per_unit', 'total_waste_cost', 'created_at']

    def get_loggedByName(self, obj) -> str:
        if obj.logged_by:
            return obj.logged_by.get_full_name() or obj.logged_by.username
        return 'Staff'


class StockTransferItemSerializer(serializers.ModelSerializer):
    itemName = serializers.CharField(source='inventory_item.name', read_only=True)

    class Meta:
        model = StockTransferItem
        fields = ['id', 'inventory_item', 'itemName', 'quantity', 'unit']


class StockTransferSerializer(serializers.ModelSerializer):
    items = StockTransferItemSerializer(many=True, read_only=True)
    transferredByName = serializers.SerializerMethodField()

    class Meta:
        model = StockTransfer
        fields = [
            'id',
            'transfer_number',
            'from_location',
            'to_location',
            'status',
            'notes',
            'transferred_by',
            'transferredByName',
            'items',
            'created_at',
        ]
        read_only_fields = ['id', 'transfer_number', 'created_at']

    def get_transferredByName(self, obj) -> str:
        if obj.transferred_by:
            return obj.transferred_by.get_full_name() or obj.transferred_by.username
        return 'Staff'


class StockAuditItemSerializer(serializers.ModelSerializer):
    itemName = serializers.CharField(source='inventory_item.name', read_only=True)

    class Meta:
        model = StockAuditItem
        fields = [
            'id',
            'inventory_item',
            'itemName',
            'expected_stock',
            'actual_stock',
            'variance',
            'unit',
            'unit_cost',
            'variance_cost',
            'notes',
        ]
        read_only_fields = ['id', 'expected_stock', 'variance', 'unit', 'unit_cost', 'variance_cost']


class StockAuditCountSerializer(serializers.ModelSerializer):
    items = StockAuditItemSerializer(many=True, read_only=True)
    performedByName = serializers.SerializerMethodField()

    class Meta:
        model = StockAuditCount
        fields = [
            'id',
            'audit_number',
            'name',
            'status',
            'audit_date',
            'total_expected_value',
            'total_actual_value',
            'total_variance_value',
            'performed_by',
            'performedByName',
            'notes',
            'items',
            'created_at',
            'reconciled_at',
        ]
        read_only_fields = ['id', 'audit_number', 'total_expected_value', 'total_actual_value', 'total_variance_value', 'created_at', 'reconciled_at']

    def get_performedByName(self, obj) -> str:
        if obj.performed_by:
            return obj.performed_by.get_full_name() or obj.performed_by.username
        return 'Staff'


class PurchaseOrderItemSerializer(serializers.ModelSerializer):
    itemName = serializers.CharField(source='inventory_item.name', read_only=True)

    class Meta:
        model = PurchaseOrderItem
        fields = [
            'id',
            'inventory_item',
            'itemName',
            'quantity_ordered',
            'quantity_received',
            'unit',
            'unit_cost',
            'total_cost',
            'batch_number',
            'expiry_date',
            'is_fully_received',
        ]


class PurchaseOrderSerializer(serializers.ModelSerializer):
    items = PurchaseOrderItemSerializer(many=True, read_only=True)
    supplierName = serializers.CharField(source='supplier.name', read_only=True)
    createdByName = serializers.SerializerMethodField()
    receivedByName = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseOrder
        fields = [
            'id',
            'po_number',
            'supplier',
            'supplierName',
            'status',
            'order_date',
            'expected_delivery_date',
            'actual_delivery_date',
            'subtotal',
            'tax',
            'total_cost',
            'invoice_number',
            'notes',
            'created_by',
            'createdByName',
            'received_by',
            'receivedByName',
            'items',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'po_number', 'subtotal', 'total_cost', 'actual_delivery_date', 'created_at', 'updated_at']

    def get_createdByName(self, obj) -> str:
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.username
        return 'Staff'

    def get_receivedByName(self, obj) -> str:
        if obj.received_by:
            return obj.received_by.get_full_name() or obj.received_by.username
        return None


class SupplierDetailSerializer(serializers.ModelSerializer):
    """
    Supplier management view including contact information, products supplied with purchase prices,
    order history, and notes.
    """
    productsSupplied = serializers.SerializerMethodField()
    orderHistory = serializers.SerializerMethodField()

    class Meta:
        model = Supplier
        fields = [
            'id',
            'name',
            'contact_name',
            'email',
            'phone',
            'address',
            'lead_time_days',
            'payment_terms',
            'notes',
            'is_active',
            'productsSupplied',
            'orderHistory',
            'created_at',
            'updated_at',
        ]

    def get_productsSupplied(self, obj) -> list:
        items = obj.inventory_items.filter(is_active=True)
        return [
            {
                'id': str(it.id),
                'name': it.name,
                'category': it.category,
                'unit': it.unit,
                'purchasePrice': float(it.purchase_price),
                'currentStock': float(it.current_stock),
                'reorderLevel': float(it.reorder_level),
            }
            for it in items
        ]

    def get_orderHistory(self, obj) -> list:
        pos = obj.purchase_orders.all()[:10]
        return [
            {
                'id': str(po.id),
                'poNumber': po.po_number,
                'status': po.status,
                'orderDate': po.order_date.isoformat(),
                'actualDeliveryDate': po.actual_delivery_date.isoformat() if po.actual_delivery_date else None,
                'totalCost': float(po.total_cost),
                'invoiceNumber': po.invoice_number,
            }
            for po in pos
        ]

