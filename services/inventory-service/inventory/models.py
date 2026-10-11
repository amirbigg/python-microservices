from django.db import models


class InventoryItem(models.Model):
    product_id = models.PositiveBigIntegerField(unique=True)
    quantity = models.PositiveIntegerField(default=0)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["product_id"]

    def __str__(self):
        return f"Product {self.product_id}: {self.quantity}"
