from rest_framework import serializers
from .models import SEOMetadata, RedirectRule


class SEOMetadataSerializer(serializers.ModelSerializer):
    class Meta:
        model = SEOMetadata
        fields = '__all__'


class SEOResolveSerializer(serializers.Serializer):
    path = serializers.CharField()
    title = serializers.CharField()
    description = serializers.CharField()
    keywords = serializers.CharField(allow_blank=True)
    canonicalUrl = serializers.CharField(allow_blank=True)
    robots = serializers.CharField()
    openGraph = serializers.DictField()
    twitter = serializers.DictField()
    structuredData = serializers.DictField(allow_null=True)


class RedirectRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = RedirectRule
        fields = '__all__'


class SEOAuditItemSerializer(serializers.Serializer):
    path = serializers.CharField()
    status = serializers.CharField()
    issues = serializers.ListField(child=serializers.CharField())
    score = serializers.IntegerField()


class SEOAuditReportSerializer(serializers.Serializer):
    total_pages = serializers.IntegerField()
    healthy_pages = serializers.IntegerField()
    pages_with_warnings = serializers.IntegerField()
    overall_score = serializers.IntegerField()
    reports = SEOAuditItemSerializer(many=True)
