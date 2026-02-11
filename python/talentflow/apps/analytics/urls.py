"""
TalentFlow Analytics URLs
"""
from django.urls import path

from . import views

app_name = 'analytics'

urlpatterns = [
    path('reports/', views.ReportListView.as_view(), name='report-list'),
    path('reports/<int:pk>/', views.ReportDetailView.as_view(), name='report-detail'),
    path('metrics/daily/', views.DailyMetricsView.as_view(), name='daily-metrics'),
    path('funnel/', views.HiringFunnelView.as_view(), name='hiring-funnel'),
    path('sources/', views.SourceEffectivenessView.as_view(), name='source-effectiveness'),
    path('recruiters/', views.RecruiterPerformanceView.as_view(), name='recruiter-performance'),
    path('time-to-hire/', views.TimeToHireView.as_view(), name='time-to-hire'),
    path('cache-stats/', views.CacheStatsView.as_view(), name='cache-stats'),
]
