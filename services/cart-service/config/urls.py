from django.contrib import admin
from django.urls import path, include


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/cart/', include("cart.urls")),
    path('metrics/', include('django_prometheus.urls')),
]
