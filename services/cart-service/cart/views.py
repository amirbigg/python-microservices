from django.core.cache import cache
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from .clients.catalog import CatalogServiceError, get_product


def get_cart_key(user_id):
    return f"cart:user:{user_id}"


class HealthCheckView(APIView):
    def get(self, request):
        return Response({"service": "cart-service", "status": "ok"})


class CartView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user_id = request.user.id
        cart = cache.get(get_cart_key(user_id), {"items":[]})
        return Response(cart)


class CartItemView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user_id = request.user.id
        product_id = request.data.get("product_id")
        quantity = request.data.get("quantity", 1)

        if not product_id:
            return Response({"detail": "product_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            quantity = int(quantity)
        except (TypeError, ValueError):
            return Response({"detail": "quantity must be a integer."}, status=status.HTTP_400_BAD_REQUEST)

        if quantity <= 0:
            return Response({"detail": "quantity must be greater than zero."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            product = get_product(product_id)
        except CatalogServiceError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        if product is None:
            return Response({"detail": "Product does not exist."}, status=status.HTTP_404_NOT_FOUND)

        if not product["is_active"]:
            return Response({"detail": "Product is not active."}, status=status.HTTP_400_BAD_REQUEST)

        key = get_cart_key(user_id)
        cart = cache.get(key, {"items":[]})

        for item in cart["items"]:
            if item["product_id"] == product_id:
                item["quantity"] += quantity
                break
        else:
            cart["items"].append({"product_id": product_id, "quantity": quantity})

        cache.set(key, cart)
        return Response(cart, status=status.HTTP_201_CREATED)


class CartItemDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, product_id):
        user_id = request.user.id
        quantity = request.data.get("quantity")
        try:
            quantity = int(quantity)
        except (TypeError, ValueError):
            return Response({"detail": "quantity must be a integer."}, status=status.HTTP_400_BAD_REQUEST)

        if quantity <= 0:
            return Response({"detail": "quantity must be greater than zero."}, status=status.HTTP_400_BAD_REQUEST)

        key = get_cart_key(user_id)
        cart = cache.get(key, {"items":[]})

        for item in cart["items"]:
            if item["product_id"] == product_id:
                item["quantity"] = quantity
                cache.set(key, cart)
                return Response(cart)

        return Response({"detail": "Product is not in cart."}, status=status.HTTP_404_NOT_FOUND)

    def delete(self, request, product_id):
        user_id = request.user.id
        key = get_cart_key(user_id)
        cart = cache.get(key, {"items":[]})

        cart["items"] = [item for item in cart["items"] if item["product_id"] != product_id]
        cache.set(key, cart)
        return Response(cart)


class CartClearView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        user_id = request.user.id
        cache.delete(get_cart_key(user_id))
        return Response({"items":[]})
