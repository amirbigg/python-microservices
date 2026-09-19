from rest_framework import status
from rest_framework.test import APITestCase


class UserServiceTest(APITestCase):
    def test_health_check(self):
        response = self.client.get("/api/users/health/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "ok")
