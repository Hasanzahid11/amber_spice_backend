from django.db import models


class SEOMetadata(models.Model):
    CHANGE_FREQ_CHOICES = [
        ('always', 'Always'),
        ('hourly', 'Hourly'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
        ('never', 'Never'),
    ]

    path = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Relative URL path, e.g. '/', '/menu', '/about', '/offers', '/contact'"
    )
    title = models.CharField(max_length=150, help_text="Meta title tag for search engines")
    description = models.TextField(max_length=320, help_text="Meta description tag for search snippets")
    keywords = models.CharField(max_length=300, blank=True, help_text="Comma-separated keywords")
    canonical_url = models.URLField(max_length=500, blank=True, help_text="Canonical URL to prevent duplicate content")

    # OpenGraph (Social media preview)
    og_title = models.CharField(max_length=150, blank=True)
    og_description = models.TextField(max_length=320, blank=True)
    og_image_url = models.URLField(max_length=500, blank=True)
    og_type = models.CharField(max_length=50, default='website')

    # Twitter Cards
    twitter_title = models.CharField(max_length=150, blank=True)
    twitter_description = models.TextField(max_length=320, blank=True)
    twitter_image_url = models.URLField(max_length=500, blank=True)

    # Search Engine Directives
    robots = models.CharField(max_length=50, default='index, follow', help_text="Robots directives, e.g. 'index, follow'")
    change_frequency = models.CharField(max_length=20, default='weekly', choices=CHANGE_FREQ_CHOICES)
    priority = models.DecimalField(max_digits=3, decimal_places=1, default=0.8, help_text="Sitemap priority from 0.0 to 1.0")

    # Schema.org structured data (JSON-LD)
    structured_data = models.JSONField(default=dict, blank=True, help_text="Custom Schema.org JSON-LD structured data")

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'SEO Metadata'
        verbose_name_plural = 'SEO Metadata'
        ordering = ['-priority', 'path']

    def __str__(self):
        return f"{self.path} - {self.title[:50]}"


class RedirectRule(models.Model):
    STATUS_CHOICES = [
        (301, '301 Permanent Redirect'),
        (302, '302 Temporary Redirect'),
    ]

    from_path = models.CharField(max_length=255, unique=True, db_index=True)
    to_path = models.CharField(max_length=500)
    status_code = models.PositiveSmallIntegerField(default=301, choices=STATUS_CHOICES)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Redirect Rule'
        verbose_name_plural = 'Redirect Rules'
        ordering = ['from_path']

    def __str__(self):
        return f"{self.from_path} -> {self.to_path} ({self.status_code})"
