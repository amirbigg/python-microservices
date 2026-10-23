import os

import httpx

from .common import DownstreamUnavailable, InventoryReservationRejected


INVENTORY_SERVICE_URL = os.getenv("INVENTORY_SERVICE_URL", "http://inventory-service:8003")


def reserve_stock(authorization, reservation_id, product_id, quantity):
    url = f"{INVENTORY_SERVICE_URL}/api/inventory/reservation/"
    payload = {"reservation_id": str(reservation_id), "product_id": product_id, "quantity": quantity}

    try:
        response = httpx.post(url, json=payload, headers={"Authorization": authorization}, timeout=5.0)
    except httpx.RequestError as exc:
        raise DownstreamUnavailable("Inventory Service is unavailable.") from exc

    if response.status_code in (200, 201):
        return response.json()

    if response.status_code in (404, 409):
        raise InventoryReservationRejected("Inventory rejected the reservation.")

    raise DownstreamUnavailable("Could not reserve stock.")


def release_stock(authorization, reservation_id):
    url = f"{INVENTORY_SERVICE_URL}/api/inventory/reservation/{reservation_id}/release/"

    try:
        response = httpx.post(url, headers={"Authorization":authorization}, timeout=5.0)
    except httpx.RequestError as exc:
        raise DownstreamUnavailable("Could not release an inventory reservation") from exc

    if response.status_code in (200, 404):
        return

    raise DownstreamUnavailable("Could not release an inventory reservation.")
