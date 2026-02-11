"""
TalentFlow URL Configuration
"""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),

    # OAuth2 Provider URLs
    path('oauth/', include('oauth2_provider.urls', namespace='oauth2_provider')),

    # API URLs
    path('api/v1/accounts/', include('apps.accounts.urls', namespace='accounts')),
    path('api/v1/candidates/', include('apps.candidates.urls', namespace='candidates')),
    path('api/v1/jobs/', include('apps.jobs.urls', namespace='jobs')),
    path('api/v1/interviews/', include('apps.interviews.urls', namespace='interviews')),
    path('api/v1/analytics/', include('apps.analytics.urls', namespace='analytics')),
]
