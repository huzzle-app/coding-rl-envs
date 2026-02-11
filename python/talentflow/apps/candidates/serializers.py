"""
TalentFlow Candidate Serializers
"""
from rest_framework import serializers

from .models import Candidate, CandidateSkill, CandidateNote, CandidateDocument, Skill


class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ['id', 'name', 'category']


class CandidateSkillSerializer(serializers.ModelSerializer):
    skill = SkillSerializer(read_only=True)
    skill_id = serializers.PrimaryKeyRelatedField(
        queryset=Skill.objects.all(),
        source='skill',
        write_only=True
    )

    class Meta:
        model = CandidateSkill
        fields = [
            'id', 'skill', 'skill_id', 'proficiency',
            'years_used', 'is_primary', 'verified'
        ]


class CandidateNoteSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source='author.get_full_name', read_only=True)

    class Meta:
        model = CandidateNote
        fields = ['id', 'note_type', 'content', 'author_name', 'created_at']
        read_only_fields = ['id', 'author_name', 'created_at']


class CandidateDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = CandidateDocument
        fields = [
            'id', 'name', 'document_type', 'file_url',
            'file_size', 'mime_type', 'uploaded_at'
        ]
        read_only_fields = ['id', 'uploaded_at']


class CandidateSerializer(serializers.ModelSerializer):
    """
    Serializer for candidate list view.

    This serializer accesses candidate_skills to get proficiency info,
    which causes N+1 queries if not properly prefetched.
    """
    skills_with_proficiency = serializers.SerializerMethodField()
    created_by_name = serializers.CharField(
        source='created_by.get_full_name',
        read_only=True
    )

    class Meta:
        model = Candidate
        fields = [
            'id', 'first_name', 'last_name', 'email', 'phone',
            'status', 'title', 'current_company', 'years_experience',
            'location', 'skills_with_proficiency', 'overall_score',
            'source', 'created_at', 'created_by_name'
        ]

    def get_skills_with_proficiency(self, obj):
        """
        Get skills with proficiency info.
        """
        return [
            {
                'id': cs.skill.id,
                'name': cs.skill.name,  # Another query per skill!
                'proficiency': cs.proficiency,
                'is_primary': cs.is_primary,
            }
            for cs in obj.candidate_skills.all()  # Query per candidate!
        ]


class CandidateDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for single candidate view."""
    skills = CandidateSkillSerializer(
        source='candidate_skills',
        many=True,
        read_only=True
    )
    notes = CandidateNoteSerializer(
        source='activity_notes',
        many=True,
        read_only=True
    )
    documents = CandidateDocumentSerializer(many=True, read_only=True)
    created_by_name = serializers.CharField(
        source='created_by.get_full_name',
        read_only=True
    )
    referred_by_name = serializers.CharField(
        source='referred_by.get_full_name',
        read_only=True,
        allow_null=True
    )

    class Meta:
        model = Candidate
        fields = [
            'id', 'first_name', 'last_name', 'email', 'phone',
            'status', 'status_updated_at', 'title', 'current_company',
            'years_experience', 'location', 'skills', 'resume_url',
            'resume_text', 'linkedin_url', 'portfolio_url',
            'overall_score', 'skill_match_score', 'experience_score',
            'source', 'source_details', 'referred_by_name',
            'notes', 'tags', 'documents',
            'created_at', 'updated_at', 'created_by_name'
        ]
        read_only_fields = [
            'id', 'status_updated_at', 'created_at', 'updated_at',
            'created_by_name', 'referred_by_name'
        ]


class CandidateCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating candidates."""
    skill_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False
    )

    class Meta:
        model = Candidate
        fields = [
            'first_name', 'last_name', 'email', 'phone',
            'title', 'current_company', 'years_experience', 'location',
            'resume_url', 'resume_text', 'linkedin_url', 'portfolio_url',
            'source', 'source_details', 'notes', 'tags', 'skill_ids'
        ]

    def create(self, validated_data):
        skill_ids = validated_data.pop('skill_ids', [])
        candidate = super().create(validated_data)

        # Add skills
        for skill_id in skill_ids:
            try:
                skill = Skill.objects.get(id=skill_id)
                CandidateSkill.objects.create(
                    candidate=candidate,
                    skill=skill
                )
            except Skill.DoesNotExist:
                pass

        return candidate
