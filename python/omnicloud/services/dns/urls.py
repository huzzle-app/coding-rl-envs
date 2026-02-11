"""
URL configuration for OmniCloud dns service.
"""
from django.urls import path
from services.dns import views

urlpatterns = [
    path('health/', views.health_check),
    path('api/v1/', views.api_root),
]
