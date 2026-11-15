from django.db.models import Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import serializers
from drf_spectacular.utils import inline_serializer
from apps.accounts.permissions import HasRestaurantPermission
from .models import Promotion, Faq, GalleryItem, Review, HelpfulVote, ContactMessage, NewsletterSubscriber, RestaurantProfile
from .serializers import (PromotionSerializer, FaqSerializer, GalleryItemSerializer, ReviewSerializer,
                          ReviewModerationSerializer, ContactMessageSerializer, ContactStatusSerializer, NewsletterSerializer, RestaurantProfileSerializer)


def manages_content(user):
    return user.is_authenticated and user.has_restaurant_permission('settings:manage')


class RestaurantProfileViewSet(viewsets.ModelViewSet):
    queryset = RestaurantProfile.objects.all().order_by('id')
    serializer_class = RestaurantProfileSerializer
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_permissions(self):
        return [permissions.AllowAny()] if self.action in ['list', 'retrieve'] else [HasRestaurantPermission('settings:manage')]

    def perform_create(self, serializer):
        if RestaurantProfile.objects.exists():
            raise serializers.ValidationError({'detail': 'A restaurant profile already exists. Edit the saved profile.'})
        serializer.save(pk=1)


class PublicContentViewSet(viewsets.ModelViewSet):
    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        return [HasRestaurantPermission('settings:manage')]

    def get_queryset(self):
        queryset = super().get_queryset()
        if not manages_content(self.request.user):
            queryset = queryset.filter(is_active=True)
        return queryset


class PromotionViewSet(PublicContentViewSet):
    queryset = Promotion.objects.all()
    serializer_class = PromotionSerializer
    search_fields = ['code', 'title']

    def get_queryset(self):
        queryset = super().get_queryset()
        if not manages_content(self.request.user):
            queryset = queryset.filter(valid_until__gte=timezone.localdate())
        return queryset


class FaqViewSet(PublicContentViewSet):
    queryset = Faq.objects.all()
    serializer_class = FaqSerializer
    search_fields = ['question', 'answer', 'category']


class GalleryViewSet(PublicContentViewSet):
    queryset = GalleryItem.objects.select_related('dish').all()
    serializer_class = GalleryItemSerializer
    search_fields = ['title', 'category', 'description']


class ReviewViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                    mixins.UpdateModelMixin, viewsets.GenericViewSet):
    queryset = Review.objects.select_related('user', 'order').prefetch_related('helpful_votes').all()
    serializer_class = ReviewSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        if self.action in ['update', 'partial_update']:
            return [HasRestaurantPermission('settings:manage')]
        return [permissions.IsAuthenticated()]

    def get_serializer_class(self):
        return ReviewModerationSerializer if self.action in ['update', 'partial_update'] else ReviewSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if manages_content(user):
            return queryset
        return queryset.filter(Q(is_approved=True) | Q(user=user)) if user.is_authenticated else queryset.filter(is_approved=True)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user, name=self.request.user.get_full_name() or self.request.user.username)

    @extend_schema(request=None, responses=ReviewSerializer, description='JWT required. An account can mark a review helpful once; repeats are idempotent.')
    @action(detail=True, methods=['post'])
    def helpful(self, request, pk=None):
        review = self.get_object()
        HelpfulVote.objects.get_or_create(review=review, user=request.user)
        # Refresh the prefetched vote count after writing.
        review = Review.objects.get(pk=review.pk)
        return Response(ReviewSerializer(review).data)


class ContactMessageViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                          mixins.UpdateModelMixin, viewsets.GenericViewSet):
    queryset = ContactMessage.objects.all()
    serializer_class = ContactMessageSerializer
    filterset_fields = ['status']

    def get_serializer_class(self):
        return ContactStatusSerializer if self.action in ['update', 'partial_update'] else ContactMessageSerializer

    def get_permissions(self):
        return [permissions.AllowAny()] if self.action == 'create' else [HasRestaurantPermission('customers:view')]


class NewsletterViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = NewsletterSubscriber.objects.all()
    serializer_class = NewsletterSerializer

    def get_permissions(self):
        return [permissions.AllowAny()] if self.action == 'create' else [HasRestaurantPermission('settings:manage')]


class MenuAssistantView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(request=inline_serializer('MenuSearchRequest', fields={'question': serializers.CharField(max_length=500)}), responses=inline_serializer('MenuSearchResponse', fields={'message': serializers.CharField(), 'items': serializers.ListField(child=serializers.DictField())}), description='Search the current available catalog. This is a catalog assistant, not an LLM or an allergen-certification service.')
    def post(self, request):
        import re
        from apps.menu.models import Dish
        question = request.data.get('question', '')
        if not isinstance(question, str) or not question.strip() or len(question) > 500:
            raise serializers.ValidationError({'question': 'Enter a menu question of up to 500 characters.'})
        query = question.lower()
        dishes = Dish.objects.filter(is_available=True, category__is_active=True).select_related('category')
        if any(word in query for word in ['mild', 'creamy']):
            dishes = dishes.filter(spicy_level__lte=1)
        elif any(word in query for word in ['spicy', 'hot']):
            dishes = dishes.filter(spicy_level__gte=2)
        else:
            words = [word for word in re.findall(r'\w+', query) if word not in {'show', 'me', 'the', 'a', 'an', 'available', 'dishes', 'menu', 'recommend', 'what', 'is', 'your', 'best', 'please', 'vegetarian', 'vegan'}]
            if words:
                match = Q()
                for word in words:
                    match |= Q(name__icontains=word) | Q(description__icontains=word) | Q(category__name__icontains=word)
                dishes = dishes.filter(match)
        candidates = list(dishes.order_by('-orders_count', 'name')[:100])
        if 'vegetarian' in query or 'vegan' in query:
            label = 'vegan' if 'vegan' in query else 'vegetarian'
            candidates = [dish for dish in candidates if label in [str(value).lower() for value in dish.dietary]]
        rows = [{'id': dish.id, 'name': dish.name, 'price': str(dish.price), 'category': dish.category.name, 'dietary': dish.dietary} for dish in candidates[:5]]
        message = 'Available matching dishes: ' + '; '.join(f"{row['name']} (€{row['price']})" for row in rows) if rows else 'No matching available dishes. Try a dish or category name.'
        if any(word in query for word in ['allerg', 'halal', 'certif']):
            message = 'Certification and allergen details need confirmation from the restaurant. ' + message
        return Response({'message': message, 'items': rows})
