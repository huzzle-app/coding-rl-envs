"""
TalentFlow Interview Serializers
"""
from rest_framework import serializers

from .models import Interview, InterviewParticipant, InterviewFeedback, InterviewerAvailability


class InterviewParticipantSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = InterviewParticipant
        fields = ['id', 'user', 'user_name', 'user_email', 'role', 'status']


class InterviewSerializer(serializers.ModelSerializer):
    participants = InterviewParticipantSerializer(many=True, read_only=True)
    candidate_name = serializers.CharField(
        source='application.candidate.full_name',
        read_only=True
    )
    job_title = serializers.CharField(
        source='application.job.title',
        read_only=True
    )

    class Meta:
        model = Interview
        fields = [
            'id', 'application', 'interview_type', 'status', 'round_number',
            'scheduled_at', 'duration_minutes', 'timezone', 'location',
            'meeting_url', 'meeting_id', 'participants',
            'candidate_name', 'job_title', 'candidate_instructions',
            'created_at', 'updated_at'
        ]


class InterviewCreateSerializer(serializers.ModelSerializer):
    interviewer_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True
    )

    class Meta:
        model = Interview
        fields = [
            'application', 'interview_type', 'round_number',
            'scheduled_at', 'duration_minutes', 'timezone',
            'location', 'meeting_url', 'meeting_id', 'meeting_password',
            'candidate_instructions', 'interviewer_instructions',
            'interviewer_ids'
        ]

    def create(self, validated_data):
        interviewer_ids = validated_data.pop('interviewer_ids', [])
        interview = super().create(validated_data)

        # Add interviewers
        from apps.accounts.models import User
        for user_id in interviewer_ids:
            try:
                user = User.objects.get(id=user_id)
                InterviewParticipant.objects.create(
                    interview=interview,
                    user=user,
                    role='technical',
                    status='pending'
                )
            except User.DoesNotExist:
                pass

        return interview


class InterviewFeedbackSerializer(serializers.ModelSerializer):
    interviewer_name = serializers.CharField(
        source='interviewer.get_full_name',
        read_only=True
    )

    class Meta:
        model = InterviewFeedback
        fields = [
            'id', 'interview', 'interviewer', 'interviewer_name',
            'overall_rating', 'technical_rating', 'communication_rating',
            'culture_fit_rating', 'strengths', 'weaknesses', 'notes',
            'submitted_at', 'updated_at'
        ]
        read_only_fields = ['id', 'submitted_at', 'updated_at']


class InterviewerAvailabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = InterviewerAvailability
        fields = [
            'id', 'user', 'start_time', 'end_time',
            'is_recurring', 'recurrence_rule', 'is_available'
        ]
        read_only_fields = ['id']


class ScheduleSuggestionSerializer(serializers.Serializer):
    application_id = serializers.IntegerField()
    interviewer_ids = serializers.ListField(child=serializers.IntegerField())
    duration_minutes = serializers.IntegerField(default=60)
    days_ahead = serializers.IntegerField(default=7)
    preferred_timezone = serializers.CharField(default='America/New_York')
