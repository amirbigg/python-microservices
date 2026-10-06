from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from django.core.cache import cache
from django.db import transaction

from .models import Category, Product
from .serializers import CategorySerializer, ProductSerializer
from .messaging.rabbitmq import publish_event


class HealthCheckView(APIView):
    def get(self, request):
        return Response({
            "service": "catalog-service",
            "status": "ok",
        })


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.select_related("category").all()
    serializer_class = ProductSerializer

    def list(self, request, *args, **kwargs):
        cache_key = "product-list"

        cached_data = cache.get(cache_key)

        if cached_data is not None:
            return Response(cached_data)

        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)

        cache.set(cache_key, serializer.data)

        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        cache.delete("product-list")

        if response.status_code == 201:
            product_id = response.data["id"]

            def publish_product_created():
                product = Product.objects.get(pk=product_id)

                publish_event("product.created", {
                    "id": product.id,
                    "name": product.name,
                    "price": str(product.price),
                    "stock": product.stock
                })

            transaction.on_commit(publish_product_created)
        return response

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        cache.delete("product-list")
        return response

    def partial_update(self, request, *args, **kwargs):
        response = super().partial_update(request, *args, **kwargs)
        cache.delete("product-list")
        return response

    def destroy(self, request, *args, **kwargs):
        response = super().destroy(request, *args, **kwargs)
        cache.delete("product-list")
        return response
