from django.contrib import admin

from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product_id", "product_name", "unit_price", "quantity", "reservation_id")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "customer_id", "status", "total_amount", "created")
    list_filter = ("status", "created")
    search_fields = ("idempotency_key", "customer_id")
    readonly_fields = ("id", "customer_id", "idempotency_key", "total_amount", "created", "updated")
    inlines = [OrderItemInline]
