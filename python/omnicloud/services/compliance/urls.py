"""
URL configuration for OmniCloud compliance service.
"""
from django.urls import path
from services.compliance import views

urlpatterns = [
    path('health/', views.health_check),
    path('api/v1/', views.api_root),
]
