from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import InventoryItem, StockReservation
from .serializers import InventoryItemSerializer, ReserveStockRequestSeriazlier, StockReservationSerializer
from .services import InsufficientStock, ReservationConflict, reserve_stock, release_stock, confirm_stock


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


class ReserveStockView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ReserveStockRequestSeriazlier(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            reservation, created = reserve_stock(reservation_id=data["reservation_id"],
                                                 product_id=data["product_id"], quantity=data["quantity"])
        except InventoryItem.DoesNotExist:
            return Response({"detail": "Inventory record does not exist for this product."},
                            status=status.HTTP_404_NOT_FOUND)
        except InsufficientStock as exc:
            return Response({"detail":str(exc)}, status=status.HTTP_409_CONFLICT)
        except ReservationConflict as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

        response_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK

        return Response(StockReservationSerializer(reservation).data, status=response_status)


class ReleaseStockView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, reservation_id):
        try:
            reservation, _ = release_stock(reservation_id)
        except StockReservation.DoesNotExist:
            return Response({"detail": "Reservation not found."}, status=status.HTTP_404_NOT_FOUND)
        except ReservationConflict as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

        return Response(StockReservationSerializer(reservation).data, status=status.HTTP_200_OK)


class ConfirmStockView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, reservation_id):
        try:
            reservation, _ = confirm_stock(reservation_id)
        except StockReservation.DoesNotExist:
            return Response({"detail": "Reservation not found."}, status=status.HTTP_404_NOT_FOUND)
        except ReservationConflict as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

        return Response(StockReservationSerializer(reservation).data, status=status.HTTP_200_OK)
