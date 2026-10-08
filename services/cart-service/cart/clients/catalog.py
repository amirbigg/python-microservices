import os
import httpx


CATALOG_SERVICE_URL = os.getenv("CATALOG_SERVICE_URL", "http://catalog-service:8001")


class CatalogServiceError(Exception):
    pass


def get_product(product_id):
    url = f"{CATALOG_SERVICE_URL}/api/catalog/products/{product_id}/"

    try:
        response = httpx.get(url, timeout=3.0)
    except httpx.RequestError as exc:
        raise CatalogServiceError("Catalog service is unavailable.") from exc

    if response.status_code == 404:
        return None

    if response.status_code != 200:
        raise CatalogServiceError(f"Catalog service returned status={response.status_code}, body={response.text}")

    return response.json()
