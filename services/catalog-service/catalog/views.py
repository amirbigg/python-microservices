from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from django.core.cache import cache
from django.db import transaction
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiResponse, OpenApiExample

from .models import Category, Product
from .serializers import CategorySerializer, ProductSerializer
from .messaging.rabbitmq import publish_event


class HealthCheckView(APIView):

    @extend_schema(
        tags=["Catalog"],
        summary="Check Catalog Service Health",
        description="Checks whether the Catalog Service API is responding.",
        responses={
            200: OpenApiResponse(description="The Service is healthy.")
        },
        examples=[
            OpenApiExample(
                "Successful health check",
                value={"service":"", "status":"ok"},
                status_codes=["200"],
            )
        ]
    )
    def get(self, request):
        return Response({
            "service": "catalog-service",
            "status": "ok",
        })


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer


@extend_schema_view(
    list=extend_schema(
        tags=["Catalog - Products"],
        summary="List products",
        description="Returns the list of products. The endpoint uses caching to improve response performance.",
        responses={200: ProductSerializer(many=True)},
        examples=[
            OpenApiExample(
                "Product list response",
                value=[
                    {
                        "id":1,
                        "category": 1,
                        "name": "Sony Z1",
                        "description": "A good phone",
                        "price": 200,
                        "stock": 10,
                        "is_active": True,
                        "created": "2026-01-27T10:00:00",
                        "updated": "2026-02-27T10:00:00",
                    }
                ],
                response_only=True,
                status_codes=["200"]
            )
        ]
    ),
    retrieve=extend_schema(
        tags=["Catalog - Products"],
        summary="Retrieve a product",
        description="Returns a product identified by its ID.",
        responses={
            200: ProductSerializer,
            404: OpenApiResponse(description="The requested product was not found.")
        }
    ),
    create=extend_schema(
        tags=["Catalog - Products"],
        summary="Create a product",
        description=("Creates a product and invalidates the product-list cache."
                    "After a successful database commit, the service publishes a product.created event."),
        request=ProductSerializer,
        responses={
            200: ProductSerializer,
            400: OpenApiResponse(description="Invalid input, missing required fields, or invalid field values.")
        },
        examples=[
            OpenApiExample(
                "Create product request.",
                value={
                    "category": 1,
                    "name": "Sony Z1",
                    "description": "A good phone",
                    "price": 200,
                    "stock": 10,
                    "is_active": True,
                },
                request_only=True
            ),
            OpenApiExample(
                "Created product response",
                value={
                    "id":1,
                    "category": 1,
                    "name": "Sony Z1",
                    "description": "A good phone",
                    "price": 200,
                    "stock": 10,
                    "is_active": True,
                    "created": "2026-01-27T10:00:00",
                    "updated": "2026-02-27T10:00:00",
                },
                response_only=True,
                status_codes=["201"]
            )
        ]
    ),
    update=extend_schema(
        tags=["Catalog - Products"],
        summary="Replace a product",
        description="Replaces the editable fields of an existing product. The request must contain all required fields.",
        request=ProductSerializer,
        responses={
            200: ProductSerializer,
            400: OpenApiResponse(description="The submitted product data is invalid."),
            404: OpenApiResponse(description="The requested product was not found.")
        }
    ),
    partial_update=extend_schema(
        tags=["Catalog - Products"],
        summary="Partially update a product",
        description="Updates only the product fields provided in the request. The product-list cache is invalidated after the update.",
        request=ProductSerializer,
        responses={
            200: ProductSerializer,
            400: OpenApiResponse(description="The submitted product data is invalid."),
            404: OpenApiResponse(description="The requested product was not found.")
        },
        examples=[
            OpenApiExample("Update product stock", value={"stock":13}, request_only=True),
            OpenApiExample("Update product price", value={"price":500}, request_only=True),
        ]
    ),
    destroy=extend_schema(
        tags=["Catalog - Products"],
        summary="Delete a product",
        description="Deletes a product and invalidates the product-list cache.",
        responses={
            204: OpenApiResponse(description="The product was deleted successfully."),
            404: OpenApiResponse(description="The requested product was not found.")
        }
    )
)
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
