from django.db import transaction

from inventory.models import InventoryItem


class InvalidCatalogEvent(ValueError):
    """Raised when a Catalog event does not match the expected format."""


@transaction.atomic
def process_catalog_event(message):

    if not isinstance(message, dict):
        raise InvalidCatalogEvent("Event payload must be a JSON object.")

    if message.get("event") != "product.created":
        raise InvalidCatalogEvent("Unsupported Catalog event type.")

    data = message.get("data")

    if not isinstance(data, dict):
        raise InvalidCatalogEvent("Event data must be a JSON object.")

    product_id = data.get("id")
    initial_quantity = data.get("stock")

    if type(product_id) is not int or product_id <= 0:
        raise InvalidCatalogEvent("data.id must be a positive integer.")

    if type(initial_quantity) is not int or initial_quantity < 0:
        raise InvalidCatalogEvent("data.stock must be a non-negative integer.")

    item, created = InventoryItem.objects.get_or_create(product_id=product_id, defaults={"quantity":initial_quantity})

    return item, created
