"""
Unit tests for analytics app.

Tests: 5
"""
import pytest


pytestmark = [pytest.mark.unit, pytest.mark.django_db]


class TestReportModel:
    """Tests for Report model."""

    def test_create_report(self, company, user):
        """Test creating a report."""
        from apps.analytics.models import Report

        report = Report.objects.create(
            company=company,
            report_type='hiring_funnel',
            name='Test Report',
            created_by=user,
        )
        assert report.status == 'pending'
        assert str(report) == f'{report.name} ({report.report_type})'

    def test_report_status_choices(self, company, user):
        """Test valid report statuses."""
        from apps.analytics.models import Report

        report = Report.objects.create(
            company=company,
            report_type='hiring_funnel',
            name='Test',
            created_by=user,
        )

        valid_statuses = [s[0] for s in Report.STATUS_CHOICES]
        for status in valid_statuses:
            report.status = status
            report.save()
            report.refresh_from_db()
            assert report.status == status


class TestDailyMetric:
    """Tests for DailyMetric model."""

    def test_create_daily_metric(self, company):
        """Test creating daily metrics."""
        from apps.analytics.models import DailyMetric
        from django.utils import timezone

        metric = DailyMetric.objects.create(
            company=company,
            date=timezone.now().date(),
            new_applications=10,
            new_candidates=5,
        )
        assert metric.new_applications == 10
        assert metric.new_candidates == 5


class TestCachedQuery:
    """Tests for CachedQuery model."""

    def test_cached_query_expiration(self, company):
        """Test cached query expiration check."""
        from apps.analytics.models import CachedQuery
        from django.utils import timezone
        from datetime import timedelta

        # Non-expired query
        fresh = CachedQuery.objects.create(
            query_hash='abc123',
            query_type='test',
            company=company,
            expires_at=timezone.now() + timedelta(hours=1),
        )
        assert not fresh.is_expired

        # Expired query
        stale = CachedQuery.objects.create(
            query_hash='xyz789',
            query_type='test',
            company=company,
            expires_at=timezone.now() - timedelta(hours=1),
        )
        assert stale.is_expired

    def test_cached_query_unique_hash(self, company):
        """Test that query hash must be unique."""
        from apps.analytics.models import CachedQuery
        from django.utils import timezone
        from django.db import IntegrityError
        from datetime import timedelta

        CachedQuery.objects.create(
            query_hash='unique123',
            query_type='test',
            company=company,
            expires_at=timezone.now() + timedelta(hours=1),
        )

        with pytest.raises(IntegrityError):
            CachedQuery.objects.create(
                query_hash='unique123',
                query_type='other',
                company=company,
                expires_at=timezone.now() + timedelta(hours=1),
            )
