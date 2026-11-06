from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db.models import Sum
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .constants import PERMISSION_CATEGORIES, PERMISSIONS
from .models import RolePermissionConfig, UserCustomPermission

User = get_user_model()


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Gold standard JWT Login Serializer:
    1. Supports logging in with EITHER username OR email.
    2. Embeds user profile, role, and permission array in the response.
    """
    username_field = 'username'

    def validate(self, attrs):
        username_or_email = attrs.get('username')
        password = attrs.get('password')

        if not username_or_email or not password:
            raise serializers.ValidationError('Both username/email and password are required.')

        user = None
        # Check if login input is email
        if '@' in username_or_email:
            user = User.objects.filter(email__iexact=username_or_email).first()
            if user:
                user = authenticate(username=user.username, password=password)
        else:
            user = authenticate(username=username_or_email, password=password)

        if not user:
            raise serializers.ValidationError('Invalid login credentials.')

        if not user.is_active:
            raise serializers.ValidationError('This account has been deactivated.')

        # Generate tokens
        data = super().validate({'username': user.username, 'password': password})

        # Add rich user details and permissions to response
        data['user'] = {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'fullName': user.get_full_name() or user.username,
            'role': user.role,
            'roleDisplay': user.get_role_display(),
            'avatar': user.avatar,
            'phone': user.phone,
            'isVip': user.is_vip,
            'isStaff': user.is_restaurant_staff,
            'permissions': user.all_permissions,
        }
        return data


class UserRegistrationSerializer(serializers.ModelSerializer):
    """
    Public registration serializer for customers.
    """
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = [
            'username',
            'email',
            'first_name',
            'last_name',
            'phone',
            'password',
            'password_confirm',
        ]

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({'password_confirm': "Passwords do not match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        # Public registrations are strictly customers
        user = User.objects.create_user(
            role=User.Role.CUSTOMER,
            password=password,
            **validated_data
        )
        return user


class StaffCreateSerializer(serializers.ModelSerializer):
    """
    Internal staff creation serializer used by Owner/Admin and Managers.
    """
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])

    class Meta:
        model = User
        fields = [
            'username',
            'email',
            'first_name',
            'last_name',
            'phone',
            'role',
            'avatar',
            'password',
        ]

    def validate_role(self, value):
        valid_staff_roles = [
            User.Role.ADMIN,
            User.Role.MANAGER,
            User.Role.KITCHEN_STAFF,
            User.Role.DELIVERY_STAFF,
            User.Role.CASHIER_FRONT,
        ]
        if value not in valid_staff_roles:
            raise serializers.ValidationError("Role must be a valid restaurant staff role.")
        return value

    def create(self, validated_data):
        password = validated_data.pop('password')
        role = validated_data.get('role', User.Role.CASHIER_FRONT)
        is_staff = role in [User.Role.ADMIN, User.Role.MANAGER]
        user = User.objects.create_user(
            password=password,
            is_staff=is_staff,
            **validated_data
        )
        return user


class UserProfileSerializer(serializers.ModelSerializer):
    fullName = serializers.SerializerMethodField()
    roleDisplay = serializers.CharField(source='get_role_display', read_only=True)
    permissions = serializers.ListField(source='all_permissions', read_only=True)

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'fullName',
            'role',
            'roleDisplay',
            'phone',
            'avatar',
            'is_vip',
            'is_active',
            'permissions',
            'date_joined',
        ]
        read_only_fields = ['id', 'username', 'role', 'roleDisplay', 'permissions', 'date_joined']

    def get_fullName(self, obj):
        return obj.get_full_name() or obj.username


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value


class RolePermissionConfigSerializer(serializers.ModelSerializer):
    availablePermissions = serializers.SerializerMethodField()
    categories = serializers.SerializerMethodField()

    class Meta:
        model = RolePermissionConfig
        fields = [
            'id',
            'role',
            'name',
            'description',
            'permissions',
            'is_customizable',
            'availablePermissions',
            'categories',
            'updated_at',
        ]
        read_only_fields = ['id', 'role', 'name', 'is_customizable', 'availablePermissions', 'categories', 'updated_at']

    def get_availablePermissions(self, obj):
        return PERMISSIONS

    def get_categories(self, obj):
        return PERMISSION_CATEGORIES


class UserCustomPermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserCustomPermission
        fields = ['granted_permissions', 'revoked_permissions', 'updated_at']


class CustomerAdminSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    orders_count = serializers.SerializerMethodField()
    total_spent = serializers.SerializerMethodField()
    last_order_date = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'name',
            'email',
            'phone',
            'is_vip',
            'orders_count',
            'total_spent',
            'last_order_date',
        ]

    def get_name(self, obj):
        return obj.get_full_name() or obj.username

    def get_orders_count(self, obj):
        return obj.orders.count()

    def get_total_spent(self, obj):
        total = obj.orders.filter(payment_status='paid').aggregate(total=Sum('total_amount'))['total']
        return float(total or 0.0)

    def get_last_order_date(self, obj):
        last_order = obj.orders.order_by('-created_at').first()
        return last_order.created_at.isoformat() if last_order else None
