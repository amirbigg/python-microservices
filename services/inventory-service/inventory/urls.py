from django.urls import include, path
from rest_framework.routers import DefaultRouter
from . import views


router = DefaultRouter()
router.register("items", views.InventoryItemViewSet, basename="inventory-item")

urlpatterns = [
    path("health/", views.HealthCheckView.as_view()),
    path("", include(router.urls)),
]