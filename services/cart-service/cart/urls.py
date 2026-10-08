from django.urls import path
from . import views


urlpatterns = [
    path("health/", views.HealthCheckView.as_view()),
    path("", views.CartView.as_view()),
    path("items/", views.CartItemView.as_view()),
    path("items/<int:product_id>/", views.CartItemDetailView.as_view()),
    path("clear/", views.CartClearView.as_view()),
]
