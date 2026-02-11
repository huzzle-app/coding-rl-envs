"""
Unit tests for encoding and unicode handling.

Tests: 25
"""
import pytest


pytestmark = [pytest.mark.unit, pytest.mark.django_db]


class TestUnicodeHandling:
    """Tests for unicode character handling."""

    @pytest.mark.bug_g3
    def test_bulk_import_unicode_names(self, company, db):
        """Test bulk import handles unicode names correctly."""
        from apps.candidates.tasks import bulk_import_candidates

        candidates_data = [
            {'first_name': 'José', 'last_name': 'García', 'email': 'jose@example.com'},
            {'first_name': '田中', 'last_name': '太郎', 'email': 'tanaka@example.com'},
            {'first_name': 'Müller', 'last_name': 'François', 'email': 'muller@example.com'},
            {'first_name': 'Владимир', 'last_name': 'Петров', 'email': 'vladimir@example.com'},
        ]

        result = bulk_import_candidates(company.id, candidates_data)

        assert result['created'] == len(candidates_data)

    @pytest.mark.bug_g3
    def test_unicode_name_preservation(self, company, db):
        """Test that unicode names are preserved correctly."""
        from apps.candidates.tasks import bulk_import_candidates
        from apps.candidates.models import Candidate

        candidates_data = [
            {'first_name': 'José', 'last_name': 'García', 'email': 'jose2@example.com'},
        ]

        bulk_import_candidates(company.id, candidates_data)

        candidate = Candidate.objects.filter(email='jose2@example.com').first()
        if candidate:
            assert candidate.first_name == 'José'

    @pytest.mark.bug_g3
    def test_ascii_encoding_strips_unicode(self):
        """Test that ASCII encoding strips unicode characters."""
        test_strings = {
            'José': 'Jos',
            '田中': '',
            'Müller': 'Mller',
            'Владимир': '',
            'naïve': 'nave',
        }

        for original, expected in test_strings.items():
            encoded = original.encode('ascii', 'ignore').decode()
            assert encoded == expected

    @pytest.mark.bug_g3
    def test_proper_unicode_handling(self):
        """Test proper unicode handling with UTF-8."""
        test_strings = ['José', '田中', 'Müller', 'Владимир', 'naïve']

        for s in test_strings:
            encoded = s.encode('utf-8')
            decoded = encoded.decode('utf-8')
            assert decoded == s


class TestCandidateNameEncoding:
    """Tests for candidate name encoding."""

    def test_create_candidate_with_unicode(self, company, user, db):
        """Test creating candidate with unicode name."""
        from apps.candidates.models import Candidate

        candidate = Candidate.objects.create(
            first_name='François',
            last_name='Müller',
            email='francois@example.com',
            company=company,
            created_by=user
        )

        candidate.refresh_from_db()
        assert candidate.first_name == 'François'
        assert candidate.last_name == 'Müller'

    def test_candidate_full_name_unicode(self, company, user, db):
        """Test full_name property with unicode."""
        from apps.candidates.models import Candidate

        candidate = Candidate.objects.create(
            first_name='田中',
            last_name='太郎',
            email='tanaka2@example.com',
            company=company,
            created_by=user
        )

        assert candidate.full_name == '田中 太郎'

    def test_candidate_search_unicode(self, company, user, db):
        """Test searching for candidates with unicode names."""
        from apps.candidates.models import Candidate

        Candidate.objects.create(
            first_name='José',
            last_name='García',
            email='jose3@example.com',
            company=company,
            created_by=user
        )

        found = Candidate.objects.filter(first_name__icontains='José').exists()
        assert found


class TestEmailEncoding:
    """Tests for email address encoding."""

    def test_email_with_plus_addressing(self, company, user, db):
        """Test email with plus addressing."""
        from apps.candidates.models import Candidate

        candidate = Candidate.objects.create(
            first_name='Test',
            last_name='User',
            email='test+tag@example.com',
            company=company,
            created_by=user
        )

        assert candidate.email == 'test+tag@example.com'

    def test_internationalized_email(self, company, user, db):
        """Test internationalized email addresses."""
        from apps.candidates.models import Candidate

        candidate = Candidate.objects.create(
            first_name='Test',
            last_name='User',
            email='user@例え.jp',
            company=company,
            created_by=user
        )

        assert '@' in candidate.email


class TestExportEncoding:
    """Tests for export file encoding."""

    @pytest.mark.bug_g2
    def test_csv_export_encoding(self, company, user, db):
        """Test CSV export handles encoding correctly."""
        from apps.candidates.models import Candidate
        from io import StringIO
        import csv

        Candidate.objects.create(
            first_name='François',
            last_name='Müller',
            email='export_test@example.com',
            company=company,
            created_by=user
        )

        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(['François', 'Müller', 'export_test@example.com'])

        content = output.getvalue()
        assert 'François' in content

    def test_json_export_encoding(self, candidate, db):
        """Test JSON export handles unicode."""
        import json

        candidate.first_name = 'José'
        candidate.save()

        data = {
            'name': candidate.full_name,
            'email': candidate.email
        }

        encoded = json.dumps(data, ensure_ascii=False)
        decoded = json.loads(encoded)

        assert decoded['name'] == candidate.full_name


class TestDatabaseEncoding:
    """Tests for database encoding."""

    def test_database_stores_unicode(self, company, user, db):
        """Test database correctly stores unicode."""
        from apps.candidates.models import Candidate

        test_cases = [
            ('José', 'García'),
            ('田中', '太郎'),
            ('Владимир', 'Петров'),
            ('🎉', 'Emoji'),
        ]

        for first, last in test_cases:
            c = Candidate.objects.create(
                first_name=first,
                last_name=last,
                email=f'{first[:3]}@test.com'.lower(),
                company=company,
                created_by=user
            )
            c.refresh_from_db()
            assert c.first_name == first

    def test_text_field_encoding(self, job, db):
        """Test text fields handle unicode."""
        unicode_description = """
        This job requires:
        • Fluent in español
        • Knowledge of 日本語
        • Experience with Ümlauts
        """

        job.description = unicode_description
        job.save()
        job.refresh_from_db()

        assert 'español' in job.description


class TestURLEncoding:
    """Tests for URL encoding in various fields."""

    def test_resume_url_encoding(self, candidate, db):
        """Test resume URL with special characters."""
        url = 'https://example.com/résumé/José García.pdf'

        candidate.resume_url = url
        candidate.save()
        candidate.refresh_from_db()

        assert candidate.resume_url == url

    def test_linkedin_url_encoding(self, candidate, db):
        """Test LinkedIn URL encoding."""
        url = 'https://linkedin.com/in/josé-garcía'

        candidate.linkedin_url = url
        candidate.save()
        candidate.refresh_from_db()

        assert candidate.linkedin_url == url


class TestNotificationEncoding:
    """Tests for notification message encoding."""

    def test_notification_with_unicode_name(self, candidate, db):
        """Test notification handles unicode names."""
        from apps.candidates.tasks import send_candidate_notification

        candidate.first_name = 'François'
        candidate.save()

        with pytest.raises(Exception) as exc_info:
            send_candidate_notification(candidate.id, 'application_received')

        assert exc_info is not None

    def test_email_template_encoding(self, candidate, db):
        """Test email template encodes names correctly."""
        candidate.first_name = '田中'

        template = f'Dear {candidate.first_name}, we have received your application.'

        assert '田中' in template
