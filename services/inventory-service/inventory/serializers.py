from rest_framework import serializers
from .models import InventoryItem, StockReservation


class InventoryItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryItem
        fields = ["id", "product_id", "quantity", "created", "updated"]
        read_only_fields = fields


class ReserveStockRequestSeriazlier(serializers.Serializer):
    reservation_id = serializers.UUIDField()
    product_id = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1)


class StockReservationSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(source="inventory_item.product_id", read_only=True)

    class Meta:
        model = StockReservation
        fields = [
            "reservation_id",
            "product_id",
            "quantity",
            "status",
            "created",
            "updated",
        ]
