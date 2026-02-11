from django.urls import path
from services.settlement import views

urlpatterns = [
    path("health/", views.health),
    path("settlements", views.create_settlement),
    path("settlements/<str:settlement_id>/process", views.process_settlement),
]
