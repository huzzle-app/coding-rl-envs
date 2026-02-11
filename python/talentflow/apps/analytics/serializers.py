"""
TalentFlow Analytics Serializers
"""
from rest_framework import serializers

from .models import Report, DailyMetric


class ReportSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(
        source='created_by.get_full_name',
        read_only=True
    )

    class Meta:
        model = Report
        fields = [
            'id', 'report_type', 'name', 'parameters',
            'date_range_start', 'date_range_end', 'status',
            'error_message', 'data', 'summary',
            'created_at', 'completed_at', 'created_by_name'
        ]
        read_only_fields = [
            'id', 'status', 'error_message', 'data', 'summary',
            'created_at', 'completed_at'
        ]


class ReportCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = [
            'report_type', 'name', 'parameters',
            'date_range_start', 'date_range_end'
        ]


class DailyMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyMetric
        fields = [
            'id', 'date',
            'new_applications', 'applications_reviewed',
            'applications_rejected', 'applications_shortlisted',
            'interviews_scheduled', 'interviews_completed', 'interviews_cancelled',
            'offers_extended', 'offers_accepted', 'offers_declined',
            'jobs_opened', 'jobs_closed', 'jobs_filled',
            'new_candidates'
        ]
