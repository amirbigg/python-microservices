from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient


class CartAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user_id = "10"

        cache.clear()

        self.product = {"id":1, "name": "sony", "price": 50, "stock": 10, "is_active":True}

    def tearDown(self):
        cache.clear()

    def test_health_check(self):
        response = self.client.get("/api/cart/health/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["service"], "cart-service")

    def test_cart_requires_user_id(self):
        response = self.client.get("/api/cart/")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_empty_cart(self):
        response = self.client.get("/api/cart/", HTTP_X_USER_ID=self.user_id)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"items":[]})

    @patch("cart.views.get_product")
    def test_add_valid_product(self, mock_get_product):
        mock_get_product.return_value = self.product

        response = self.client.post("/api/cart/items/", {"product_id": 1, "quantity":2},
                                    format="json", HTTP_X_USER_ID=self.user_id)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["items"], [{"product_id":1, "quantity":2}])
        mock_get_product.assert_called_once_with(1)

    @patch("cart.views.get_product")
    def test_add_non_existing_product(self, mock_get_product):
        mock_get_product.return_value = None

        response = self.client.post("/api/cart/items/", {"product_id": 999, "quantity": 2},
                                    format="json", HTTP_X_USER_ID=self.user_id)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["detail"], "Product does not exist.")

    @patch("cart.views.get_product")
    def test_add_inactive_product(self, mock_get_product):
        mock_get_product.return_value = {**self.product, "is_active": False}

        response = self.client.post("/api/cart/items/", {"product_id": 1, "quantity": 2},
                                    format="json", HTTP_X_USER_ID=self.user_id)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["detail"], "Product is not active.")

    def test_invalid_quantity(self):
        response = self.client.post("/api/cart/items/", {"product_id": 1, "quantity": 0},
                                    format="json", HTTP_X_USER_ID=self.user_id)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_non_integer_quantity(self):
        response = self.client.post("/api/cart/items/", {"product_id": 1, "quantity": "abc"},
                                    format="json", HTTP_X_USER_ID=self.user_id)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("cart.views.get_product")
    def test_add_same_product_twice(self, mock_get_product):
        mock_get_product.return_value = self.product

        self.client.post("/api/cart/items/", {"product_id": 1, "quantity": 2},
                                    format="json", HTTP_X_USER_ID=self.user_id)

        response = self.client.post("/api/cart/items/", {"product_id": 1, "quantity": 3},
                                    format="json", HTTP_X_USER_ID=self.user_id)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["items"][0]["quantity"], 5)

    @patch("cart.views.get_product")
    def test_update_cart_item(self, mock_get_product):
        mock_get_product.return_value = self.product

        self.client.post("/api/cart/items/", {"product_id": 1, "quantity": 2},
                         format="json", HTTP_X_USER_ID=self.user_id)

        response = self.client.patch("/api/cart/items/1/", {"quantity": 7},
                         format="json", HTTP_X_USER_ID=self.user_id)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["items"][0]["quantity"], 7)

    @patch("cart.views.get_product")
    def test_remove_cart_item(self, mock_get_product):
        mock_get_product.return_value = self.product

        self.client.post("/api/cart/items/", {"product_id": 1, "quantity": 2},
                         format="json", HTTP_X_USER_ID=self.user_id)

        response = self.client.delete("/api/cart/items/1/", HTTP_X_USER_ID=self.user_id)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"items":[]})

    @patch("cart.views.get_product")
    def test_clear_cart(self, mock_get_product):
        mock_get_product.return_value = self.product

        self.client.post("/api/cart/items/", {"product_id": 1, "quantity": 2},
                         format="json", HTTP_X_USER_ID=self.user_id)

        response = self.client.delete("/api/cart/clear/", HTTP_X_USER_ID=self.user_id)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"items": []})

    @patch("cart.views.get_product")
    def test_catalog_service_unavailable(self, mock_get_product):
        from cart.clients.catalog import CatalogServiceError

        mock_get_product.side_effect = CatalogServiceError("Catalog service is unavailable.")

        response = self.client.post("/api/cart/items/", {"product_id": 1, "quantity": 2},
                         format="json", HTTP_X_USER_ID=self.user_id)

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.data["detail"], "Catalog service is unavailable.")
