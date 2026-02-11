"""
TalentFlow Accounts Views
"""
from django.contrib.auth import authenticate
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import User
from .oauth import (
    JWTAuthenticationError,
    OAuthError,
    generate_access_token,
    generate_oauth_state,
    generate_refresh_token,
    process_oauth_callback,
    refresh_access_token,
    revoke_all_tokens,
)
from .serializers import (
    LoginSerializer,
    RefreshTokenSerializer,
    TokenSerializer,
    UserCreateSerializer,
    UserSerializer,
)


class RegisterView(generics.CreateAPIView):
    """Register a new user."""
    queryset = User.objects.all()
    serializer_class = UserCreateSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Generate tokens
        access_token = generate_access_token(user)
        refresh_token = generate_refresh_token(user)

        return Response({
            'user': UserSerializer(user).data,
            'tokens': {
                'access_token': access_token,
                'refresh_token': refresh_token.token,
            }
        }, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    """Authenticate and get tokens."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = authenticate(
            email=serializer.validated_data['email'],
            password=serializer.validated_data['password']
        )

        if not user:
            return Response(
                {'error': 'Invalid credentials'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        access_token = generate_access_token(user)
        refresh_token = generate_refresh_token(user)

        return Response({
            'user': UserSerializer(user).data,
            'tokens': {
                'access_token': access_token,
                'refresh_token': refresh_token.token,
            }
        })


class RefreshTokenView(APIView):
    """Refresh access token using refresh token."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RefreshTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            tokens = refresh_access_token(
                serializer.validated_data['refresh_token']
            )
            return Response(tokens)
        except JWTAuthenticationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_401_UNAUTHORIZED
            )


class LogoutView(APIView):
    """Revoke all tokens for the current user."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        count = revoke_all_tokens(request.user)
        return Response({
            'message': f'Revoked {count} tokens'
        })


class MeView(generics.RetrieveUpdateAPIView):
    """Get or update current user profile."""
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class OAuthInitView(APIView):
    """Initialize OAuth flow."""
    permission_classes = [AllowAny]

    def get(self, request):
        provider = request.query_params.get('provider', 'google')
        redirect_uri = request.query_params.get(
            'redirect_uri',
            request.build_absolute_uri('/oauth/callback')
        )

        state = generate_oauth_state(provider, redirect_uri)

        # Build authorization URL (simplified)
        auth_urls = {
            'google': 'https://accounts.google.com/o/oauth2/v2/auth',
            'github': 'https://github.com/login/oauth/authorize',
        }

        auth_url = auth_urls.get(provider, auth_urls['google'])

        return Response({
            'authorization_url': f'{auth_url}?state={state}&redirect_uri={redirect_uri}',
            'state': state,
        })


class OAuthCallbackView(APIView):
    """Handle OAuth callback."""
    permission_classes = [AllowAny]

    def get(self, request):
        code = request.query_params.get('code')
        state = request.query_params.get('state')
        error = request.query_params.get('error')

        if error:
            return Response(
                {'error': error},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not code:
            return Response(
                {'error': 'Missing authorization code'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            result = process_oauth_callback(
                provider=request.query_params.get('provider', 'google'),
                code=code,
                state=state,
            )
            return Response(result)
        except OAuthError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class UserListView(generics.ListAPIView):
    """List users in the same company."""
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.company:
            return User.objects.filter(company=user.company)
        return User.objects.none()
