"""
URL configuration for OmniCloud audit service.
"""
from django.urls import path
from services.audit import views

urlpatterns = [
    path('health/', views.health_check),
    path('api/v1/', views.api_root),
]
