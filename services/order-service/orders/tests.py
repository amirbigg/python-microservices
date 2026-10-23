from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from .models import Order


class OrderAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=SimpleNamespace(id=7, is_authenticated=True))
        self.cart_data = {"items":[{"product_id": 15, "quantity": 2}]}
        self.product_data = {"id": 15, "name": "Test product", "price": 25, "is_active": True}

    def test_health_check(self):
        response = self.client.get("/api/orders/health/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["service"], "order-service")

    def test_checkout_requires_idempotency_key(self):
        response = self.client.post("/api/orders/checkout/", {}, format="json")

        self.assertEqual(response.status_code, 400)

    @patch("orders.services.clear_cart")
    @patch("orders.services.reserve_stock")
    @patch("orders.services.get_product")
    @patch("orders.services.get_cart")
    def test_checkout_creates_order_and_reserves_stock(self, mock_get_cart, mock_get_product,
                                                       mock_reserve_stock, mock_clear_cart):

        mock_get_cart.return_value = self.cart_data
        mock_get_product.return_value = self.product_data
        mock_reserve_stock.return_value = {"status": "reserved"}

        response = self.client.post("/api/orders/checkout/", {}, format="json",
                                    HTTP_IDEMPOTENCY_KEY="checkout-test-001", HTTP_AUTHORIZATION="Bearer test-token")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], Order.Status.AWAITING_PAYMENT)
        self.assertEqual(response.data["total_amount"], 50)
        self.assertEqual(len(response.data["items"]), 1)

        mock_get_cart.assert_called_once()
        mock_get_product.assert_called_once_with(15, "Bearer test-token")
        mock_reserve_stock.assert_called_once()
        mock_clear_cart.assert_called_once()

    @patch("orders.services.clear_cart")
    @patch("orders.services.reserve_stock")
    @patch("orders.services.get_product")
    @patch("orders.services.get_cart")
    def test_repeating_same_idempotency_key_does_not_create_order(self, mock_get_cart, mock_get_product,
                                                                  mock_reserve_stock, mock_clear_cart):

        mock_get_cart.return_value = self.cart_data
        mock_get_product.return_value = self.product_data

        first = self.client.post("/api/orders/checkout/", {}, format="json",
                                    HTTP_IDEMPOTENCY_KEY="checkout-test-002", HTTP_AUTHORIZATION="Bearer test-token")

        second = self.client.post("/api/orders/checkout/", {}, format="json",
                                 HTTP_IDEMPOTENCY_KEY="checkout-test-002", HTTP_AUTHORIZATION="Bearer test-token")

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.data["id"], second.data["id"])
        self.assertEqual(Order.objects.count(), 1)

        mock_reserve_stock.assert_called_once()

    @patch("orders.services.release_stock")
    @patch("orders.services.reserve_stock")
    @patch("orders.services.get_product")
    @patch("orders.services.get_cart")
    def test_insufficient_stock_marks_order_failed(self, mock_get_cart, mock_get_product,
                                                   mock_reserve_stock, mock_release_stock):

        from orders.clients.common import InventoryReservationRejected

        mock_get_cart.return_value = self.cart_data
        mock_get_product.return_value = self.product_data
        mock_reserve_stock.side_effect = InventoryReservationRejected("Not enough available stock.")

        response = self.client.post("/api/orders/checkout/", {}, format="json",
                                    HTTP_IDEMPOTENCY_KEY="checkout-test-003", HTTP_AUTHORIZATION="Bearer test-token")

        self.assertEqual(response.status_code, 409)

        order = Order.objects.get(idempotency_key="checkout-test-003")
        self.assertEqual(order.status, Order.Status.FAILED)

        mock_release_stock.assert_called_once()

    def test_user_cannot_view_another_users_order(self):
        order = Order.objects.create(customer_id=99, idempotency_key="other-user-order",
                                     status=Order.Status.AWAITING_PAYMENT, total_amount=25)

        response = self.client.get(f"/api/orders/{order.id}/")

        self.assertEqual(response.status_code, 404)
