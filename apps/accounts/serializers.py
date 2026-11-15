import re
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db.models import Sum
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .constants import PERMISSION_CATEGORIES, PERMISSIONS
from .models import RolePermissionConfig, UserCustomPermission
from .utils import find_user_by_phone, normalize_phone_number, validate_phone_number

User = get_user_model()


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Gold standard JWT Login Serializer:
    1. Supports logging in with phone number (primary), email, OR username.
    2. Seamlessly accepts credentials sent under 'username', 'phone', or 'email' without breaking API.
    3. Normalizes Irish phone numbers (+353..., 08x..., spaced, unspaced).
    4. Embeds user profile, role, and permission array in the response.
    """
    username = serializers.CharField(required=False, allow_blank=True)
    email = serializers.CharField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'username' in self.fields:
            self.fields['username'].required = False
            self.fields['username'].allow_blank = True

    def validate(self, attrs):
        login_input = (
            attrs.get('username')
            or attrs.get('phone')
            or attrs.get('email')
            or attrs.get('identifier')
            or ''
        ).strip()
        password = attrs.get('password')

        if not login_input or not password:
            raise serializers.ValidationError('Credentials (phone number, email, or username) and password are required.')

        user = None

        # 1. If login input contains '@', search by email first
        if '@' in login_input:
            candidate = User.objects.filter(email__iexact=login_input).first()
            if candidate:
                user = authenticate(username=candidate.username, password=password)

        # 2. Check if login input matches a phone number (Irish & international formats)
        if not user:
            candidate = find_user_by_phone(login_input)
            if candidate:
                user = authenticate(username=candidate.username, password=password)

        # 3. Check if login input matches username
        if not user:
            candidate = User.objects.filter(username__iexact=login_input).first()
            if candidate:
                user = authenticate(username=candidate.username, password=password)

        # 4. Fallback direct authenticate
        if not user:
            user = authenticate(username=login_input, password=password)

        if not user:
            raise serializers.ValidationError('Invalid login credentials.')

        if not user.is_active:
            raise serializers.ValidationError('This account has been deactivated.')

        # Generate tokens with the user's authentic username
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
    Public registration serializer for customers:
    - User can choose to register with Phone Number (primary) OR Email (or both).
    - Username is optional; if omitted, automatically generated from phone or email.
    - Full backward compatibility: callers providing username, email, and phone continue to work smoothly.
    """
    username = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    phone = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=30)
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
        # 1. Passwords match check
        if attrs.get('password') != attrs.get('password_confirm'):
            raise serializers.ValidationError({'password_confirm': "Passwords do not match."})

        raw_phone = (attrs.get('phone') or '').strip()
        raw_email = (attrs.get('email') or '').strip()
        raw_username = (attrs.get('username') or '').strip()

        # 2. User must provide at least one contact method: phone or email
        if not raw_phone and not raw_email:
            raise serializers.ValidationError(
                "Either phone number or email is required to register."
            )

        # 3. Phone validation & uniqueness
        if raw_phone:
            normalized_phone = validate_phone_number(raw_phone)
            existing_user = find_user_by_phone(normalized_phone)
            if existing_user:
                raise serializers.ValidationError({'phone': "A user with this phone number already exists."})
            attrs['phone'] = normalized_phone
        else:
            attrs['phone'] = None

        # 4. Email validation & uniqueness
        if raw_email:
            clean_email = raw_email.lower()
            if User.objects.filter(email__iexact=clean_email).exists():
                raise serializers.ValidationError({'email': "A user with this email address already exists."})
            attrs['email'] = clean_email
        else:
            attrs['email'] = None

        # 5. Username handling
        if raw_username:
            if User.objects.filter(username__iexact=raw_username).exists():
                raise serializers.ValidationError({'username': "A user with that username already exists."})
            attrs['username'] = raw_username
        else:
            # Auto-generate unique username from phone or email
            if attrs.get('phone'):
                base = re.sub(r'[^\w+_-]', '', attrs['phone'])
            elif attrs.get('email'):
                base = attrs['email'].split('@')[0]
            else:
                base = 'customer'
            candidate = base
            counter = 1
            while User.objects.filter(username__iexact=candidate).exists():
                candidate = f"{base}_{counter}"
                counter += 1
            attrs['username'] = candidate

        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm', None)
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
    Supports phone number (primary) and/or email.
    """
    username = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    phone = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=30)
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

    def validate(self, attrs):
        raw_phone = (attrs.get('phone') or '').strip()
        raw_email = (attrs.get('email') or '').strip()
        raw_username = (attrs.get('username') or '').strip()

        if not raw_phone and not raw_email and not raw_username:
            raise serializers.ValidationError("At least one identifier (phone, email, or username) is required.")

        if raw_phone:
            normalized_phone = validate_phone_number(raw_phone)
            existing_user = find_user_by_phone(normalized_phone)
            if existing_user:
                raise serializers.ValidationError({'phone': "A user with this phone number already exists."})
            attrs['phone'] = normalized_phone
        else:
            attrs['phone'] = None

        if raw_email:
            clean_email = raw_email.lower()
            if User.objects.filter(email__iexact=clean_email).exists():
                raise serializers.ValidationError({'email': "A user with this email address already exists."})
            attrs['email'] = clean_email
        else:
            attrs['email'] = None

        if raw_username:
            if User.objects.filter(username__iexact=raw_username).exists():
                raise serializers.ValidationError({'username': "A user with that username already exists."})
            attrs['username'] = raw_username
        else:
            if attrs.get('phone'):
                base = re.sub(r'[^\w+_-]', '', attrs['phone'])
            elif attrs.get('email'):
                base = attrs['email'].split('@')[0]
            else:
                base = 'staff'
            candidate = base
            counter = 1
            while User.objects.filter(username__iexact=candidate).exists():
                candidate = f"{base}_{counter}"
                counter += 1
            attrs['username'] = candidate

        return attrs

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
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    phone = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=30)

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

    def validate(self, attrs):
        instance = getattr(self, 'instance', None)

        if 'phone' in attrs:
            raw_phone = (attrs.get('phone') or '').strip()
            if raw_phone:
                normalized_phone = validate_phone_number(raw_phone)
                existing = find_user_by_phone(normalized_phone)
                if existing and (not instance or existing.id != instance.id):
                    raise serializers.ValidationError({'phone': "This phone number is already registered to another account."})
                attrs['phone'] = normalized_phone
            else:
                attrs['phone'] = None

        if 'email' in attrs:
            raw_email = (attrs.get('email') or '').strip()
            if raw_email:
                clean_email = raw_email.lower()
                query = User.objects.filter(email__iexact=clean_email)
                if instance:
                    query = query.exclude(id=instance.id)
                if query.exists():
                    raise serializers.ValidationError({'email': "This email address is already registered to another account."})
                attrs['email'] = clean_email
            else:
                attrs['email'] = None

        # Ensure user maintains at least one valid contact method
        eff_email = attrs.get('email', instance.email if instance else None)
        eff_phone = attrs.get('phone', instance.phone if instance else None)
        if not eff_email and not eff_phone:
            raise serializers.ValidationError(
                "A user must have at least one contact method (phone number or email)."
            )

        return attrs


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

    def validate_permissions(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Permissions must be provided as a list of permission codes.")
        invalid_codes = [p for p in value if p not in PERMISSIONS]
        if invalid_codes:
            raise serializers.ValidationError(
                f"Invalid permission code(s): {', '.join(invalid_codes)}. Refer to catalog for valid codes."
            )
        # Deduplicate while preserving order
        return list(dict.fromkeys(value))


class UserCustomPermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserCustomPermission
        fields = ['granted_permissions', 'revoked_permissions', 'updated_at']

    def validate_granted_permissions(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("granted_permissions must be a list.")
        invalid_codes = [p for p in value if p not in PERMISSIONS]
        if invalid_codes:
            raise serializers.ValidationError(
                f"Invalid granted permission codes: {', '.join(invalid_codes)}"
            )
        return list(dict.fromkeys(value))

    def validate_revoked_permissions(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("revoked_permissions must be a list.")
        invalid_codes = [p for p in value if p not in PERMISSIONS]
        if invalid_codes:
            raise serializers.ValidationError(
                f"Invalid revoked permission codes: {', '.join(invalid_codes)}"
            )
        return list(dict.fromkeys(value))


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
