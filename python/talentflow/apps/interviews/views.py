"""
TalentFlow Interview Views
"""
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Interview, InterviewFeedback, InterviewerAvailability
from .serializers import (
    InterviewSerializer,
    InterviewCreateSerializer,
    InterviewFeedbackSerializer,
    InterviewerAvailabilitySerializer,
    ScheduleSuggestionSerializer,
)
from .scheduling import (
    schedule_interview,
    suggest_interview_times,
    SchedulingError,
)


class InterviewListView(generics.ListCreateAPIView):
    """List and create interviews."""
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return InterviewCreateSerializer
        return InterviewSerializer

    def get_queryset(self):
        return Interview.objects.filter(
            application__job__company=self.request.user.company
        ).select_related(
            'application__candidate', 'application__job'
        ).prefetch_related('participants__user')

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class InterviewDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete an interview."""
    serializer_class = InterviewSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Interview.objects.filter(
            application__job__company=self.request.user.company
        ).select_related(
            'application__candidate', 'application__job'
        ).prefetch_related('participants__user')


class InterviewStatusView(APIView):
    """Update interview status."""
    permission_classes = [IsAuthenticated]

    def patch(self, request, interview_id):
        try:
            interview = Interview.objects.get(
                id=interview_id,
                application__job__company=request.user.company
            )
        except Interview.DoesNotExist:
            return Response(
                {'error': 'Interview not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        new_status = request.data.get('status')
        if new_status not in dict(Interview.STATUS_CHOICES):
            return Response(
                {'error': 'Invalid status'},
                status=status.HTTP_400_BAD_REQUEST
            )

        interview.status = new_status
        interview.save()

        return Response({'status': new_status})


class InterviewFeedbackListView(generics.ListCreateAPIView):
    """List and create interview feedback."""
    serializer_class = InterviewFeedbackSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        interview_id = self.kwargs.get('interview_id')
        return InterviewFeedback.objects.filter(
            interview_id=interview_id,
            interview__application__job__company=self.request.user.company
        ).select_related('interviewer')

    def perform_create(self, serializer):
        interview_id = self.kwargs.get('interview_id')
        interview = Interview.objects.get(
            id=interview_id,
            application__job__company=self.request.user.company
        )
        serializer.save(interview=interview, interviewer=self.request.user)


class InterviewerAvailabilityView(generics.ListCreateAPIView):
    """List and create interviewer availability."""
    serializer_class = InterviewerAvailabilitySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return InterviewerAvailability.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class ScheduleSuggestionView(APIView):
    """Get suggested interview times."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ScheduleSuggestionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            suggestions = suggest_interview_times(
                application_id=serializer.validated_data['application_id'],
                interviewer_ids=serializer.validated_data['interviewer_ids'],
                duration_minutes=serializer.validated_data['duration_minutes'],
                days_ahead=serializer.validated_data['days_ahead'],
                preferred_timezone=serializer.validated_data['preferred_timezone'],
            )
            return Response({'suggestions': suggestions})
        except SchedulingError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class ScheduleInterviewView(APIView):
    """Schedule a new interview."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = InterviewCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            interview = schedule_interview(
                application_id=serializer.validated_data['application'].id,
                interview_type=serializer.validated_data['interview_type'],
                scheduled_at=serializer.validated_data['scheduled_at'],
                duration_minutes=serializer.validated_data.get('duration_minutes', 60),
                interviewer_ids=serializer.validated_data.get('interviewer_ids', []),
                interview_timezone=serializer.validated_data.get('timezone', 'UTC'),
                created_by=request.user,
            )
            return Response(
                InterviewSerializer(interview).data,
                status=status.HTTP_201_CREATED
            )
        except SchedulingError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class MyInterviewsView(generics.ListAPIView):
    """List interviews for the current user (as interviewer)."""
    serializer_class = InterviewSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Interview.objects.filter(
            participants__user=self.request.user
        ).select_related(
            'application__candidate', 'application__job'
        ).distinct()
