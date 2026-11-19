from hashlib import sha256
from uuid import uuid4

from django.core.cache import cache
from django.db.models import Count, Q
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import permissions, viewsets
from rest_framework.response import Response

from apps.accounts.permissions import CanManageMenu
from ..models import Category
from ..serializers import CategorySerializer
from ..services.cache import CACHE_KEY_CATEGORIES, CACHE_TIMEOUT, invalidate_menu_cache


@extend_schema_view(
    list=extend_schema(
        description='Public users see active categories. Users with menu:manage can also see inactive categories. '
                    'Supports is_active/slug filters, search, ordering and pagination.',
    ),
    create=extend_schema(description='Create a category. Requires menu:manage. Only name is required. '
                         'Upload an optional image as multipart/form-data; imageUrl returns its public URL.'),
    destroy=extend_schema(
        description='Archive the category by setting is_active=false. Existing dishes are preserved. '
                    'Requires menu:manage. Reactivate using PATCH.',
    ),
)
class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.annotate(
        available_dish_count=Count('dishes', filter=Q(dishes__is_available=True)),
    ).select_related('created_by').order_by('order', 'name', 'pk')
    serializer_class = CategorySerializer
    filterset_fields = ['is_active', 'slug']
    search_fields = ['name', 'description']
    ordering_fields = ['order', 'name', 'created_at']

    def can_manage_menu(self):
        user = self.request.user
        return user.is_authenticated and user.has_restaurant_permission('menu:manage')

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset if self.can_manage_menu() else queryset.filter(is_active=True)

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        return [CanManageMenu()]

    def list(self, request, *args, **kwargs):
        # Rotate the shared generation on a category/dish write to invalidate every variant.
        generation = cache.get_or_set(CACHE_KEY_CATEGORIES, lambda: uuid4().hex, timeout=None)
        audience = 'manage' if self.can_manage_menu() else 'public'
        request_hash = sha256(request.build_absolute_uri().encode()).hexdigest()
        cache_key = f'{CACHE_KEY_CATEGORIES}:{generation}:{audience}:{request_hash}'
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            return Response(cached_data)

        response = super().list(request, *args, **kwargs)
        cache.set(cache_key, response.data, CACHE_TIMEOUT)
        return response

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
        invalidate_menu_cache()

    def perform_update(self, serializer):
        super().perform_update(serializer)
        invalidate_menu_cache()

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=['is_active'])
        invalidate_menu_cache()
