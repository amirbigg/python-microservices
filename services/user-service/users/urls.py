from django.urls import path
from . import views


urlpatterns = [
    path("health/", views.HealthCheckView.as_view()),
]