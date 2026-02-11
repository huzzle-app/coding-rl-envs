"""
Integration tests for API endpoints.

Tests: 10
"""
import pytest
from django.urls import reverse
from rest_framework import status


pytestmark = [pytest.mark.integration, pytest.mark.django_db]


class TestAccountsAPI:
    """Tests for accounts API endpoints."""

    def test_register_user(self, api_client, company):
        """Test user registration."""
        data = {
            'email': 'newuser@example.com',
            'password': 'securepass123',
            'confirm_password': 'securepass123',
            'first_name': 'New',
            'last_name': 'User',
        }
        response = api_client.post('/api/v1/accounts/register/', data)

        assert response.status_code == status.HTTP_201_CREATED
        assert 'tokens' in response.data
        assert 'access_token' in response.data['tokens']

    def test_login_user(self, api_client, user):
        """Test user login."""
        data = {
            'email': user.email,
            'password': 'testpass123',
        }
        response = api_client.post('/api/v1/accounts/login/', data)

        assert response.status_code == status.HTTP_200_OK
        assert 'tokens' in response.data

    def test_refresh_token(self, api_client, refresh_token):
        """Test token refresh."""
        data = {'refresh_token': refresh_token.token}
        response = api_client.post('/api/v1/accounts/token/refresh/', data)

        assert response.status_code == status.HTTP_200_OK
        assert 'access_token' in response.data

    def test_get_current_user(self, authenticated_client, user):
        """Test getting current user profile."""
        response = authenticated_client.get('/api/v1/accounts/me/')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['email'] == user.email


class TestCandidatesAPI:
    """Tests for candidates API endpoints."""

    def test_list_candidates(self, authenticated_client, candidates):
        """Test listing candidates."""
        response = authenticated_client.get('/api/v1/candidates/')

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) > 0

    def test_create_candidate(self, authenticated_client, company):
        """Test creating a candidate."""
        data = {
            'first_name': 'New',
            'last_name': 'Candidate',
            'email': 'new.candidate@example.com',
            'title': 'Developer',
            'years_experience': 3,
        }
        response = authenticated_client.post('/api/v1/candidates/', data)

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['email'] == data['email']

    def test_get_candidate_detail(self, authenticated_client, candidate):
        """Test getting candidate detail."""
        response = authenticated_client.get(f'/api/v1/candidates/{candidate.id}/')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == candidate.id


class TestJobsAPI:
    """Tests for jobs API endpoints."""

    def test_list_jobs(self, authenticated_client, jobs):
        """Test listing jobs."""
        response = authenticated_client.get('/api/v1/jobs/')

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) > 0

    def test_create_job(self, authenticated_client, company, skills):
        """Test creating a job."""
        data = {
            'title': 'New Job',
            'description': 'Job description',
            'location': 'Remote',
            'employment_type': 'full_time',
            'experience_level': 'mid',
            'required_skill_ids': [skills[0].id],
        }
        response = authenticated_client.post('/api/v1/jobs/', data, format='json')

        assert response.status_code == status.HTTP_201_CREATED

    def test_get_job_candidates(self, authenticated_client, job, candidates):
        """Test getting ranked candidates for a job."""
        response = authenticated_client.get(f'/api/v1/jobs/{job.id}/candidates/')

        assert response.status_code == status.HTTP_200_OK
        assert 'candidates' in response.data
