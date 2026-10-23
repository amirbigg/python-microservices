from django.urls import path

from . import views


urlpatterns = [
    path("health/", views.HealthCheckView.as_view()),
    path("checkout/", views.CheckoutView.as_view()),
    path("", views.OrderListView.as_view()),
    path("<uuid:order_id>/", views.OrderDetailView.as_view()),
]