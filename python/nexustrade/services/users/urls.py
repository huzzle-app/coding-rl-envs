from django.urls import path
from services.users import views

urlpatterns = [
    path("health/", views.health),
    path("users/<str:user_id>", views.get_profile),
    path("users/<str:user_id>/update", views.update_profile),
    path("users/<str:user_id>/bank-accounts", views.get_bank_accounts),
]
