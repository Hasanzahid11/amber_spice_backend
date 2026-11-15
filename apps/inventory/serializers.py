from decimal import Decimal
from rest_framework import serializers

from apps.menu.models import Dish
from .models import (
    InventoryItem,
    Recipe,
    RecipeIngredient,
    StockMovement,
    Supplier,
)


class SupplierSerializer(serializers.ModelSerializer):
    contactName = serializers.CharField(source='contact_name', required=False, allow_blank=True)
    leadTimeDays = serializers.IntegerField(source='lead_time_days', required=False)
    paymentTerms = serializers.CharField(source='payment_terms', required=False, allow_blank=True)
    isActive = serializers.BooleanField(source='is_active', required=False)
    itemsCount = serializers.IntegerField(source='items_count', read_only=True)

    class Meta:
        model = Supplier
        fields = [
            'id',
            'name',
            'contact_name',
            'contactName',
            'email',
            'phone',
            'address',
            'lead_time_days',
            'leadTimeDays',
            'payment_terms',
            'paymentTerms',
            'notes',
            'is_active',
            'isActive',
            'itemsCount',
            'created_at',
            'updated_at',
        ]

    def to_internal_value(self, data):
        normalized = dict(data)
        mappings = {
            'contactName': 'contact_name',
            'leadTimeDays': 'lead_time_days',
            'paymentTerms': 'payment_terms',
            'isActive': 'is_active',
        }
        for camel, snake in mappings.items():
            if camel in normalized and snake not in normalized:
                normalized[snake] = normalized[camel]
        return super().to_internal_value(normalized)


class InventoryItemSerializer(serializers.ModelSerializer):
    # Preserved Legacy API Fields (100% backward compatible)
    currentStock = serializers.DecimalField(source='current_stock', max_digits=12, decimal_places=3, required=False)
    minimumStock = serializers.DecimalField(source='minimum_stock', max_digits=12, decimal_places=3, required=False)
    lastRestocked = serializers.DateTimeField(source='last_restocked', read_only=True)
    status = serializers.CharField(read_only=True)

    # Modern Restaurant Inventory Fields
    reorderLevel = serializers.DecimalField(source='reorder_level', max_digits=12, decimal_places=3, required=False)
    purchasePrice = serializers.DecimalField(source='purchase_price', max_digits=10, decimal_places=2, required=False)
    expiryDate = serializers.DateField(source='expiry_date', required=False, allow_null=True)
    batchNumber = serializers.CharField(source='batch_number', required=False, allow_blank=True)
    storageLocation = serializers.CharField(source='storage_location', required=False, allow_blank=True)
    supplierRef = serializers.PrimaryKeyRelatedField(
        source='supplier_ref',
        queryset=Supplier.objects.all(),
        required=False,
        allow_null=True
    )
    supplierDetails = SupplierSerializer(source='supplier_ref', read_only=True)
    reorderNeeded = serializers.BooleanField(source='reorder_needed', read_only=True)
    isExpiringSoon = serializers.BooleanField(source='is_expiring_soon', read_only=True)
    stockValue = serializers.DecimalField(source='stock_value', max_digits=12, decimal_places=2, read_only=True)
    isActive = serializers.BooleanField(source='is_active', required=False)

    class Meta:
        model = InventoryItem
        fields = [
            # Legacy fields
            'id',
            'name',
            'category',
            'currentStock',
            'minimumStock',
            'unit',
            'status',
            'lastRestocked',
            'supplier',
            # Snake case & modern aliases
            'current_stock',
            'minimum_stock',
            'reorder_level',
            'reorderLevel',
            'purchase_price',
            'purchasePrice',
            'expiry_date',
            'expiryDate',
            'batch_number',
            'batchNumber',
            'storage_location',
            'storageLocation',
            'supplier_ref',
            'supplierRef',
            'supplierDetails',
            'reorderNeeded',
            'isExpiringSoon',
            'stockValue',
            'is_active',
            'isActive',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'status', 'lastRestocked', 'reorderNeeded', 'isExpiringSoon', 'stockValue', 'created_at', 'updated_at']

    def to_internal_value(self, data):
        normalized = dict(data)
        mappings = {
            'currentStock': 'current_stock',
            'minimumStock': 'minimum_stock',
            'reorderLevel': 'reorder_level',
            'purchasePrice': 'purchase_price',
            'expiryDate': 'expiry_date',
            'batchNumber': 'batch_number',
            'storageLocation': 'storage_location',
            'supplierRef': 'supplier_ref',
            'isActive': 'is_active',
        }
        for camel, snake in mappings.items():
            if camel in normalized and snake not in normalized:
                normalized[snake] = normalized[camel]
        return super().to_internal_value(normalized)


