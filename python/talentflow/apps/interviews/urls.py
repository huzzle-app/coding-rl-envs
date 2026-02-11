"""
TalentFlow Interviews URLs
"""
from django.urls import path

from . import views

app_name = 'interviews'

urlpatterns = [
    path('', views.InterviewListView.as_view(), name='interview-list'),
    path('<int:pk>/', views.InterviewDetailView.as_view(), name='interview-detail'),
    path('<int:interview_id>/status/', views.InterviewStatusView.as_view(), name='interview-status'),
    path('<int:interview_id>/feedback/', views.InterviewFeedbackListView.as_view(), name='interview-feedback'),
    path('availability/', views.InterviewerAvailabilityView.as_view(), name='availability'),
    path('suggestions/', views.ScheduleSuggestionView.as_view(), name='schedule-suggestions'),
    path('schedule/', views.ScheduleInterviewView.as_view(), name='schedule-interview'),
    path('mine/', views.MyInterviewsView.as_view(), name='my-interviews'),
]
