from django.conf import settings
from django.db import models


class Promotion(models.Model):
    code = models.CharField(max_length=40, unique=True)
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    discount_type = models.CharField(max_length=20, choices=[('percentage', 'Percentage'), ('fixed', 'Fixed amount')])
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    min_spend = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    valid_until = models.DateField()
    usage_limit = models.PositiveIntegerField(default=100)
    usage_count = models.PositiveIntegerField(default=0, editable=False)
    is_active = models.BooleanField(default=True)
    first_order_only = models.BooleanField(default=False)
    image_url = models.URLField(max_length=500, blank=True)
    badge = models.CharField(max_length=50, blank=True)

    class Meta:
        ordering = ['-id']


class RestaurantProfile(models.Model):
    name = models.CharField(max_length=150)
    story = models.TextField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)
    address = models.CharField(max_length=400, blank=True)
    city = models.CharField(max_length=100, blank=True)
    opening_hours = models.TextField(blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=11, decimal_places=7, null=True, blank=True)
    delivery_postcode_prefixes = models.JSONField(default=list, blank=True)
    delivery_fee = models.DecimalField(max_digits=8, decimal_places=2, default=2)
    free_delivery_threshold = models.DecimalField(max_digits=10, decimal_places=2, default=30)
    included_vat_percent = models.DecimalField(max_digits=5, decimal_places=2, default='13.50')
    ordering_enabled = models.BooleanField(default=True)


class Faq(models.Model):
    question = models.CharField(max_length=300)
    answer = models.TextField()
    category = models.CharField(max_length=80, default='General')
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['display_order', 'id']


class GalleryItem(models.Model):
    title = models.CharField(max_length=180)
    tag = models.CharField(max_length=80, blank=True)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=100)
    image_url = models.URLField(max_length=500)
    dish = models.ForeignKey('menu.Dish', null=True, blank=True, on_delete=models.SET_NULL)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-id']


class Review(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    order = models.ForeignKey('orders.Order', null=True, blank=True, on_delete=models.SET_NULL)
    name = models.CharField(max_length=150)
    location = models.CharField(max_length=120, blank=True)
    rating = models.PositiveSmallIntegerField()
    dish = models.CharField(max_length=200, blank=True)
    comment = models.TextField()
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']


class HelpfulVote(models.Model):
    review = models.ForeignKey(Review, related_name='helpful_votes', on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['review', 'user'], name='one_helpful_vote_per_user')]


class ContactMessage(models.Model):
    full_name = models.CharField(max_length=150)
    email = models.EmailField()
    subject = models.CharField(max_length=200)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=[('new', 'New'), ('read', 'Read'), ('resolved', 'Resolved')], default='new')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class NewsletterSubscriber(models.Model):
    email = models.EmailField(unique=True)
    consent = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class BannerSlide(models.Model):
    tag = models.CharField(max_length=120, default='SPECIAL OFFER', help_text='Badge or top highlight text')
    title_line1 = models.CharField(max_length=150, default='', help_text='First line of main heading')
    title_line2 = models.CharField(max_length=150, blank=True, default='', help_text='Second line / colored highlight text')
    subtitle = models.TextField(blank=True, help_text='Descriptive paragraph')
    cta_text = models.CharField(max_length=80, default='Order Now', help_text='Button label')
    cta_link = models.CharField(max_length=100, default='menu', help_text='Navigation target or link (e.g. menu, reservation, offers, order)')
    image_url = models.CharField(max_length=500, default='/figma-assets/hero-family-combos.png', help_text='Image URL or asset path')
    display_order = models.PositiveIntegerField(default=1, help_text='Slide sort order')
    is_active = models.BooleanField(default=True, help_text='Whether slide is visible on public site')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_order', 'id']

    def __str__(self):
        return f"{self.display_order}. {self.title_line1} {self.title_line2}".strip()

