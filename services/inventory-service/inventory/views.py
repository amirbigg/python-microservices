from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import InventoryItem
from .serializers import InventoryItemSerializer


class HealthCheckView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"service":"inventory-service", "status":"ok"})


class InventoryItemViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]

    queryset = InventoryItem.objects.all()
    serializer_class = InventoryItemSerializer

    lookup_field = "product_id"
    lookup_value_regex = r"\d+"
