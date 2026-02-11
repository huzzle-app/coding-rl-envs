"""
URL configuration for OmniCloud config service.
"""
from django.urls import path
from services.config import views

urlpatterns = [
    path('health/', views.health_check),
    path('api/v1/', views.api_root),
]
