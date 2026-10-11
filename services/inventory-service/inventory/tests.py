from types import SimpleNamespace

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from .models import InventoryItem


class InventoryAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.authenticated_client = APIClient()
        self.authenticated_client.force_authenticate(user=SimpleNamespace(id=1, is_authenticated=True))

        self.item = InventoryItem.objects.create(product_id=15, quantity=40)

    def test_health_check(self):
        response = self.client.get("/api/inventory/health/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["service"], "inventory-service")

    def test_inventory_requires_authentication(self):
        response = self.client.get("/api/inventory/items/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_inventory_items(self):
        response = self.authenticated_client.get("/api/inventory/items/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["product_id"], 15)
        self.assertEqual(response.data[0]["quantity"], 40)

    def test_retrieve_by_product_id(self):
        response = self.authenticated_client.get("/api/inventory/items/15/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["product_id"], 15)
        self.assertEqual(response.data["quantity"], 40)