class RecipeIngredientSerializer(serializers.ModelSerializer):
    inventoryItem = serializers.PrimaryKeyRelatedField(
        source='inventory_item',
        queryset=InventoryItem.objects.all(),
        required=False
    )
    inventoryItemName = serializers.CharField(source='inventory_item.name', read_only=True)
    inventoryItemCategory = serializers.CharField(source='inventory_item.category', read_only=True)
    inventoryItemUnit = serializers.CharField(source='inventory_item.unit', read_only=True)
    inventoryItemStock = serializers.DecimalField(source='inventory_item.current_stock', max_digits=12, decimal_places=3, read_only=True)
    inventoryItemPrice = serializers.DecimalField(source='inventory_item.purchase_price', max_digits=10, decimal_places=2, read_only=True)
    quantityInItemUnit = serializers.DecimalField(source='quantity_in_item_unit', max_digits=10, decimal_places=3, read_only=True)
    cost = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = RecipeIngredient
        fields = [
            'id',
            'recipe',
            'inventory_item',
            'inventoryItem',
            'inventoryItemName',
            'inventoryItemCategory',
            'inventoryItemUnit',
            'inventoryItemStock',
            'inventoryItemPrice',
            'quantity',
            'unit',
            'notes',
            'quantityInItemUnit',
            'cost',
        ]
        read_only_fields = ['id', 'cost', 'quantityInItemUnit']
        extra_kwargs = {
            'recipe': {'required': False}
        }

    def to_internal_value(self, data):
        normalized = dict(data)
        if 'inventoryItem' in normalized and 'inventory_item' not in normalized:
            normalized['inventory_item'] = normalized['inventoryItem']
        return super().to_internal_value(normalized)


