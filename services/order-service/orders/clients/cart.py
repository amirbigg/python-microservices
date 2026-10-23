import os

import httpx

from .common import DownstreamUnavailable


CART_SERVICE_URL = os.getenv("CART_SERVICE_URL", "http://cart-service:8002")

def get_cart(authorization):
    try:
        response = httpx.get(f"{CART_SERVICE_URL}/api/cart/", headers={"Authorization":authorization}, timeout=5.0)
    except httpx.RequestError as exc:
        raise DownstreamUnavailable("Cart Service is unavailable.") from exc

    if response.status_code != 200:
        raise DownstreamUnavailable("Could not retrieve the cart.")

    try:
        data = response.json()
    except ValueError as exc:
        raise DownstreamUnavailable("Cart Service returned invalid JSON.") from exc

    if not isinstance(data, dict):
        raise DownstreamUnavailable("Cart Service returned an invalid response.")

    return data


def clear_cart(authorization):
    try:
        response = httpx.delete(f"{CART_SERVICE_URL}/api/cart/clear/", headers={"Authorization": authorization}, timeout=5.0)
    except httpx.RequestError as exc:
        raise DownstreamUnavailable("Could not clear the cart.") from exc

    if response.status_code != 200:
        raise DownstreamUnavailable("Could not clear the cart.")
