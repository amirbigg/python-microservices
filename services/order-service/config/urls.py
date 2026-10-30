from django.contrib import admin
from django.urls import path, include


urlpatterns = [
    path('admin/', admin.site.urls),
    path("api/orders/", include("orders.urls")),
    path('metrics/', include('django_prometheus.urls')),
]
