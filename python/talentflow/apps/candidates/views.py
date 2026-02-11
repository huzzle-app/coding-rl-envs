"""
TalentFlow Candidate Views

API views for managing candidates in the talent management system.
"""
from rest_framework import generics, status, filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Prefetch, Count, Avg

from .models import Candidate, CandidateSkill, CandidateNote, Skill
from .serializers import (
    CandidateSerializer,
    CandidateDetailSerializer,
    CandidateCreateSerializer,
    CandidateNoteSerializer,
    CandidateSkillSerializer,
)


class CandidateListView(generics.ListCreateAPIView):
    """
    List all candidates for the user's company.
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['first_name', 'last_name', 'email', 'title']
    ordering_fields = ['created_at', 'overall_score', 'status']

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CandidateCreateSerializer
        return CandidateSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = Candidate.objects.filter(company=user.company)

        # Prefetch skills for the candidate listing
        queryset = queryset.prefetch_related('skills')

        # Filter by status if provided
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        return queryset

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company,
            created_by=self.request.user
        )


class CandidateDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or delete a candidate.
    """
    serializer_class = CandidateDetailSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Candidate.objects.filter(company=user.company).select_related(
            'created_by', 'referred_by', 'company'
        ).prefetch_related(
            Prefetch(
                'candidate_skills',
                queryset=CandidateSkill.objects.select_related('skill')
            ),
            'activity_notes__author',
            'documents',
        )


class CandidateSkillsView(generics.ListCreateAPIView):
    """Manage skills for a candidate."""
    serializer_class = CandidateSkillSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        candidate_id = self.kwargs['candidate_id']
        return CandidateSkill.objects.filter(
            candidate_id=candidate_id,
            candidate__company=self.request.user.company
        ).select_related('skill')

    def perform_create(self, serializer):
        candidate_id = self.kwargs['candidate_id']
        candidate = Candidate.objects.get(
            id=candidate_id,
            company=self.request.user.company
        )
        serializer.save(candidate=candidate)


class CandidateNotesView(generics.ListCreateAPIView):
    """Manage notes for a candidate."""
    serializer_class = CandidateNoteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        candidate_id = self.kwargs['candidate_id']
        return CandidateNote.objects.filter(
            candidate_id=candidate_id,
            candidate__company=self.request.user.company
        ).select_related('author')

    def perform_create(self, serializer):
        candidate_id = self.kwargs['candidate_id']
        candidate = Candidate.objects.get(
            id=candidate_id,
            company=self.request.user.company
        )
        serializer.save(candidate=candidate, author=self.request.user)


class CandidateStatusView(APIView):
    """Update candidate status."""
    permission_classes = [IsAuthenticated]

    def patch(self, request, candidate_id):
        try:
            candidate = Candidate.objects.get(
                id=candidate_id,
                company=request.user.company
            )
        except Candidate.DoesNotExist:
            return Response(
                {'error': 'Candidate not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        new_status = request.data.get('status')
        if new_status not in dict(Candidate.STATUS_CHOICES):
            return Response(
                {'error': 'Invalid status'},
                status=status.HTTP_400_BAD_REQUEST
            )

        old_status = candidate.status
        candidate.status = new_status
        candidate.save()

        # Create status change note
        CandidateNote.objects.create(
            candidate=candidate,
            author=request.user,
            note_type='status_change',
            content=f'Status changed from {old_status} to {new_status}'
        )

        return Response({'status': new_status})


class CandidateSearchView(APIView):
    """
    Search candidates with advanced filters.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        company = request.user.company
        queryset = Candidate.objects.filter(company=company)

        # Apply filters from request body
        filters = request.data.get('filters', {})

        if 'status' in filters:
            queryset = queryset.filter(status__in=filters['status'])

        if 'skills' in filters:
            skill_ids = filters['skills']
            queryset = queryset.filter(skills__id__in=skill_ids).distinct()

        if 'min_experience' in filters:
            queryset = queryset.filter(years_experience__gte=filters['min_experience'])

        if 'max_experience' in filters:
            queryset = queryset.filter(years_experience__lte=filters['max_experience'])

        if 'location' in filters:
            queryset = queryset.filter(location__icontains=filters['location'])

        if 'source' in filters:
            queryset = queryset.filter(source__in=filters['source'])

        # Prefetch skills for results
        queryset = queryset.prefetch_related('skills')

        # Pagination
        page = request.data.get('page', 1)
        page_size = request.data.get('page_size', 20)
        start = (page - 1) * page_size
        end = start + page_size

        candidates = queryset[start:end]
        total = queryset.count()

        serializer = CandidateSerializer(candidates, many=True)

        return Response({
            'results': serializer.data,
            'total': total,
            'page': page,
            'page_size': page_size,
        })


class CandidateStatsView(APIView):
    """Get candidate statistics for the company."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company = request.user.company
        queryset = Candidate.objects.filter(company=company)

        stats = {
            'total': queryset.count(),
            'by_status': dict(
                queryset.values('status').annotate(count=Count('id')).values_list('status', 'count')
            ),
            'by_source': dict(
                queryset.values('source').annotate(count=Count('id')).values_list('source', 'count')
            ),
            'avg_score': queryset.aggregate(avg=Avg('overall_score'))['avg'],
        }

        return Response(stats)


class CandidateAdvancedSearchView(APIView):
    """
    Advanced candidate search with full-text search.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from django.db import connection

        company = request.user.company
        query = request.data.get('query', '')
        order_by = request.data.get('order_by', 'created_at')

        sql = f"""
            SELECT id, first_name, last_name, email, status, overall_score
            FROM candidates_candidate
            WHERE company_id = %s
            AND (
                first_name ILIKE %s
                OR last_name ILIKE %s
                OR email ILIKE %s
                OR title ILIKE %s
            )
            ORDER BY {order_by}
            LIMIT 100
        """

        search_pattern = f'%{query}%'

        with connection.cursor() as cursor:
            cursor.execute(sql, [company.id, search_pattern, search_pattern, search_pattern, search_pattern])
            columns = [col[0] for col in cursor.description]
            results = [dict(zip(columns, row)) for row in cursor.fetchall()]

        return Response({
            'results': results,
            'total': len(results),
        })


class CandidateExportView(APIView):
    """Export candidates to CSV."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        import csv
        from django.http import HttpResponse
        from datetime import datetime

        company = request.user.company
        candidates = Candidate.objects.filter(company=company)

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="candidates_{datetime.now():%x}.csv"'

        writer = csv.writer(response)
        writer.writerow(['Name', 'Email', 'Status', 'Score', 'Created'])

        for c in candidates:
            writer.writerow([
                f'{c.first_name} {c.last_name}',
                c.email,
                c.status,
                c.overall_score,
                c.created_at.strftime('%x %X'),  # Locale-dependent!
            ])

        return response
