from rest_framework import serializers
from .models import InventoryItem


class InventoryItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryItem
        fields = ["id", "product_id", "quantity", "created", "updated"]
        read_only_fields = fields