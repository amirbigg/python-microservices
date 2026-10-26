from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from . import views


urlpatterns = [
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),

    path("health/", views.HealthCheckView.as_view()),
    path("", views.CartView.as_view()),
    path("items/", views.CartItemView.as_view()),
    path("items/<int:product_id>/", views.CartItemDetailView.as_view()),
    path("clear/", views.CartClearView.as_view()),
]
