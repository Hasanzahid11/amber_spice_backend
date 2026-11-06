from django.contrib.auth import get_user_model
from rest_framework import generics, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .constants import PERMISSION_CATEGORIES, PERMISSIONS
from .models import RolePermissionConfig, UserCustomPermission
from .permissions import CanManageStaff, IsOwnerOrAdmin, IsRestaurantStaff
from .serializers import (
    ChangePasswordSerializer,
    CustomerAdminSerializer,
    CustomTokenObtainPairSerializer,
    RolePermissionConfigSerializer,
    StaffCreateSerializer,
    UserCustomPermissionSerializer,
    UserProfileSerializer,
    UserRegistrationSerializer,
)

User = get_user_model()


class CustomLoginView(TokenObtainPairView):
    """
    POST /api/v1/auth/login/
    Accepts username or email + password. Returns JWT tokens and user profile.
    """
    serializer_class = CustomTokenObtainPairSerializer


class RegisterView(generics.CreateAPIView):
    """
    POST /api/v1/auth/register/
    Customer registration. Returns tokens and user data on success.
    """
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Generate JWT tokens immediately upon registration
        refresh = RefreshToken.for_user(user)
        user_data = UserProfileSerializer(user).data

        return Response({
            'message': 'Account registered successfully.',
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': user_data,
        }, status=status.HTTP_201_CREATED)


class CurrentUserView(APIView):
    """
    GET /api/v1/auth/me/
    PATCH /api/v1/auth/me/
    Retrieves and updates currently authenticated user's profile and permissions.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data)

    def patch(self, request):
        serializer = UserProfileSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class ChangePasswordView(APIView):
    """
    POST /api/v1/auth/change-password/
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data['new_password'])
        request.user.save()
        return Response({'message': 'Password changed successfully.'}, status=status.HTTP_200_OK)


class LogoutView(APIView):
    """
    POST /api/v1/auth/logout/
    Blacklists the provided refresh token.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            if not refresh_token:
                return Response({'error': 'Refresh token is required.'}, status=status.HTTP_400_BAD_REQUEST)
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({'message': 'Logged out successfully.'}, status=status.HTTP_200_OK)
        except Exception:
            # If token blacklisting is not configured or token is expired, return success for client cleanup
            return Response({'message': 'Session ended.'}, status=status.HTTP_200_OK)


class RolePermissionConfigViewSet(viewsets.ModelViewSet):
    """
    Configurable Role Permissions API.
    GET /api/v1/auth/roles-config/
    PATCH /api/v1/auth/roles-config/<id>/
    Allows Owner/Admin to inspect and configure permissions per role.
    """
    queryset = RolePermissionConfig.objects.all()
    serializer_class = RolePermissionConfigSerializer
    permission_classes = [IsOwnerOrAdmin]

    @action(detail=False, methods=['get'])
    def catalog(self, request):
        """
        Returns the entire catalog of available permissions and categories.
        """
        return Response({
            'permissions': PERMISSIONS,
            'categories': PERMISSION_CATEGORIES,
        })


class StaffViewSet(viewsets.ModelViewSet):
    """
    Staff management viewset.
    Accessible by Owner/Admin and Manager.
    """
    queryset = User.objects.filter(role__in=[
        User.Role.ADMIN,
        User.Role.MANAGER,
        User.Role.KITCHEN_STAFF,
        User.Role.DELIVERY_STAFF,
        User.Role.CASHIER_FRONT,
    ])
    permission_classes = [CanManageStaff]
    filterset_fields = ['role', 'is_active']
    search_fields = ['username', 'first_name', 'last_name', 'email', 'phone']

    def get_serializer_class(self):
        if self.action == 'create':
            return StaffCreateSerializer
        return UserProfileSerializer

    @action(detail=True, methods=['get', 'patch'], permission_classes=[IsOwnerOrAdmin])
    def permissions(self, request, pk=None):
        """
        GET/PATCH /api/v1/auth/staff/<id>/permissions/
        Customize granted/revoked permissions for a specific staff user.
        """
        staff_user = self.get_object()
        custom_perm, _ = UserCustomPermission.objects.get_or_create(user=staff_user)

        if request.method == 'GET':
            return Response({
                'userId': staff_user.id,
                'username': staff_user.username,
                'role': staff_user.role,
                'rolePermissions': RolePermissionConfig.get_role_permissions(staff_user.role),
                'grantedPermissions': custom_perm.granted_permissions,
                'revokedPermissions': custom_perm.revoked_permissions,
                'effectivePermissions': staff_user.all_permissions,
            })

        # PATCH update
        granted = request.data.get('granted_permissions', custom_perm.granted_permissions)
        revoked = request.data.get('revoked_permissions', custom_perm.revoked_permissions)
        custom_perm.granted_permissions = granted
        custom_perm.revoked_permissions = revoked
        custom_perm.save()

        return Response({
            'message': f"Updated permissions for {staff_user.username}.",
            'effectivePermissions': staff_user.all_permissions,
        })


class CustomerListView(generics.ListAPIView):
    """
    GET /api/v1/auth/customers/
    List of registered customers with total orders and spending.
    """
    serializer_class = CustomerAdminSerializer
    permission_classes = [IsRestaurantStaff]

    def get_queryset(self):
        return User.objects.filter(role=User.Role.CUSTOMER).prefetch_related('orders')
