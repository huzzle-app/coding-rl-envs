"""
TalentFlow Analytics Views
"""
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Count, Avg, Sum
from django.db.models.functions import TruncDate

from .models import Report, DailyMetric
from .serializers import ReportSerializer, DailyMetricSerializer, ReportCreateSerializer
from .caching import get_analytics_cache, compute_with_cache


class ReportListView(generics.ListCreateAPIView):
    """List and create reports."""
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return ReportCreateSerializer
        return ReportSerializer

    def get_queryset(self):
        return Report.objects.filter(company=self.request.user.company)

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company,
            created_by=self.request.user
        )


class ReportDetailView(generics.RetrieveDestroyAPIView):
    """Retrieve or delete a report."""
    serializer_class = ReportSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Report.objects.filter(company=self.request.user.company)


class DailyMetricsView(generics.ListAPIView):
    """Get daily metrics."""
    serializer_class = DailyMetricSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return DailyMetric.objects.filter(company=self.request.user.company)


class HiringFunnelView(APIView):
    """Get hiring funnel analytics."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.jobs.models import Application

        company = request.user.company

        cache_key = f"funnel:{company.id}"

        def compute_funnel():
            applications = Application.objects.filter(job__company=company)

            funnel = {
                'total_applications': applications.count(),
                'pending': applications.filter(status='pending').count(),
                'reviewing': applications.filter(status='reviewing').count(),
                'shortlisted': applications.filter(status='shortlisted').count(),
                'interviewing': applications.filter(status='interviewing').count(),
                'offer': applications.filter(status='offer').count(),
                'accepted': applications.filter(status='accepted').count(),
                'rejected': applications.filter(status='rejected').count(),
            }

            # Calculate conversion rates
            if funnel['total_applications'] > 0:
                funnel['conversion_to_shortlist'] = round(
                    funnel['shortlisted'] / funnel['total_applications'] * 100, 2
                )
                funnel['conversion_to_interview'] = round(
                    funnel['interviewing'] / funnel['total_applications'] * 100, 2
                )
                funnel['conversion_to_offer'] = round(
                    funnel['offer'] / funnel['total_applications'] * 100, 2
                )
                funnel['conversion_to_hire'] = round(
                    funnel['accepted'] / funnel['total_applications'] * 100, 2
                )

            return funnel

        funnel_data = compute_with_cache(cache_key, compute_funnel, ttl=1800)

        return Response(funnel_data)


class SourceEffectivenessView(APIView):
    """Get source effectiveness analytics."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.candidates.models import Candidate
        from apps.jobs.models import Application

        company = request.user.company

        # Source breakdown
        sources = Candidate.objects.filter(company=company).values('source').annotate(
            total=Count('id'),
            avg_score=Avg('overall_score'),
        )

        # Hired by source
        hired = Application.objects.filter(
            job__company=company,
            status='accepted'
        ).values('candidate__source').annotate(
            hired=Count('id')
        )

        hired_dict = {h['candidate__source']: h['hired'] for h in hired}

        source_data = []
        for source in sources:
            source_name = source['source']
            total = source['total']
            hired_count = hired_dict.get(source_name, 0)

            source_data.append({
                'source': source_name,
                'total_candidates': total,
                'average_score': round(source['avg_score'] or 0, 2),
                'hired': hired_count,
                'hire_rate': round(hired_count / total * 100, 2) if total > 0 else 0,
            })

        return Response({
            'sources': source_data,
            'total_sources': len(source_data),
        })


class RecruiterPerformanceView(APIView):
    """Get recruiter performance analytics."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.jobs.models import Application, Job
        from apps.accounts.models import User

        company = request.user.company

        recruiters = User.objects.filter(
            company=company,
            role__in=['recruiter', 'hiring_manager']
        )

        performance_data = []
        for recruiter in recruiters:
            # Jobs managed
            jobs_count = Job.objects.filter(
                recruiters=recruiter
            ).count()

            # Applications reviewed
            reviewed = Application.objects.filter(
                reviewed_by=recruiter
            ).count()

            # Hires made (applications they moved to accepted)
            hires = Application.objects.filter(
                job__recruiters=recruiter,
                status='accepted'
            ).count()

            performance_data.append({
                'recruiter_id': recruiter.id,
                'name': recruiter.get_full_name(),
                'jobs_managed': jobs_count,
                'applications_reviewed': reviewed,
                'hires': hires,
            })

        return Response({'recruiters': performance_data})


class TimeToHireView(APIView):
    """Get time-to-hire analytics."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.jobs.models import Application
        from django.db.models import F, ExpressionWrapper, DurationField

        company = request.user.company

        # Get hired applications with timing data
        hired = Application.objects.filter(
            job__company=company,
            status='accepted'
        ).annotate(
            time_to_hire=ExpressionWrapper(
                F('updated_at') - F('applied_at'),
                output_field=DurationField()
            )
        )

        if hired.exists():
            avg_days = sum(
                (a.time_to_hire.days for a in hired)
            ) / hired.count()

            fastest = min(a.time_to_hire.days for a in hired)
            slowest = max(a.time_to_hire.days for a in hired)
        else:
            avg_days = 0
            fastest = 0
            slowest = 0

        return Response({
            'average_days': round(avg_days, 1),
            'fastest_hire_days': fastest,
            'slowest_hire_days': slowest,
            'total_hires': hired.count(),
        })


class CacheStatsView(APIView):
    """Get cache statistics (admin only)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_staff:
            return Response(
                {'error': 'Admin access required'},
                status=status.HTTP_403_FORBIDDEN
            )

        cache = get_analytics_cache()
        stats = cache.get_stats()

        return Response(stats)
