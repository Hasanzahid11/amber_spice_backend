from decimal import Decimal
from rest_framework import serializers
from .models import InventoryCategory, InventoryItem, StockAlert, WastageRecord


class InventoryCategorySerializer(serializers.ModelSerializer):
    itemsCount = serializers.SerializerMethodField(read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)

    class Meta:
        model = InventoryCategory
        fields = [
            'id',
            'name',
            'slug',
            'description',
            'is_active',
            'itemsCount',
            'createdAt',
            'updatedAt',
        ]
        read_only_fields = ['id', 'slug', 'createdAt', 'updatedAt']

    def get_itemsCount(self, obj) -> int:
        return obj.items.count() or InventoryItem.objects.filter(category__iexact=obj.name).count()

    def validate_name(self, value):
        trimmed = value.strip() if value else ''
        if not trimmed:
            raise serializers.ValidationError('Category name cannot be blank.')
        qs = InventoryCategory.objects.filter(name__iexact=trimmed)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('An inventory category with this name already exists.')
        return trimmed


class InventoryItemSerializer(serializers.ModelSerializer):
    currentStock = serializers.DecimalField(source='current_stock', max_digits=10, decimal_places=2, min_value=Decimal('0'))
    minimumStock = serializers.DecimalField(source='minimum_stock', max_digits=10, decimal_places=2, min_value=Decimal('0'))
    lastRestocked = serializers.DateTimeField(source='last_restocked', read_only=True)
    status = serializers.CharField(read_only=True)
    categoryRef = serializers.PrimaryKeyRelatedField(
        source='category_ref',
        queryset=InventoryCategory.objects.all(),
        required=False,
        allow_null=True
    )
    categoryName = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = InventoryItem
        fields = [
            'id',
            'name',
            'category',
            'categoryRef',
            'categoryName',
            'currentStock',
            'minimumStock',
            'unit',
            'status',
            'lastRestocked',
            'supplier',
        ]

    def get_categoryName(self, obj) -> str:
        return obj.category_ref.name if obj.category_ref else obj.category

    def to_internal_value(self, data):
        data = data.copy() if hasattr(data, 'copy') else dict(data)
        if 'current_stock' in data and 'currentStock' not in data:
            data['currentStock'] = data.pop('current_stock')
        if 'minimum_stock' in data and 'minimumStock' not in data:
            data['minimumStock'] = data.pop('minimum_stock')
        if 'category_ref' in data and 'categoryRef' not in data:
            data['categoryRef'] = data.pop('category_ref')
        return super().to_internal_value(data)

    def validate_name(self, value):
        trimmed = value.strip() if value else ''
        if not trimmed:
            raise serializers.ValidationError('Ingredient name cannot be blank.')
        return trimmed


class StockAlertSerializer(serializers.ModelSerializer):
    stock_remaining_percent = serializers.IntegerField(min_value=0, max_value=100)
    item_name = serializers.CharField(source='item.name', read_only=True)
    reporter_name = serializers.CharField(source='reported_by.username', read_only=True)

    class Meta:
        model = StockAlert
        fields = ['id', 'item', 'item_name', 'stock_remaining_percent', 'note', 'resolved', 'reporter_name', 'created_at']
        read_only_fields = ['created_at']


class WastageSerializer(serializers.ModelSerializer):
    quantity = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0.01'))
    item_name = serializers.CharField(source='item.name', read_only=True)

    class Meta:
        model = WastageRecord
        fields = ['id', 'item', 'item_name', 'quantity', 'reason', 'created_at']
        read_only_fields = ['created_at']

