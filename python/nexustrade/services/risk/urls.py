"""Risk service URL configuration."""
from django.urls import path
from services.risk import views

urlpatterns = [
    path("health/", views.health),
    path("risk/check-order", views.check_order_risk),
    path("risk/exposure/<str:user_id>", views.get_exposure),
    path("risk/margin/<str:user_id>", views.get_margin_status),
    path("risk/var/<str:user_id>", views.calculate_var),
]
