from django.contrib import admin
from django.urls import path, include


urlpatterns = [
    path('metrics', include('django_prometheus.urls')),
    path('admin/', admin.site.urls),
    path('api/users/', include("users.urls")),
]
