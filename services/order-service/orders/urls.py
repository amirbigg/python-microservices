from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from . import views


urlpatterns = [
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),

    path("health/", views.HealthCheckView.as_view()),
    path("checkout/", views.CheckoutView.as_view()),
    path("", views.OrderListView.as_view()),
    path("<uuid:order_id>/", views.OrderDetailView.as_view()),
]