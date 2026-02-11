"""
TalentFlow Jobs Views
"""
from rest_framework import generics, status, filters
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Job, Application, ApplicationNote
from .serializers import (
    JobSerializer,
    JobDetailSerializer,
    JobCreateSerializer,
    ApplicationSerializer,
    ApplicationDetailSerializer,
    ApplicationCreateSerializer,
    ApplicationNoteSerializer,
)
from .matching import apply_to_job, rank_candidates_for_job, MatchingError


class JobListView(generics.ListCreateAPIView):
    """List and create jobs."""
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'description', 'department']
    ordering_fields = ['created_at', 'title', 'status']

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return JobCreateSerializer
        return JobSerializer

    def get_queryset(self):
        return Job.objects.filter(
            company=self.request.user.company
        ).prefetch_related('required_skills', 'preferred_skills')

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company,
            created_by=self.request.user
        )


class JobDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a job."""
    serializer_class = JobDetailSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Job.objects.filter(
            company=self.request.user.company
        ).select_related('hiring_manager', 'created_by')


class JobPublishView(APIView):
    """Publish a job."""
    permission_classes = [IsAuthenticated]

    def post(self, request, job_id):
        try:
            job = Job.objects.get(id=job_id, company=request.user.company)
        except Job.DoesNotExist:
            return Response(
                {'error': 'Job not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        if job.status != 'draft':
            return Response(
                {'error': 'Job is not in draft status'},
                status=status.HTTP_400_BAD_REQUEST
            )

        job.publish()
        return Response({'status': job.status, 'published_at': job.published_at})


class JobCloseView(APIView):
    """Close a job."""
    permission_classes = [IsAuthenticated]

    def post(self, request, job_id):
        try:
            job = Job.objects.get(id=job_id, company=request.user.company)
        except Job.DoesNotExist:
            return Response(
                {'error': 'Job not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        job.close()
        return Response({'status': job.status, 'closed_at': job.closed_at})


class JobCandidatesView(APIView):
    """Get ranked candidates for a job."""
    permission_classes = [IsAuthenticated]

    def get(self, request, job_id):
        try:
            job = Job.objects.get(id=job_id, company=request.user.company)
        except Job.DoesNotExist:
            return Response(
                {'error': 'Job not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        limit = int(request.query_params.get('limit', 50))
        ranked = rank_candidates_for_job(job, limit=limit)

        return Response({
            'job_id': job_id,
            'candidates': [
                {
                    'id': r['candidate'].id,
                    'name': r['candidate'].full_name,
                    'email': r['candidate'].email,
                    'score': r['score'],
                    'skill_score': r['skill_score'],
                    'experience_score': r['experience_score'],
                }
                for r in ranked
            ]
        })


class ApplicationListView(generics.ListAPIView):
    """List applications for a job."""
    serializer_class = ApplicationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        job_id = self.kwargs.get('job_id')
        return Application.objects.filter(
            job_id=job_id,
            job__company=self.request.user.company
        ).select_related('candidate', 'job')


class ApplicationDetailView(generics.RetrieveUpdateAPIView):
    """Retrieve or update an application."""
    serializer_class = ApplicationDetailSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Application.objects.filter(
            job__company=self.request.user.company
        ).select_related('candidate', 'job').prefetch_related('notes')


class ApplicationCreateView(APIView):
    """Create a job application."""
    permission_classes = [IsAuthenticated]

    def post(self, request, candidate_id):
        from apps.candidates.models import Candidate

        serializer = ApplicationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            candidate = Candidate.objects.get(
                id=candidate_id,
                company=request.user.company
            )
            job = Job.objects.get(
                id=serializer.validated_data['job_id'],
                company=request.user.company
            )
        except Candidate.DoesNotExist:
            return Response(
                {'error': 'Candidate not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Job.DoesNotExist:
            return Response(
                {'error': 'Job not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            application = apply_to_job(
                candidate=candidate,
                job=job,
                cover_letter=serializer.validated_data.get('cover_letter', '')
            )
            return Response(
                ApplicationSerializer(application).data,
                status=status.HTTP_201_CREATED
            )
        except MatchingError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class ApplicationStatusView(APIView):
    """Update application status."""
    permission_classes = [IsAuthenticated]

    def patch(self, request, application_id):
        try:
            application = Application.objects.get(
                id=application_id,
                job__company=request.user.company
            )
        except Application.DoesNotExist:
            return Response(
                {'error': 'Application not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        new_status = request.data.get('status')
        if new_status not in dict(Application.STATUS_CHOICES):
            return Response(
                {'error': 'Invalid status'},
                status=status.HTTP_400_BAD_REQUEST
            )

        old_status = application.status
        application.status = new_status
        application.save()

        # Create status change note
        ApplicationNote.objects.create(
            application=application,
            author=request.user,
            note_type='status_change',
            content=f'Status changed from {old_status} to {new_status}'
        )

        return Response({'status': new_status})


class ApplicationNotesView(generics.ListCreateAPIView):
    """List and create notes for an application."""
    serializer_class = ApplicationNoteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        application_id = self.kwargs['application_id']
        return ApplicationNote.objects.filter(
            application_id=application_id,
            application__job__company=self.request.user.company
        ).select_related('author')

    def perform_create(self, serializer):
        application_id = self.kwargs['application_id']
        application = Application.objects.get(
            id=application_id,
            job__company=self.request.user.company
        )
        serializer.save(application=application, author=self.request.user)
