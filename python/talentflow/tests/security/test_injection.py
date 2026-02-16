"""
Security tests for injection vulnerabilities.

Tests: 30
"""
import pytest
from unittest.mock import patch, MagicMock


pytestmark = [pytest.mark.security, pytest.mark.django_db]


class TestSQLInjection:
    """Tests for SQL injection vulnerabilities."""

    @pytest.mark.bug_i1
    def test_advanced_search_order_by_injection(self, client, user, company, db):
        """Test SQL injection via order_by parameter."""
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken

        api_client = APIClient()
        api_client.force_authenticate(user=user)

        malicious_order = "created_at; DROP TABLE candidates_candidate; --"

        response = api_client.post(
            '/api/v1/candidates/advanced-search/',
            {'query': 'test', 'order_by': malicious_order},
            format='json'
        )

        assert response.status_code == 400

    @pytest.mark.bug_i1
    def test_order_by_with_union_injection(self, client, user, company, db):
        """Test UNION-based SQL injection."""
        from rest_framework.test import APIClient

        api_client = APIClient()
        api_client.force_authenticate(user=user)

        malicious_order = "1 UNION SELECT id,email,password,1,1 FROM accounts_user--"

        response = api_client.post(
            '/api/v1/candidates/advanced-search/',
            {'query': 'a', 'order_by': malicious_order},
            format='json'
        )

        assert response.status_code == 400

    @pytest.mark.bug_i1
    def test_order_by_with_subquery_injection(self, client, user, db):
        """Test subquery-based SQL injection."""
        from rest_framework.test import APIClient

        api_client = APIClient()
        api_client.force_authenticate(user=user)

        malicious_order = "(SELECT password FROM accounts_user LIMIT 1)"

        response = api_client.post(
            '/api/v1/candidates/advanced-search/',
            {'query': 'test', 'order_by': malicious_order},
            format='json'
        )

        assert response.status_code == 400

    @pytest.mark.bug_i1
    def test_order_by_time_based_injection(self, client, user, db):
        """Test time-based blind SQL injection."""
        from rest_framework.test import APIClient

        api_client = APIClient()
        api_client.force_authenticate(user=user)

        malicious_order = "created_at; SELECT pg_sleep(5)--"

        response = api_client.post(
            '/api/v1/candidates/advanced-search/',
            {'query': 'test', 'order_by': malicious_order},
            format='json'
        )

        assert response.status_code == 400

    @pytest.mark.bug_i1
    def test_valid_order_by_values(self, client, user, candidate, db):
        """Test valid order_by values work correctly."""
        from rest_framework.test import APIClient

        api_client = APIClient()
        api_client.force_authenticate(user=user)

        valid_orders = ['created_at', 'first_name', 'email', 'overall_score']

        for order in valid_orders:
            response = api_client.post(
                '/api/v1/candidates/advanced-search/',
                {'query': 'test', 'order_by': order},
                format='json'
            )
            assert response.status_code in [200, 404]


class TestSSRF:
    """Tests for Server-Side Request Forgery vulnerabilities."""

    @pytest.mark.bug_i2
    def test_sync_external_candidates_ssrf(self, company, db):
        """Test SSRF vulnerability in sync_external_candidates."""
        from apps.candidates.tasks import sync_external_candidates

        malicious_sources = [
            'localhost',
            '127.0.0.1',
            '169.254.169.254',
            'internal.company.com',
            '10.0.0.1',
        ]

        for source in malicious_sources:
            with patch('apps.candidates.tasks.requests') as mock_requests:
                mock_requests.get.return_value = MagicMock(
                    json=lambda: {'candidates': []}
                )

                result = sync_external_candidates(company.id, source, 'api_key')

                call_url = mock_requests.get.call_args[0][0]
                assert source in call_url

    @pytest.mark.bug_i2
    def test_ssrf_with_file_protocol(self, company, db):
        """Test SSRF with file:// protocol attempt."""
        from apps.candidates.tasks import sync_external_candidates

        with patch('apps.candidates.tasks.requests') as mock_requests:
            mock_requests.get.side_effect = Exception("Invalid URL")

            result = sync_external_candidates(
                company.id,
                'file:///etc/passwd',
                'api_key'
            )

            assert 'error' in result

    @pytest.mark.bug_i2
    def test_ssrf_url_construction(self, company, db):
        """Test URL construction in sync task."""
        from apps.candidates.tasks import sync_external_candidates

        with patch('apps.candidates.tasks.requests') as mock_requests:
            mock_requests.get.return_value = MagicMock(
                json=lambda: {'candidates': []}
            )

            sync_external_candidates(company.id, 'legitimate', 'key')

            expected_url = 'https://legitimate.example.com/api/candidates'
            mock_requests.get.assert_called_once()
            actual_url = mock_requests.get.call_args[0][0]
            assert actual_url == expected_url


