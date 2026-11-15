from rest_framework import serializers

try:
    from apps.accounts.utils import normalize_phone_number
except ImportError:
    def normalize_phone_number(val):
        return val

from .models import StaffAttendance, StaffMember, StaffShift


class StaffAttendanceSerializer(serializers.ModelSerializer):
    staffMember = serializers.PrimaryKeyRelatedField(source='staff_member', queryset=StaffMember.objects.all(), required=False)
    staffMemberName = serializers.CharField(source='staff_member.name', read_only=True)
    clockIn = serializers.DateTimeField(source='clock_in', required=False)
    clockOut = serializers.DateTimeField(source='clock_out', required=False, allow_null=True)
    breakMinutes = serializers.IntegerField(source='break_minutes', required=False)
    totalHours = serializers.DecimalField(source='total_hours', max_digits=5, decimal_places=2, read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)

    class Meta:
        model = StaffAttendance
        fields = [
            'id',
            'staff_member',
            'staffMember',
            'staffMemberName',
            'clock_in',
            'clockIn',
            'clock_out',
            'clockOut',
            'break_minutes',
            'breakMinutes',
            'total_hours',
            'totalHours',
            'status',
            'notes',
            'created_at',
            'createdAt',
        ]

    def to_internal_value(self, data):
        normalized = dict(data)
        mappings = {
            'staffMember': 'staff_member',
            'clockIn': 'clock_in',
            'clockOut': 'clock_out',
            'breakMinutes': 'break_minutes',
        }
        for camel, snake in mappings.items():
            if camel in normalized and snake not in normalized:
                normalized[snake] = normalized[camel]
        return super().to_internal_value(normalized)


class StaffShiftSerializer(serializers.ModelSerializer):
    staffMember = serializers.PrimaryKeyRelatedField(source='staff_member', queryset=StaffMember.objects.all(), required=False)
    staffMemberName = serializers.CharField(source='staff_member.name', read_only=True)
    staffMemberRole = serializers.CharField(source='staff_member.role', read_only=True)
    shiftDate = serializers.DateField(source='shift_date', required=False)
    startTime = serializers.TimeField(source='start_time', required=False)
    endTime = serializers.TimeField(source='end_time', required=False)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)

    class Meta:
        model = StaffShift
        fields = [
            'id',
            'staff_member',
            'staffMember',
            'staffMemberName',
            'staffMemberRole',
            'shift_date',
            'shiftDate',
            'start_time',
            'startTime',
            'end_time',
            'endTime',
            'title',
            'station',
            'status',
            'notes',
            'created_at',
            'createdAt',
        ]

    def to_internal_value(self, data):
        normalized = dict(data)
        mappings = {
            'staffMember': 'staff_member',
            'shiftDate': 'shift_date',
            'startTime': 'start_time',
            'endTime': 'end_time',
        }
        for camel, snake in mappings.items():
            if camel in normalized and snake not in normalized:
                normalized[snake] = normalized[camel]
        return super().to_internal_value(normalized)


class StaffMemberSerializer(serializers.ModelSerializer):
    # Preserved Legacy API Fields (100% backward compatible)
    assignedSection = serializers.CharField(source='assigned_section', required=False)

    # Modern Employee Fields
    userId = serializers.IntegerField(source='user.id', read_only=True, allow_null=True)
    hourlyRate = serializers.DecimalField(source='hourly_rate', max_digits=8, decimal_places=2, required=False, allow_null=True)
    hireDate = serializers.DateField(source='hire_date', required=False, allow_null=True)
    emergencyContactName = serializers.CharField(source='emergency_contact_name', required=False, allow_blank=True)
    emergencyContactPhone = serializers.CharField(source='emergency_contact_phone', required=False, allow_blank=True)
    isActive = serializers.BooleanField(source='is_active', required=False)
    isOnDuty = serializers.BooleanField(source='is_on_duty', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)

    class Meta:
        model = StaffMember
        fields = [
            # Legacy Fields
            'id',
            'name',
            'role',
            'shift',
            'status',
            'avatar',
            'assignedSection',
            'phone',
            # Snake-case & Modern Extensions
            'user',
            'userId',
            'email',
            'assigned_section',
            'hourly_rate',
            'hourlyRate',
            'hire_date',
            'hireDate',
            'emergency_contact_name',
            'emergencyContactName',
            'emergency_contact_phone',
            'emergencyContactPhone',
            'is_active',
            'isActive',
            'isOnDuty',
            'created_at',
            'createdAt',
            'updated_at',
            'updatedAt',
        ]
        read_only_fields = ['id', 'userId', 'isOnDuty', 'created_at', 'createdAt', 'updated_at', 'updatedAt']

    def to_internal_value(self, data):
        normalized = dict(data)
        mappings = {
            'assignedSection': 'assigned_section',
            'hourlyRate': 'hourly_rate',
            'hireDate': 'hire_date',
            'emergencyContactName': 'emergency_contact_name',
            'emergencyContactPhone': 'emergency_contact_phone',
            'isActive': 'is_active',
        }
        for camel, snake in mappings.items():
            if camel in normalized and snake not in normalized:
                normalized[snake] = normalized[camel]
        return super().to_internal_value(normalized)

    def validate_phone(self, value):
        if value:
            return normalize_phone_number(value)
        return value

    def validate_emergency_contact_phone(self, value):
        if value:
            return normalize_phone_number(value)
        return value
