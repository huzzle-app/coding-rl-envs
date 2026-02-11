"""
TalentFlow Accounts URLs
"""
from django.urls import path

from . import views

app_name = 'accounts'

urlpatterns = [
    # Authentication
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('token/refresh/', views.RefreshTokenView.as_view(), name='token-refresh'),

    # OAuth
    path('oauth/init/', views.OAuthInitView.as_view(), name='oauth-init'),
    path('oauth/callback/', views.OAuthCallbackView.as_view(), name='oauth-callback'),

    # Profile
    path('me/', views.MeView.as_view(), name='me'),
    path('users/', views.UserListView.as_view(), name='user-list'),
]
