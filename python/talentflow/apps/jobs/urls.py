"""
TalentFlow Jobs URLs
"""
from django.urls import path

from . import views

app_name = 'jobs'

urlpatterns = [
    # Jobs
    path('', views.JobListView.as_view(), name='job-list'),
    path('<int:pk>/', views.JobDetailView.as_view(), name='job-detail'),
    path('<int:job_id>/publish/', views.JobPublishView.as_view(), name='job-publish'),
    path('<int:job_id>/close/', views.JobCloseView.as_view(), name='job-close'),
    path('<int:job_id>/candidates/', views.JobCandidatesView.as_view(), name='job-candidates'),

    # Applications
    path('<int:job_id>/applications/', views.ApplicationListView.as_view(), name='application-list'),
    path('applications/<int:pk>/', views.ApplicationDetailView.as_view(), name='application-detail'),
    path('applications/<int:application_id>/status/', views.ApplicationStatusView.as_view(), name='application-status'),
    path('applications/<int:application_id>/notes/', views.ApplicationNotesView.as_view(), name='application-notes'),
    path('apply/<int:candidate_id>/', views.ApplicationCreateView.as_view(), name='application-create'),
]
