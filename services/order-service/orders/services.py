import logging

from django.db import IntegrityError, transaction

from .clients.cart import get_cart, clear_cart
from .clients.catalog import get_product
from .clients.inventory import reserve_stock, release_stock
from .clients.common import DownstreamUnavailable, InventoryReservationRejected
from .models import Order, OrderItem


logger = logging.getLogger(__name__)


class CheckoutError(Exception):
    def __init__(self, detail, status_code):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def _get_cart_lines(cart):
    items = cart.get("items")
    if not isinstance(items, list):
        raise CheckoutError("Cart response has an invalid format.", 502)

    quantities = {}
    for item in items:
        if not isinstance(item, dict):
            raise CheckoutError("Cart contains an invalid item.", 502)

        try:
            product_id = int(item.get("product_id"))
            quantity = int(item.get("quantity"))
        except (TypeError, ValueError):
            raise CheckoutError("Cart contains invalid product or quantity data.", 400)

        if product_id <= 0 or quantity <= 0:
            raise CheckoutError("Product IDs and quantities must be positive.", 400)

        quantities[product_id] = (quantities.get(product_id, 0) + quantity)

        if not quantities:
            raise CheckoutError("Cannot create an order from empty cart.", 400)

    return quantities


def _prepare_order_items(quantities, authorization):
    prepared = []

    for product_id, quantity in sorted(quantities.items()):
        product = get_product(product_id, authorization)

        if product is None:
            raise CheckoutError(f"Product {product_id} does not exist.", 400)

        if not product.get("is_active"):
            raise CheckoutError(f"Product {product_id} is not active.", 400)

        price = product["price"]
        if price < 0:
            raise CheckoutError(f"Product {product_id} has an invalid price.", 502)

        name = product.get("name")
        if not isinstance(name, str) or not name:
            raise CheckoutError(f"Product {product_id} has an invalid name.", 502)

        prepared.append({"product_id": product_id, "product_name": name, "unit_price": price, "quantity": quantity})

    return prepared


def _create_order(customer_id, idempotency_key, prepared):
    total = sum(item["unit_price"] * item["quantity"] for item in prepared)

    try:
        with transaction.atomic():
            order = Order.objects.create(customer_id=customer_id, idempotency_key=idempotency_key,
                                         status=Order.Status.PROCESSING, total_amount=total)

            OrderItem.objects.bulk_create([
                OrderItem(
                    order=order,
                    product_id=item["product_id"],
                    product_name=item["product_name"],
                    unit_price=item["unit_price"],
                    quantity=item["quantity"],
                ) for item in prepared
            ])
        return order, True
    except IntegrityError:
        existing = (Order.objects.filter(customer_id=customer_id, idempotency_key=idempotency_key)
                    .prefetch_related("items").first())

        if existing is not None:
            return existing, False

        raise


def _compensate_reservations(order, authorization):
    compensation_failed = False

    for item in order.items.all():
        try:
            release_stock(authorization, item.reservation_id)
        except DownstreamUnavailable:
            compensation_failed = True
            logger.exception(f"Could not compensate reservation {item.reservation_id} for order {order.id}")

    return compensation_failed


def _mark_order_failed(order, authorization, reason):
    compensation_failed = _compensate_reservations(order, authorization)
    order.status = Order.Status.FAILED

    if compensation_failed:
        order.failure_reason = f"{reason} Compensation was incomplete; inventory reconciliation is required."
    else:
        order.failure_reason = reason

    order.save(update_fields=["status", "failure_reason", "updated"])


def checkout(customer_id, authorization, idempotency_key):
    existing = (Order.objects.filter(customer_id=customer_id, idempotency_key=idempotency_key)
                .prefetch_related("items").first())

    if existing is not None:
        return existing, False

    try:
        cart = get_cart(authorization)
        quantities = _get_cart_lines(cart)
        prepared = _prepare_order_items(quantities, authorization)
    except DownstreamUnavailable as exc:
        raise CheckoutError(str(exc), 503) from exc

    order, created = _create_order(customer_id, idempotency_key, prepared)

    if not created:
        return order, False

    try:
        for item in order.items.all():
            reserve_stock(authorization=authorization, reservation_id=item.reservation_id,
                          product_id=item.product_id, quantity=item.quantity)

        clear_cart(authorization)

    except InventoryReservationRejected as exc:
        _mark_order_failed(order, authorization, str(exc))
        raise CheckoutError(str(exc), 409) from exc

    except DownstreamUnavailable as exc:
        _mark_order_failed(order, authorization, str(exc))
        raise CheckoutError(str(exc), 503) from exc

    order.status = Order.Status.AWAITING_PAYMENT
    order.save(update_fields=["status", "updated"])

    return order, True
