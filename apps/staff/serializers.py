from rest_framework import serializers
from .models import StaffMember


class StaffMemberSerializer(serializers.ModelSerializer):
    assignedSection = serializers.CharField(source='assigned_section')

    class Meta:
        model = StaffMember
        fields = [
            'id',
            'name',
            'role',
            'shift',
            'status',
            'avatar',
            'assignedSection',
            'phone',
        ]

