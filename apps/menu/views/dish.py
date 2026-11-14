from django.core.cache import cache
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import CanManageMenu, CanToggleMenuAvailability
from ..models import Dish
from ..serializers import DishSerializer
from ..services.cache import CACHE_KEY_POPULAR, CACHE_TIMEOUT, invalidate_menu_cache


class DishViewSet(viewsets.ModelViewSet):
    queryset = Dish.objects.select_related('category').prefetch_related('portion_options', 'extra_options').all()
    serializer_class = DishSerializer
    filterset_fields = ['category', 'category__slug', 'station', 'is_available', 'is_bestseller', 'is_popular', 'is_special']
    search_fields = ['name', 'description', 'category__name']
    ordering_fields = ['price', 'rating', 'orders_count', 'created_at']

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.is_authenticated and user.has_restaurant_permission('menu:manage'):
            return queryset
        return queryset.filter(category__is_active=True)

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'popular', 'bestsellers']:
            return [permissions.AllowAny()]
        if self.action in ['toggle_availability']:
            return [CanToggleMenuAvailability()]
        return [CanManageMenu()]

    @action(detail=False, methods=['get'])
    def popular(self, request):
        cached_popular = cache.get(CACHE_KEY_POPULAR)
        if cached_popular is not None:
            return Response(cached_popular)

        popular_dishes = self.get_queryset().filter(
            category__is_active=True, is_available=True, is_popular=True,
        )[:10]
        serializer = self.get_serializer(popular_dishes, many=True)
        cache.set(CACHE_KEY_POPULAR, serializer.data, CACHE_TIMEOUT)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def bestsellers(self, request):
        bestsellers = self.get_queryset().filter(
            category__is_active=True, is_available=True, is_bestseller=True,
        )[:10]
        serializer = self.get_serializer(bestsellers, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['patch', 'post'], url_path='toggle-availability')
    def toggle_availability(self, request, pk=None):
        """
        Complies with Specification:
        'If an ingredient becomes unavailable, staff should be able to
        temporarily mark the relevant menu item as unavailable.'
        Allows Kitchen Staff, Cashier, Manager, Admin to toggle dish availability.
        """
        dish = self.get_object()
        raw = request.data.get('is_available')

        if raw is not None:
            if isinstance(raw, str):
                dish.is_available = raw.lower() in ('true', '1')
            else:
                dish.is_available = bool(raw)
        else:
            dish.is_available = not dish.is_available

        dish.save(update_fields=['is_available'])
        invalidate_menu_cache()

        status_text = 'available' if dish.is_available else 'unavailable'
        return Response({
            'message': f"Menu item '{dish.name}' is now marked as {status_text}.",
            'id': dish.id,
            'name': dish.name,
            'is_available': dish.is_available,
        }, status=status.HTTP_200_OK)

    def perform_create(self, serializer):
        super().perform_create(serializer)
        invalidate_menu_cache()

    def perform_update(self, serializer):
        super().perform_update(serializer)
        invalidate_menu_cache()

    def perform_destroy(self, instance):
        super().perform_destroy(instance)
        invalidate_menu_cache()
