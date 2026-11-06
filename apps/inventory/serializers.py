from rest_framework import serializers
from .models import InventoryItem


class InventoryItemSerializer(serializers.ModelSerializer):
    currentStock = serializers.DecimalField(source='current_stock', max_digits=10, decimal_places=2)
    minimumStock = serializers.DecimalField(source='minimum_stock', max_digits=10, decimal_places=2)
    lastRestocked = serializers.DateTimeField(source='last_restocked', read_only=True)
    status = serializers.CharField(read_only=True)

    class Meta:
        model = InventoryItem
        fields = [
            'id',
            'name',
            'category',
            'currentStock',
            'minimumStock',
            'unit',
            'status',
            'lastRestocked',
            'supplier',
        ]