class RecipeSerializer(serializers.ModelSerializer):
    dishName = serializers.CharField(source='dish.name', read_only=True)
    dishPrice = serializers.DecimalField(source='dish.price', max_digits=10, decimal_places=2, read_only=True)
    yieldPortions = serializers.IntegerField(source='yield_portions', required=False, default=1)
    prepTimeMinutes = serializers.IntegerField(source='prep_time_minutes', required=False)
    isActive = serializers.BooleanField(source='is_active', required=False)
    ingredients = RecipeIngredientSerializer(many=True, required=False)
    totalCost = serializers.DecimalField(source='total_cost', max_digits=10, decimal_places=2, read_only=True)
    costPerPortion = serializers.DecimalField(source='cost_per_portion', max_digits=10, decimal_places=2, read_only=True)
    foodCostPercentage = serializers.FloatField(source='food_cost_percentage', read_only=True)

    class Meta:
        model = Recipe
        fields = [
            'id',
            'dish',
            'dishName',
            'dishPrice',
            'name',
            'yield_portions',
            'yieldPortions',
            'instructions',
            'prep_time_minutes',
            'prepTimeMinutes',
            'is_active',
            'isActive',
            'ingredients',
            'totalCost',
            'costPerPortion',
            'foodCostPercentage',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'totalCost', 'costPerPortion', 'foodCostPercentage', 'created_at', 'updated_at']

    def to_internal_value(self, data):
        normalized = dict(data)
        mappings = {
            'yieldPortions': 'yield_portions',
            'prepTimeMinutes': 'prep_time_minutes',
            'isActive': 'is_active',
        }
        for camel, snake in mappings.items():
            if camel in normalized and snake not in normalized:
                normalized[snake] = normalized[camel]
        return super().to_internal_value(normalized)

    def create(self, validated_data):
        ingredients_data = validated_data.pop('ingredients', [])
        recipe = Recipe.objects.create(**validated_data)

        for ing in ingredients_data:
            RecipeIngredient.objects.create(recipe=recipe, **ing)

        return recipe

    def update(self, instance, validated_data):
        ingredients_data = validated_data.pop('ingredients', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if ingredients_data is not None:
            # Recreate ingredients list if passed
            instance.ingredients.all().delete()
            for ing in ingredients_data:
                RecipeIngredient.objects.create(recipe=instance, **ing)

        return instance


class StockMovementSerializer(serializers.ModelSerializer):
    inventoryItem = serializers.PrimaryKeyRelatedField(source='inventory_item', read_only=True)
    inventoryItemName = serializers.CharField(source='inventory_item.name', read_only=True)
    inventoryItemUnit = serializers.CharField(source='inventory_item.unit', read_only=True)
    movementType = serializers.CharField(source='movement_type', read_only=True)
    movementTypeDisplay = serializers.CharField(source='get_movement_type_display', read_only=True)
    previousStock = serializers.DecimalField(source='previous_stock', max_digits=12, decimal_places=3, read_only=True)
    newStock = serializers.DecimalField(source='new_stock', max_digits=12, decimal_places=3, read_only=True)
    unitCost = serializers.DecimalField(source='unit_cost', max_digits=10, decimal_places=2, read_only=True)
    totalCost = serializers.DecimalField(source='total_cost', max_digits=10, decimal_places=2, read_only=True)
    orderNumber = serializers.CharField(source='order.order_number', read_only=True, allow_null=True)
    performedByName = serializers.CharField(source='performed_by.username', read_only=True, allow_null=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)

    class Meta:
        model = StockMovement
        fields = [
            'id',
            'inventory_item',
            'inventoryItem',
            'inventoryItemName',
            'inventoryItemUnit',
            'movement_type',
            'movementType',
            'movementTypeDisplay',
            'quantity',
            'previous_stock',
            'previousStock',
            'new_stock',
            'newStock',
            'unit_cost',
            'unitCost',
            'total_cost',
            'totalCost',
            'reference',
            'order',
            'orderNumber',
            'performed_by',
            'performedByName',
            'notes',
            'created_at',
            'createdAt',
        ]


class RestockActionSerializer(serializers.Serializer):
    quantity = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal('0.001'))
    purchase_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, min_value=Decimal('0.00'))
    purchasePrice = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, min_value=Decimal('0.00'))
    supplier = serializers.CharField(max_length=200, required=False, allow_blank=True)
    batch_number = serializers.CharField(max_length=100, required=False, allow_blank=True)
    batchNumber = serializers.CharField(max_length=100, required=False, allow_blank=True)
    expiry_date = serializers.DateField(required=False, allow_null=True)
    expiryDate = serializers.DateField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        if 'purchasePrice' in attrs and 'purchase_price' not in attrs:
            attrs['purchase_price'] = attrs['purchasePrice']
        if 'batchNumber' in attrs and 'batch_number' not in attrs:
            attrs['batch_number'] = attrs['batchNumber']
        if 'expiryDate' in attrs and 'expiry_date' not in attrs:
            attrs['expiry_date'] = attrs['expiryDate']
        return attrs


class AdjustActionSerializer(serializers.Serializer):
    new_stock = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal('0.000'), required=False)
    newStock = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal('0.000'), required=False)
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True)

    def validate(self, attrs):
        if 'newStock' in attrs and 'new_stock' not in attrs:
            attrs['new_stock'] = attrs['newStock']
        if 'new_stock' not in attrs:
            raise serializers.ValidationError({"new_stock": "new_stock or newStock is required."})
        return attrs


class WasteActionSerializer(serializers.Serializer):
    quantity = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal('0.001'))
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True)


class OrderItemConsumptionInputSerializer(serializers.Serializer):
    dish_id = serializers.IntegerField(required=False)
    dishId = serializers.IntegerField(required=False)
    quantity = serializers.IntegerField(default=1, min_value=1)

    def validate(self, attrs):
        if 'dishId' in attrs and 'dish_id' not in attrs:
            attrs['dish_id'] = attrs['dishId']
        if 'dish_id' not in attrs:
            raise serializers.ValidationError({"dish_id": "dish_id is required."})
        return attrs


class CalculateConsumptionInputSerializer(serializers.Serializer):
    items = OrderItemConsumptionInputSerializer(many=True)
