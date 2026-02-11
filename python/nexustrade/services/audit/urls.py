from django.urls import path
from services.audit import views

urlpatterns = [
    path("health/", views.health),
    path("audit", views.create_audit_log),
    path("audit/search", views.search_audit_logs),
]
