"""
URL configuration for OmniCloud network service.
"""
from django.urls import path
from services.network import views

urlpatterns = [
    path('health/', views.health_check),
    path('api/v1/', views.api_root),
]
