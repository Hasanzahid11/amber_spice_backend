from rest_framework import serializers
from apps.profiles.models import UserProfile
from .address_serializer import UserAddressSerializer
from .preferences_serializer import UserPreferencesSerializer


class UserProfileSerializer(serializers.ModelSerializer):
    uuid = serializers.UUIDField(source='user.uuid', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', required=False)
    name = serializers.CharField(write_only=True, required=False)
    fullName = serializers.CharField(source='user.get_full_name', read_only=True)
    first_name = serializers.CharField(source='user.first_name', required=False)
    last_name = serializers.CharField(source='user.last_name', required=False)
    phone = serializers.CharField(source='user.phone', required=False, allow_null=True, allow_blank=True)
    avatar = serializers.URLField(source='user.avatar', required=False, allow_null=True, allow_blank=True)
    role = serializers.CharField(source='user.role', read_only=True)
    roleDisplay = serializers.CharField(source='user.get_role_display', read_only=True)
    isVip = serializers.BooleanField(source='user.is_vip', read_only=True)
    date_joined = serializers.DateTimeField(source='user.date_joined', read_only=True)
    dateJoined = serializers.DateTimeField(source='user.date_joined', read_only=True)
    memberSince = serializers.SerializerMethodField()

    loyaltyTierDisplay = serializers.CharField(source='get_loyalty_tier_display', read_only=True)
    completionPercentage = serializers.IntegerField(source='completion_percentage', read_only=True)
    nextTierPoints = serializers.IntegerField(source='next_tier_points', read_only=True)

    defaultAddress = serializers.SerializerMethodField()
    preferences = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = [
            'id',
            'uuid',
            'username',
            'email',
            'name',
            'fullName',
            'first_name',
            'last_name',
            'phone',
            'avatar',
            'role',
            'roleDisplay',
            'isVip',
            'date_joined',
            'dateJoined',
            'memberSince',
            'bio',
            'date_of_birth',
            'anniversary',
            'loyalty_points',
            'loyalty_tier',
            'loyaltyTierDisplay',
            'completionPercentage',
            'nextTierPoints',
            'default_delivery_instructions',
            'preferred_language',
            'emergency_contact',
            'defaultAddress',
            'preferences',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'username',
            'fullName',
            'role',
            'roleDisplay',
            'isVip',
            'loyalty_points',
            'loyalty_tier',
            'loyaltyTierDisplay',
            'completionPercentage',
            'nextTierPoints',
            'created_at',
            'updated_at',
        ]

    def get_memberSince(self, obj) -> str:
        if obj.user.date_joined:
            return obj.user.date_joined.strftime("%B %Y")
        return "Recent Member"

    def get_defaultAddress(self, obj):
        address = obj.user.saved_addresses.filter(is_default=True).first()
        if address:
            return UserAddressSerializer(address).data
        return None

    def get_preferences(self, obj):
        pref = getattr(obj.user, 'preferences', None)
        if pref:
            return UserPreferencesSerializer(pref).data
        return None

