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
    2. Accepts payload with key 'email', 'username', or 'username_or_email'.
    3. Embeds user profile, role, and permission array in the response.
    """
    username_field = 'username'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Allow username field to be optional so 'email' key can be passed directly
        if self.username_field in self.fields:
            self.fields[self.username_field].required = False
        self.fields['email'] = serializers.CharField(required=False, write_only=True)

    def validate(self, attrs):
        username_or_email = (
            attrs.get('username')
            or attrs.get('email')
            or attrs.get('username_or_email')
        )
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

        # Generate tokens using the user's actual username
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
    Supports password confirmation across various naming conventions:
    password_confirm, confirm_password, and confirmPassword.
    """
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True, required=False)
    confirm_password = serializers.CharField(write_only=True, required=False)
    confirmPassword = serializers.CharField(write_only=True, required=False)

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
            'confirm_password',
            'confirmPassword',
        ]
        extra_kwargs = {
            'username': {'required': False},
        }

    def validate(self, attrs):
        confirm = (
            attrs.get('password_confirm')
            or attrs.get('confirm_password')
            or attrs.get('confirmPassword')
        )
        if not confirm:
            raise serializers.ValidationError({'confirm_password': "Confirm password is required."})

        if attrs['password'] != confirm:
            raise serializers.ValidationError({'confirm_password': "Passwords do not match."})

        # If username is not provided, generate from email
        if not attrs.get('username') and attrs.get('email'):
            base_username = attrs['email'].split('@')[0]
            candidate = base_username
            counter = 1
            while User.objects.filter(username=candidate).exists():
                candidate = f"{base_username}{counter}"
                counter += 1
            attrs['username'] = candidate

        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm', None)
        validated_data.pop('confirm_password', None)
        validated_data.pop('confirmPassword', None)
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
