from types import SimpleNamespace
from uuid import uuid4

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from .models import InventoryItem
from inventory.messaging.catalog_event import process_catalog_event, InvalidCatalogEvent


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

    def test_reserve_stock(self):
        reservation_id = str(uuid4())

        response = self.authenticated_client.post("/api/inventory/reservations/",
                      {"reservation_id":reservation_id, "product_id":15, "quantity":3}, format="json")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], "reserved")

        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 37)

    def test_repeated_reservation_does_not_deduct_stock_twice(self):
        reservation_id = str(uuid4())
        payload = {"reservation_id": reservation_id, "product_id": 15, "quantity": 3}

        first = self.authenticated_client.post("/api/inventory/reservations/", payload, format="json")
        second = self.authenticated_client.post("/api/inventory/reservations/", payload, format="json")

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)

        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 37)

    def test_reservation_fails_when_stock_is_insufficient(self):
        response = self.authenticated_client.post("/api/inventory/reservations/",
                                                  {"reservation_id": str(uuid4()), "product_id": 15, "quantity": 41},
                                                  format="json")

        self.assertEqual(response.status_code, 409)

        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 40)

    def test_release_restores_stock_only_once(self):
        reservation_id = str(uuid4())
        self.authenticated_client.post("/api/inventory/reservations/",
                                          {"reservation_id": reservation_id, "product_id": 15, "quantity": 3},
                                          format="json")

        url = f"/api/inventory/reservations/{reservation_id}/release/"
        first = self.authenticated_client.post(url)
        second = self.authenticated_client.post(url)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.data["status"], "released")

        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 40)

    def test_confirm_keeps_stock_deducted(self):
        reservation_id = str(uuid4())
        self.authenticated_client.post("/api/inventory/reservations/",
                                       {"reservation_id": reservation_id, "product_id": 15, "quantity": 3},
                                       format="json")

        url = f"/api/inventory/reservations/{reservation_id}/confirm/"
        response = self.authenticated_client.post(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "confirmed")

        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 37)

    def test_confirmed_reservation_cannot_be_released(self):
        reservation_id = str(uuid4())
        self.authenticated_client.post("/api/inventory/reservations/",
                                       {"reservation_id": reservation_id, "product_id": 15, "quantity": 3},
                                       format="json")

        self.authenticated_client.post(f"/api/inventory/reservations/{reservation_id}/confirm/")
        response = self.authenticated_client.post(f"/api/inventory/reservations/{reservation_id}/release/")

        self.assertEqual(response.status_code, 409)

        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 37)

    def test_reservation_requires_authentication(self):
        response = self.client.post("/api/inventory/reservations/",
                                       {"reservation_id": str(uuid4()), "product_id": 15, "quantity": 3},
                                       format="json")

        self.assertEqual(response.status_code, 401)


class CatalogEventHandlerTests(TestCase):
    def test_product_creates_inventory_record(self):
        message = {
            "event": "product.created",
            "data": {"id":101, "name":"Test Product", "price":14, "stock": 7}
        }

        item, created = process_catalog_event(message)

        self.assertTrue(created)
        self.assertEqual(item.product_id, 101)
        self.assertEqual(item.quantity, 7)
        self.assertEqual(InventoryItem.objects.filter(product_id=101).count(), 1)

    def test_duplicate_event_does_not_reset_inventory(self):
        InventoryItem.objects.create(product_id=102, quantity=3)

        message = {
            "event": "product.created",
            "data": {"id": 102, "name": "Test Product", "price": 14, "stock": 20}
        }

        item, created = process_catalog_event(message)

        self.assertFalse(created)
        self.assertEqual(item.quantity, 3)
        self.assertEqual(InventoryItem.objects.filter(product_id=102).count(), 1)

    def test_invalid_event_type_is_rejected(self):
        message = {
            "event": "product.updated",
            "data": {"id": 102, "name": "Test Product", "price": 14, "stock": 20}
        }

        with self.assertRaises(InvalidCatalogEvent):
            process_catalog_event(message)

    def test_invalid_product_id_is_rejected(self):
        invalid_messages = [
            {"event": "product.created", "data": {"id": "103", "stock": 20}},
            {"event": "product.created", "data": {"id": 0, "stock": 20}},
        ]

        for message in invalid_messages:
            with self.subTest(message=message):
                with self.assertRaises(InvalidCatalogEvent):
                    process_catalog_event(message)

    def test_negative_stock_is_rejected(self):
        invalid_messages = {
            "event": "product.created", "data": {"id": "103", "stock": -1}
         }

        with self.assertRaises(InvalidCatalogEvent):
            process_catalog_event(invalid_messages)

    def test_missing_stock_is_rejected(self):
        invalid_messages = {
            "event": "product.created", "data": {"id": "103"}
        }

        with self.assertRaises(InvalidCatalogEvent):
            process_catalog_event(invalid_messages)
