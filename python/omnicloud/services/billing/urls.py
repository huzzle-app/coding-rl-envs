"""
URL configuration for OmniCloud billing service.
"""
from django.urls import path
from services.billing import views

urlpatterns = [
    path('health/', views.health_check),
    path('api/v1/', views.api_root),
]
