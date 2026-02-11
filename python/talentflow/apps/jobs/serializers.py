"""
TalentFlow Jobs Serializers
"""
from rest_framework import serializers

from apps.candidates.serializers import SkillSerializer
from .models import Job, Application, ApplicationNote


class JobSerializer(serializers.ModelSerializer):
    required_skills = SkillSerializer(many=True, read_only=True)
    preferred_skills = SkillSerializer(many=True, read_only=True)
    application_count = serializers.SerializerMethodField()

    class Meta:
        model = Job
        fields = [
            'id', 'title', 'department', 'description', 'status',
            'employment_type', 'experience_level', 'location',
            'is_remote', 'remote_type', 'salary_min', 'salary_max',
            'salary_currency', 'show_salary', 'required_skills',
            'preferred_skills', 'min_experience_years', 'max_experience_years',
            'education_level', 'pipeline_stages', 'target_hire_date',
            'created_at', 'published_at', 'application_count'
        ]

    def get_application_count(self, obj):
        return obj.applications.count()


class JobDetailSerializer(JobSerializer):
    hiring_manager_name = serializers.CharField(
        source='hiring_manager.get_full_name',
        read_only=True
    )
    created_by_name = serializers.CharField(
        source='created_by.get_full_name',
        read_only=True
    )

    class Meta(JobSerializer.Meta):
        fields = JobSerializer.Meta.fields + [
            'requirements', 'responsibilities', 'benefits',
            'hiring_manager_name', 'created_by_name', 'max_applications',
            'updated_at', 'closed_at'
        ]


class JobCreateSerializer(serializers.ModelSerializer):
    required_skill_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False
    )
    preferred_skill_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False
    )

    class Meta:
        model = Job
        fields = [
            'title', 'department', 'description', 'requirements',
            'responsibilities', 'benefits', 'employment_type',
            'experience_level', 'location', 'is_remote', 'remote_type',
            'salary_min', 'salary_max', 'salary_currency', 'show_salary',
            'min_experience_years', 'max_experience_years', 'education_level',
            'pipeline_stages', 'target_hire_date', 'max_applications',
            'required_skill_ids', 'preferred_skill_ids'
        ]

    def create(self, validated_data):
        required_skill_ids = validated_data.pop('required_skill_ids', [])
        preferred_skill_ids = validated_data.pop('preferred_skill_ids', [])

        job = super().create(validated_data)

        if required_skill_ids:
            job.required_skills.set(required_skill_ids)
        if preferred_skill_ids:
            job.preferred_skills.set(preferred_skill_ids)

        return job


class ApplicationNoteSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source='author.get_full_name', read_only=True)

    class Meta:
        model = ApplicationNote
        fields = ['id', 'note_type', 'content', 'author_name', 'created_at']
        read_only_fields = ['id', 'author_name', 'created_at']


class ApplicationSerializer(serializers.ModelSerializer):
    candidate_name = serializers.CharField(source='candidate.full_name', read_only=True)
    candidate_email = serializers.EmailField(source='candidate.email', read_only=True)
    job_title = serializers.CharField(source='job.title', read_only=True)

    class Meta:
        model = Application
        fields = [
            'id', 'job', 'job_title', 'candidate', 'candidate_name',
            'candidate_email', 'status', 'stage', 'match_score',
            'recruiter_score', 'interview_score', 'applied_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'applied_at', 'updated_at', 'match_score'
        ]


class ApplicationDetailSerializer(ApplicationSerializer):
    notes = ApplicationNoteSerializer(many=True, read_only=True)

    class Meta(ApplicationSerializer.Meta):
        fields = ApplicationSerializer.Meta.fields + [
            'cover_letter', 'recruiter_notes', 'reviewed_by', 'reviewed_at', 'notes'
        ]


class ApplicationCreateSerializer(serializers.Serializer):
    job_id = serializers.IntegerField()
    cover_letter = serializers.CharField(required=False, allow_blank=True)
