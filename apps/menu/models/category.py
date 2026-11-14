from pathlib import Path
from uuid import uuid4

from django.db import models
from django.utils.text import slugify


def category_image_path(instance, filename):
    return f'menu/categories/{uuid4().hex}{Path(filename).suffix.lower()}'


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    image_url = models.URLField(max_length=500, blank=True, null=True)
    image = models.ImageField(upload_to=category_image_path, blank=True, null=True)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['order', 'name']

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name) or 'category'
            max_length = self._meta.get_field('slug').max_length
            candidate = base_slug[:max_length]
            suffix = 2
            while Category.objects.exclude(pk=self.pk).filter(slug__iexact=candidate).exists():
                ending = f'-{suffix}'
                candidate = f'{base_slug[:max_length - len(ending)]}{ending}'
                suffix += 1
            self.slug = candidate
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    @property
    def dish_count(self):
        if hasattr(self, 'available_dish_count'):
            return self.available_dish_count
        return self.dishes.filter(is_available=True).count()
