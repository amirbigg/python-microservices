from django.urls import include, path
from rest_framework.routers import DefaultRouter
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from . import views


router = DefaultRouter()
router.register("items", views.InventoryItemViewSet, basename="inventory-item")

urlpatterns = [
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),

    path("health/", views.HealthCheckView.as_view()),
    path("reservations/", views.ReserveStockView.as_view()),
    path("reservations/<uuid:reservation_id>/release/", views.ReleaseStockView.as_view()),
    path("reservations/<uuid:reservation_id>/confirm/", views.ConfirmStockView.as_view()),
    path("", include(router.urls)),
]