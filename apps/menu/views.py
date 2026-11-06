from django.core.cache import cache
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import CanManageMenu, CanToggleMenuAvailability
from .models import Category, Dish
from .serializers import CategorySerializer, DishSerializer

CACHE_KEY_CATEGORIES = 'menu:categories'
CACHE_KEY_POPULAR = 'menu:popular_dishes'
CACHE_TIMEOUT = 60 * 15  # 15 minutes


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.filter(is_active=True).prefetch_related('dishes')
    serializer_class = CategorySerializer
    filterset_fields = ['is_active']
    search_fields = ['name', 'description']

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        return [CanManageMenu()]

    def list(self, request, *args, **kwargs):
        cached_data = cache.get(CACHE_KEY_CATEGORIES)
        if cached_data is not None:
            return Response(cached_data)

        response = super().list(request, *args, **kwargs)
        cache.set(CACHE_KEY_CATEGORIES, response.data, CACHE_TIMEOUT)
        return response

    def perform_create(self, serializer):
        super().perform_create(serializer)
        cache.delete(CACHE_KEY_CATEGORIES)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        cache.delete(CACHE_KEY_CATEGORIES)

    def perform_destroy(self, instance):
        super().perform_destroy(instance)
        cache.delete(CACHE_KEY_CATEGORIES)


class DishViewSet(viewsets.ModelViewSet):
    queryset = Dish.objects.select_related('category').prefetch_related('portion_options', 'extra_options').all()
    serializer_class = DishSerializer
    filterset_fields = ['category', 'category__slug', 'station', 'is_available', 'is_bestseller', 'is_popular', 'is_special']
    search_fields = ['name', 'description', 'category__name']
    ordering_fields = ['price', 'rating', 'orders_count', 'created_at']

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

        popular_dishes = self.get_queryset().filter(is_available=True, is_popular=True)[:10]
        serializer = self.get_serializer(popular_dishes, many=True)
        cache.set(CACHE_KEY_POPULAR, serializer.data, CACHE_TIMEOUT)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def bestsellers(self, request):
        bestsellers = self.get_queryset().filter(is_available=True, is_bestseller=True)[:10]
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
        cache.delete(CACHE_KEY_POPULAR)
        cache.delete(CACHE_KEY_CATEGORIES)

        status_text = 'available' if dish.is_available else 'unavailable'
        return Response({
            'message': f"Menu item '{dish.name}' is now marked as {status_text}.",
            'id': dish.id,
            'name': dish.name,
            'is_available': dish.is_available,
        }, status=status.HTTP_200_OK)

    def perform_create(self, serializer):
        super().perform_create(serializer)
        cache.delete(CACHE_KEY_POPULAR)
        cache.delete(CACHE_KEY_CATEGORIES)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        cache.delete(CACHE_KEY_POPULAR)
        cache.delete(CACHE_KEY_CATEGORIES)

    def perform_destroy(self, instance):
        super().perform_destroy(instance)
        cache.delete(CACHE_KEY_POPULAR)
        cache.delete(CACHE_KEY_CATEGORIES)
