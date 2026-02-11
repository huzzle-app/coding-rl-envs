"""
URL configuration for OmniCloud auth service.
"""
from django.urls import path
from services.auth import views

urlpatterns = [
    path('health/', views.health_check),
    path('api/v1/', views.api_root),
]
