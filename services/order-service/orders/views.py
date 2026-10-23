from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Order
from .serializers import OrderSerializer
from .services import CheckoutError, checkout


class HealthCheckView(APIView):
    def get(self, request):
        return Response({"service": "order-service", "status": "ok"})


class CheckoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        idempotency_key = request.headers.get("Idempotency-Key", "").strip()

        if not idempotency_key:
            return Response({"detail": "The Idempotency-Key header is required."}, status=status.HTTP_400_BAD_REQUEST)

        if len(idempotency_key) > 128:
            return Response({"detail": "Idempotency-Key cannot exceed 128 characters."}, status=status.HTTP_400_BAD_REQUEST)

        authorization = request.headers.get("Authorization", "")

        try:
            order, created = checkout(customer_id=request.user.id, authorization=authorization, idempotency_key=idempotency_key)
        except CheckoutError as exc:
            return Response({"detail": exc.detail}, status=exc.status_code)

        if not created and order.status == Order.Status.PROCESSING:
            return Response({"detail": "An order with this Idempotency-Key is already being processed.",
                             "order_id":str(order.id)}, status=status.HTTP_409_CONFLICT)

        response_staus = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(OrderSerializer(order).data, status=response_staus)


class OrderListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        orders = Order.objects.filter(customer_id=request.user.id).prefetch_related("items")
        return Response(OrderSerializer(orders, many=True).data)


class OrderDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id):
        order = Order.objects.filter(id=order_id, customer_id=request.user.id).prefetch_related("items").first()

        if order is None:
            return Response({"detail": "Order not found."}, status=status.HTTP_404_NOT_FOUND)

        return Response(OrderSerializer(order).data)
