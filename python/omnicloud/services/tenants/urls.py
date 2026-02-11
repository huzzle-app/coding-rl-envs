"""
URL configuration for OmniCloud tenants service.
"""
from django.urls import path
from services.tenants import views

urlpatterns = [
    path('health/', views.health_check),
    path('api/v1/', views.api_root),
]
