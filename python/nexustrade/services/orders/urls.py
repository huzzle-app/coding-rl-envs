"""
Orders service URL configuration.
"""
from django.urls import path
from services.orders import views

urlpatterns = [
    path("health/", views.health),
    path("orders", views.create_order),
    path("orders", views.list_orders),
    path("orders/<str:order_id>", views.get_order),
    path("orders/<str:order_id>/cancel", views.cancel_order),
    path("orders/<str:order_id>/fill", views.fill_order),
]
