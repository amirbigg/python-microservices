from django.contrib import admin
from django.urls import path, include


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/inventory/', include("inventory.urls")),
    path('metrics/', include('django_prometheus.urls')),
]
