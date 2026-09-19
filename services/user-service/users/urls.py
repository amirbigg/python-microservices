from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView

from . import views


urlpatterns = [
    path("health/", views.HealthCheckView.as_view()),
    path("register/", views.RegisterView.as_view()),
    path("login/", TokenObtainPairView.as_view()),
    path("me/", views.MeView.as_view()),
]