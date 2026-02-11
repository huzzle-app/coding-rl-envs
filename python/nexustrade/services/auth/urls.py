"""
Auth service URL configuration.
"""
from django.urls import path
from services.auth import views

urlpatterns = [
    path("health/", views.health),
    path("auth/register", views.register),
    path("auth/login", views.login),
    path("auth/refresh", views.refresh),
    path("auth/logout", views.logout),
    path("auth/service", views.service_auth),
    path("auth/permissions/<str:user_id>", views.check_permission),
    path("auth/api-keys/<str:user_id>/rotate", views.rotate_api_key),
]
