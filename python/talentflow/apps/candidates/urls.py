"""
TalentFlow Candidates URLs
"""
from django.urls import path

from . import views

app_name = 'candidates'

urlpatterns = [
    path('', views.CandidateListView.as_view(), name='candidate-list'),
    path('<int:pk>/', views.CandidateDetailView.as_view(), name='candidate-detail'),
    path('<int:candidate_id>/skills/', views.CandidateSkillsView.as_view(), name='candidate-skills'),
    path('<int:candidate_id>/notes/', views.CandidateNotesView.as_view(), name='candidate-notes'),
    path('<int:candidate_id>/status/', views.CandidateStatusView.as_view(), name='candidate-status'),
    path('search/', views.CandidateSearchView.as_view(), name='candidate-search'),
    path('stats/', views.CandidateStatsView.as_view(), name='candidate-stats'),
]
