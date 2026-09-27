from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Category, Product


class CatalogAPITests(APITestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Mobile", slug="mobile")
        self.product = Product.objects.create(
            category=self.category,
            name="Sony x1",
            description="a good phone",
            price=100,
            stock=10,
            is_active=True
        )

    def test_category_list(self):
        url = reverse("category-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_category_detail(self):
        url = reverse("category-detail", kwargs={"pk": self.category.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Mobile")

    def test_product_list(self):
        url = reverse("product-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_product_detail(self):
        url = reverse("product-detail", kwargs={"pk": self.product.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Sony x1")

    def test_create_category(self):
        url = reverse("category-list")
        data = {"name":"Laptop", "slug":"laptop"}
        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Category.objects.count(), 2)

    def test_create_product(self):
        url = reverse("product-list")
        data = {
            "category": self.category.id,
            "name": "Iphone 10",
            "description": "nice phone",
            "price": 200,
            "stock": 9,
            "is_active": True
        }
        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Product.objects.count(), 2)
