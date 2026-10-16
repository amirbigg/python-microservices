from django.urls import include, path
from rest_framework.routers import DefaultRouter
from . import views


router = DefaultRouter()
router.register("items", views.InventoryItemViewSet, basename="inventory-item")

urlpatterns = [
    path("health/", views.HealthCheckView.as_view()),
    path("reservations/", views.ReserveStockView.as_view()),
    path("reservations/<uuid:reservation_id>/release/", views.ReserveStockView.as_view()),
    path("reservations/<uuid:reservation_id>/confirm/", views.ConfirmStockView.as_view()),
    path("", include(router.urls)),
]