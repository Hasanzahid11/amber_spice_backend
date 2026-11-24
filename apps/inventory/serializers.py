from decimal import Decimal
from rest_framework import serializers
from .models import InventoryCategory, InventoryItem, StockAlert, WastageRecord, DishRecipe, StockTransaction
from apps.menu.models import Dish


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
    costPerUnit = serializers.DecimalField(source='cost_per_unit', max_digits=10, decimal_places=4, min_value=Decimal('0'), required=False)
    totalCost = serializers.DecimalField(source='total_cost', max_digits=10, decimal_places=2, read_only=True)
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
            'costPerUnit',
            'totalCost',
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
        if 'cost_per_unit' in data and 'costPerUnit' not in data:
            data['costPerUnit'] = data.pop('cost_per_unit')
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


class DishRecipeSerializer(serializers.ModelSerializer):
    dishName = serializers.CharField(source='dish.name', read_only=True)
    dishPrice = serializers.DecimalField(source='dish.price', max_digits=10, decimal_places=2, read_only=True)
    ingredientName = serializers.CharField(source='ingredient.name', read_only=True)
    ingredientUnit = serializers.CharField(source='ingredient.unit', read_only=True)
    ingredientCostPerUnit = serializers.DecimalField(source='ingredient.cost_per_unit', max_digits=10, decimal_places=4, read_only=True)
    cost = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)

    class Meta:
        model = DishRecipe
        fields = [
            'id',
            'dish',
            'dishName',
            'dishPrice',
            'ingredient',
            'ingredientName',
            'ingredientUnit',
            'ingredientCostPerUnit',
            'quantity',
            'unit',
            'notes',
            'cost',
            'createdAt',
            'updatedAt',
        ]
        read_only_fields = ['id', 'dishName', 'dishPrice', 'ingredientName', 'ingredientUnit', 'ingredientCostPerUnit', 'cost', 'createdAt', 'updatedAt']

    def validate_quantity(self, value):
        if value <= Decimal('0'):
            raise serializers.ValidationError('Recipe ingredient quantity must be greater than zero.')
        return value


class DishCostSummarySerializer(serializers.Serializer):
    dishId = serializers.IntegerField()
    dishName = serializers.CharField()
    dishCategory = serializers.CharField()
    dishPrice = serializers.DecimalField(max_digits=10, decimal_places=2)
    isAvailable = serializers.BooleanField()
    recipeItems = DishRecipeSerializer(many=True)
    totalFoodCost = serializers.DecimalField(max_digits=10, decimal_places=2)
    foodCostPercent = serializers.DecimalField(max_digits=6, decimal_places=2)
    grossProfit = serializers.DecimalField(max_digits=10, decimal_places=2)
    grossMarginPercent = serializers.DecimalField(max_digits=6, decimal_places=2)
    maxPortionsAvailable = serializers.IntegerField()


class StockTransactionSerializer(serializers.ModelSerializer):
    itemName = serializers.CharField(source='item.name', read_only=True)
    itemUnit = serializers.CharField(source='item.unit', read_only=True)
    orderNumber = serializers.CharField(source='order.order_number', read_only=True, default=None)
    createdByName = serializers.CharField(source='created_by.username', read_only=True, default='System')
    transactionType = serializers.CharField(source='transaction_type')
    quantityDelta = serializers.DecimalField(source='quantity_delta', max_digits=10, decimal_places=3)
    unitCost = serializers.DecimalField(source='unit_cost', max_digits=10, decimal_places=4, read_only=True)
    totalCost = serializers.DecimalField(source='total_cost', max_digits=10, decimal_places=2, read_only=True)
    balanceAfter = serializers.DecimalField(source='balance_after', max_digits=10, decimal_places=2, read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)

    class Meta:
        model = StockTransaction
        fields = [
            'id',
            'item',
            'itemName',
            'itemUnit',
            'transactionType',
            'quantityDelta',
            'unitCost',
            'totalCost',
            'balanceAfter',
            'order',
            'orderNumber',
            'createdByName',
            'notes',
            'createdAt',
        ]
        read_only_fields = ['id', 'itemName', 'itemUnit', 'orderNumber', 'createdByName', 'unitCost', 'totalCost', 'balanceAfter', 'createdAt']


class ManualStockAdjustmentSerializer(serializers.Serializer):
    item = serializers.PrimaryKeyRelatedField(queryset=InventoryItem.objects.all())
    transactionType = serializers.ChoiceField(choices=['PURCHASE', 'ADJUSTMENT', 'WASTAGE'])
    quantityDelta = serializers.DecimalField(max_digits=10, decimal_places=3)
    unitCost = serializers.DecimalField(max_digits=10, decimal_places=4, required=False, allow_null=True)
    notes = serializers.CharField(max_length=500, required=False, allow_blank=True, default='')