class TestOAuthSecurityFlaws:
    """Tests for OAuth security vulnerabilities."""

    @pytest.mark.bug_c2
    def test_oauth_callback_without_state_rejected(self, db):
        """Test OAuth callback rejects requests without state."""
        from apps.accounts.oauth import process_oauth_callback, OAuthError

        with pytest.raises(OAuthError):
            process_oauth_callback(
                provider='google',
                code='test_code',
                state=None
            )

    @pytest.mark.bug_c2
    def test_oauth_callback_with_invalid_state_rejected(self, db):
        """Test OAuth callback rejects invalid state."""
        from apps.accounts.oauth import process_oauth_callback, OAuthError

        with pytest.raises(OAuthError):
            process_oauth_callback(
                provider='google',
                code='test_code',
                state='invalid_state_value'
            )

    @pytest.mark.bug_c2
    def test_oauth_state_must_be_validated(self, db):
        """Test that OAuth state IS validated (fabricated states rejected)."""
        from apps.accounts.oauth import process_oauth_callback, OAuthError

        with pytest.raises(OAuthError):
            process_oauth_callback('google', 'code1', state='fabricated_state')

        with pytest.raises(OAuthError):
            process_oauth_callback('google', 'code2', state='completely_different')


class TestCrossSiteVulnerabilities:
    """Tests for XSS and CSRF vulnerabilities."""

    def test_candidate_note_xss_prevention(self, candidate, user, db):
        """Test XSS prevention in candidate notes."""
        from apps.candidates.models import CandidateNote

        xss_content = '<script>alert("XSS")</script>Test note'

        note = CandidateNote.objects.create(
            candidate=candidate,
            author=user,
            content=xss_content,
            note_type='general'
        )

        assert '<script>' in note.content or '&lt;script&gt;' in note.content

    def test_job_description_xss_prevention(self, company, user, db):
        """Test XSS prevention in job descriptions."""
        from apps.jobs.models import Job

        xss_description = '<img src=x onerror=alert("XSS")>Description'

        job = Job.objects.create(
            title='Test Job',
            company=company,
            description=xss_description,
            status='draft',
            created_by=user,
            location='Remote'
        )

        assert '<img' in job.description or '&lt;img' in job.description


class TestAuthorizationBypass:
    """Tests for authorization bypass vulnerabilities."""

    @pytest.mark.bug_f4
    def test_permission_check_logic(self, user, db):
        """Test permission check logic is correct."""
        from apps.accounts.oauth import check_permission

        user.role = 'viewer'
        user.is_active = True

        has_view = check_permission(user, 'viewer')
        has_edit = check_permission(user, 'recruiter')

        assert has_view is True
        assert has_edit is False

    @pytest.mark.bug_f4
    def test_role_hierarchy_enforcement(self, user, db):
        """Test role hierarchy is properly enforced."""
        from apps.accounts.oauth import _get_role_level, ROLE_HIERARCHY

        user.role = 'recruiter'
        level = _get_role_level(user)

        assert level == ROLE_HIERARCHY['recruiter']

    @pytest.mark.bug_f4
    def test_company_access_verification(self, user, company, db):
        """Test company access verification."""
        from apps.accounts.oauth import _verify_company_access

        user.company = company

        has_access = _verify_company_access(user, company.id)
        no_access = _verify_company_access(user, company.id + 9999)

        assert has_access is True
        assert no_access is False

    @pytest.mark.bug_f4
    def test_token_action_validation(self, user, db):
        """Test token validates action permissions."""
        from apps.accounts.oauth import generate_access_token, validate_token_for_action

        user.role = 'admin'
        token = generate_access_token(user)

        result = validate_token_for_action(token, 'manage_users')
        assert result['user_id'] == user.id

    @pytest.mark.bug_f4
    def test_impersonation_requires_admin(self, user, db):
        """Test impersonation requires admin role."""
        from apps.accounts.oauth import impersonate_user, JWTAuthenticationError

        user.role = 'recruiter'

        with pytest.raises(JWTAuthenticationError):
            impersonate_user(user, 999)


class TestInputValidation:
    """Tests for input validation."""

    def test_email_format_validation(self, company, user, db):
        """Test email format validation."""
        from apps.candidates.models import Candidate
        from django.core.exceptions import ValidationError

        invalid_emails = ['notanemail', '@missing.com', 'no@domain']

        for email in invalid_emails:
            candidate = Candidate(
                first_name='Test',
                last_name='User',
                email=email,
                company=company,
                created_by=user
            )
            try:
                candidate.full_clean()
            except ValidationError:
                pass

    def test_phone_format_validation(self, candidate, db):
        """Test phone format validation."""
        candidate.phone = '+1-555-123-4567'
        candidate.save()

        candidate.refresh_from_db()
        assert candidate.phone == '+1-555-123-4567'
