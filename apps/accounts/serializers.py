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
    3. Returns professional error messages on invalid credentials.
    4. Embeds user profile, role, and permission array in the response.
    """
    username_field = 'username'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.username_field in self.fields:
            self.fields[self.username_field].required = False
        self.fields['email'] = serializers.CharField(required=False, write_only=True)

    def validate(self, attrs):
        raw_identifier = (
            attrs.get('username')
            or attrs.get('email')
            or attrs.get('username_or_email')
        )
        password = attrs.get('password')

        if not raw_identifier or not password:
            raise serializers.ValidationError({
                'detail': 'Both email/username and password are required.'
            })

        identifier = str(raw_identifier).strip()
        user = None

        if '@' in identifier:
            user_candidate = User.objects.filter(email__iexact=identifier).first()
            if user_candidate:
                user = authenticate(
                    request=self.context.get('request'),
                    username=user_candidate.username,
                    password=password,
                )
        else:
            user = authenticate(
                request=self.context.get('request'),
                username=identifier,
                password=password,
            )
            if not user:
                user_candidate = User.objects.filter(email__iexact=identifier).first()
                if user_candidate:
                    user = authenticate(
                        request=self.context.get('request'),
                        username=user_candidate.username,
                        password=password,
                    )

        if not user:
            raise serializers.ValidationError({
                'detail': 'Invalid email or password. Please verify your credentials and try again.'
            })

        if not user.is_active:
            raise serializers.ValidationError({
                'detail': 'This account has been deactivated. Please contact support.'
            })

        self.user = user
        refresh = self.get_token(user)

        data = {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': {
                'id': user.id,
                'uuid': str(user.uuid),
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
                'date_joined': user.date_joined.isoformat() if user.date_joined else None,
            },
        }

        return data


class UserRegistrationSerializer(serializers.ModelSerializer):
    """
    Public registration serializer for customers.
    Supports password confirmation across various naming conventions:
    password_confirm, confirm_password, and confirmPassword.
    Supports single full name (name or full_name) without requiring last_name.
    Exposes unique customer uuid.
    """
    uuid = serializers.UUIDField(read_only=True)
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True, required=False)
    confirm_password = serializers.CharField(write_only=True, required=False)
    confirmPassword = serializers.CharField(write_only=True, required=False)
    full_name = serializers.CharField(write_only=True, required=False)
    name = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = [
            'id',
            'uuid',
            'username',
            'email',
            'name',
            'full_name',
            'first_name',
            'last_name',
            'phone',
            'password',
            'password_confirm',
            'confirm_password',
            'confirmPassword',
        ]
        read_only_fields = ['id', 'uuid']
        extra_kwargs = {
            'username': {'required': False},
            'first_name': {'required': False},
            'last_name': {'required': False},
            'phone': {'required': False},
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

        # Process full name or name if provided
        incoming_name = attrs.pop('full_name', None) or attrs.pop('name', None)
        if incoming_name and not attrs.get('first_name'):
            name_parts = str(incoming_name).strip().split(maxsplit=1)
            attrs['first_name'] = name_parts[0] if name_parts else ''
            attrs['last_name'] = name_parts[1] if len(name_parts) > 1 else ''

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
        validated_data.pop('full_name', None)
        validated_data.pop('name', None)
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
    Internal staff creation serializer used by Super Admin, Owner/Admin and Managers.
    Allows creating any person with any role (Super Admin, Manager, Admin, Kitchen, Delivery, Cashier, Customer).
    """
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    name = serializers.CharField(write_only=True, required=False)
    full_name = serializers.CharField(write_only=True, required=False)
    shift = serializers.CharField(write_only=True, required=False)
    assigned_section = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = [
            'username',
            'email',
            'first_name',
            'last_name',
            'name',
            'full_name',
            'phone',
            'role',
            'avatar',
            'password',
            'shift',
            'assigned_section',
        ]
        extra_kwargs = {
            'username': {'required': False},
            'first_name': {'required': False},
            'last_name': {'required': False},
            'email': {'required': True},
        }

    def validate_role(self, value):
        role_map = {
            'super_admin': User.Role.SUPER_ADMIN,
            'super admin': User.Role.SUPER_ADMIN,
            'admin': User.Role.ADMIN,
            'owner': User.Role.ADMIN,
            'manager': User.Role.MANAGER,
            'floor manager': User.Role.MANAGER,
            'general manager': User.Role.MANAGER,
            'kitchen_staff': User.Role.KITCHEN_STAFF,
            'kitchen': User.Role.KITCHEN_STAFF,
            'chef': User.Role.KITCHEN_STAFF,
            'head chef': User.Role.KITCHEN_STAFF,
            'delivery_staff': User.Role.DELIVERY_STAFF,
            'delivery': User.Role.DELIVERY_STAFF,
            'driver': User.Role.DELIVERY_STAFF,
            'cashier_front': User.Role.CASHIER_FRONT,
            'cashier': User.Role.CASHIER_FRONT,
            'customer': User.Role.CUSTOMER,
        }
        normalized = str(value).strip().lower()
        if normalized in role_map:
            return role_map[normalized]

        valid_staff_roles = [
            User.Role.SUPER_ADMIN,
            User.Role.ADMIN,
            User.Role.MANAGER,
            User.Role.KITCHEN_STAFF,
            User.Role.DELIVERY_STAFF,
            User.Role.CASHIER_FRONT,
            User.Role.CUSTOMER,
        ]
        if value not in valid_staff_roles:
            raise serializers.ValidationError(
                f"Role must be one of: {', '.join([r.value for r in valid_staff_roles])}"
            )
        return value

    def validate(self, attrs):
        # Extract full name if passed
        incoming_name = attrs.pop('full_name', None) or attrs.pop('name', None)
        if incoming_name and not attrs.get('first_name'):
            name_parts = str(incoming_name).strip().split(maxsplit=1)
            attrs['first_name'] = name_parts[0] if name_parts else ''
            attrs['last_name'] = name_parts[1] if len(name_parts) > 1 else ''

        # Auto-generate username from email if not explicitly provided
        if not attrs.get('username') and attrs.get('email'):
            base_username = attrs['email'].split('@')[0].replace('.', '_').replace('+', '_')
            candidate = base_username
            counter = 1
            while User.objects.filter(username=candidate).exists():
                candidate = f"{base_username}_{counter}"
                counter += 1
            attrs['username'] = candidate

        return attrs

    def create(self, validated_data):
        password = validated_data.pop('password')
        shift = validated_data.pop('shift', 'Morning (10:00 - 16:00)')
        assigned_section = validated_data.pop('assigned_section', '')

        role = validated_data.get('role', User.Role.MANAGER)
        is_staff = role in [
            User.Role.SUPER_ADMIN,
            User.Role.ADMIN,
            User.Role.MANAGER,
            User.Role.KITCHEN_STAFF,
            User.Role.DELIVERY_STAFF,
            User.Role.CASHIER_FRONT,
        ]
        is_superuser = (role == User.Role.SUPER_ADMIN)

        user = User.objects.create_user(
            password=password,
            is_staff=is_staff,
            is_superuser=is_superuser,
            **validated_data
        )

        # Sync with StaffMember roster if staff role
        if is_staff:
            try:
                from apps.staff.models import StaffMember
                role_display = (
                    'Floor Manager' if role == User.Role.MANAGER
                    else 'Head Chef' if role == User.Role.KITCHEN_STAFF
                    else 'Host' if role == User.Role.CASHIER_FRONT
                    else user.get_role_display() or 'Server'
                )
                section = assigned_section or (
                    'Operations & Floor' if role == User.Role.MANAGER
                    else 'Kitchen Line' if role == User.Role.KITCHEN_STAFF
                    else 'Front of House'
                )
                StaffMember.objects.get_or_create(
                    user=user,
                    defaults={
                        'name': user.get_full_name() or user.username,
                        'role': role_display,
                        'shift': shift,
                        'assigned_section': section,
                        'phone': user.phone or '',
                        'status': 'active',
                    }
                )
            except Exception:
                pass

        return user


class UserProfileSerializer(serializers.ModelSerializer):
    fullName = serializers.SerializerMethodField()
    roleDisplay = serializers.CharField(source='get_role_display', read_only=True)
    permissions = serializers.ListField(source='all_permissions', read_only=True)

    class Meta:
        model = User
        fields = [
            'id',
            'uuid',
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
