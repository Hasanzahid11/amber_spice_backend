from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import (
    PromotionViewSet,
    BannerSlideViewSet,
    FaqViewSet,
    GalleryViewSet,
    ReviewViewSet,
    ContactMessageViewSet,
    NewsletterViewSet,
    MenuAssistantView,
    RestaurantProfileViewSet,
)

router = DefaultRouter()
router.register('content/restaurant', RestaurantProfileViewSet, basename='restaurant-profile')
router.register('content/banners', BannerSlideViewSet, basename='banner-slide')
router.register('promotions', PromotionViewSet, basename='promotion')
router.register('content/faqs', FaqViewSet, basename='faq')
router.register('content/gallery', GalleryViewSet, basename='gallery')
router.register('reviews', ReviewViewSet, basename='review')
router.register('contact/messages', ContactMessageViewSet, basename='contact-message')
router.register('newsletter', NewsletterViewSet, basename='newsletter')
urlpatterns = [path('content/menu-assistant/', MenuAssistantView.as_view(), name='menu-assistant'), path('', include(router.urls))]
