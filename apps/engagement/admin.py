from django.contrib import admin
from .models import Promotion, Faq, GalleryItem, Review, ContactMessage, NewsletterSubscriber, RestaurantProfile

for model in [Promotion, Faq, GalleryItem, Review, ContactMessage, NewsletterSubscriber, RestaurantProfile]:
    admin.site.register(model)
