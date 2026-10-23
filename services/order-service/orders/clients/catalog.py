import os

import httpx

from .common import DownstreamUnavailable


CATALOG_SERVICE_URL = os.getenv("CATALOG_SERVICE_URL", "http://catalog-service:8001")


def get_product(product_id, authorization):
    try:
        response = httpx.get(f"{CATALOG_SERVICE_URL}/api/catalog/products/{product_id}/",
                             headers={"Authorization":authorization}, timeout=5.0)
    except httpx.RequestError as exc:
        raise DownstreamUnavailable("Catalog service is unavailable.") from exc

    if response.status_code == 404:
        return None

    if response.status_code != 200:
        raise DownstreamUnavailable("Could not retrieve product information.")

    try:
        data = response.json()
    except ValueError as exc:
        raise DownstreamUnavailable("Catalog Service returned invalid JSON.") from exc

    if not isinstance(data, dict):
        raise DownstreamUnavailable("Catalog Service returned an invalid response.")

    return data
