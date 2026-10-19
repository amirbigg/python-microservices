import os

import httpx


INVENTORY_SERVICE_URL = os.getenv("INVENTORY_SERVICE_URL", "http://inventory-service:8003")


class InventoryServiceError(Exception):
    """Raised when Inventory Service cannot be reached or returns invalid data."""


def get_inventory_item(product_id, authorization=None):
    url = f"{INVENTORY_SERVICE_URL}/api/inventory/items/{product_id}/"
    headers = {}

    if authorization:
        headers["Authorization"] = authorization

    try:
        response = httpx.get(url, headers=headers, timeout=3.0)
    except httpx.RequestError as exc:
        raise InventoryServiceError("Inventory Service is unavailable.") from exc

    if response.status_code == 404:
        return None

    if response.status_code != 200:
        raise InventoryServiceError("Inventory Service returned an unexpected response.")

    try:
        data = response.json()
    except ValueError as exc:
        raise InventoryServiceError("Inventory Service returned invalid JSON.") from exc

    quantity = data.get("quantity") if isinstance(data, dict) else None

    if type(quantity) is not int or quantity < 0:
        raise InventoryServiceError("Inventory Service returned invalid inventory data.")

    return data
