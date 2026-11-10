from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    ChangePasswordView,
    CurrentUserView,
    CustomerListView,
    CustomLoginView,
    LogoutView,
    RegisterView,
    RolePermissionConfigViewSet,
    StaffViewSet,
    SuperAdminSetupView,
)

router = DefaultRouter()
router.register('staff', StaffViewSet, basename='staff-management')
router.register('roles-config', RolePermissionConfigViewSet, basename='roles-config')

urlpatterns = [
    # Authentication endpoints
    path('register/', RegisterView.as_view(), name='auth_register'),
    path('login/', CustomLoginView.as_view(), name='auth_login'),
    path('superadmin/setup/', SuperAdminSetupView.as_view(), name='superadmin_setup'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('logout/', LogoutView.as_view(), name='auth_logout'),

    # Profile & Password management
    path('me/', CurrentUserView.as_view(), name='auth_me'),
    path('change-password/', ChangePasswordView.as_view(), name='auth_change_password'),

    # Customer directory
    path('customers/', CustomerListView.as_view(), name='customer_list'),

    # ViewSets (staff management, roles-config)
    path('', include(router.urls)),
]
