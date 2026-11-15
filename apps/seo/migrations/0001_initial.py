import uuid
from decimal import Decimal
from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='MarketingCampaign',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(help_text='Campaign name (e.g. Google Local Search Lunch Special)', max_length=150)),
                ('utm_source', models.CharField(help_text='e.g. google, instagram, facebook, newsletter', max_length=50)),
                ('utm_medium', models.CharField(help_text='e.g. cpc, social, email, organic', max_length=50)),
                ('utm_campaign', models.CharField(help_text='e.g. dublin_indian_takeaway', max_length=100)),
                ('utm_term', models.CharField(blank=True, max_length=100)),
                ('utm_content', models.CharField(blank=True, max_length=100)),
                ('target_path', models.CharField(default='/order', max_length=200)),
                ('clicks_count', models.PositiveIntegerField(default=0)),
                ('conversions_count', models.PositiveIntegerField(default=0)),
                ('is_active', models.BooleanField(default=True)),
                ('start_date', models.DateField(default=django.utils.timezone.now)),
                ('end_date', models.DateField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Marketing Campaign',
                'verbose_name_plural': 'Marketing Campaigns',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='OptimizedImageMetadata',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('title', models.CharField(max_length=150)),
                ('alt_text', models.CharField(help_text='Accessible and descriptive alt text for search crawlers', max_length=255)),
                ('image_url', models.URLField(max_length=500)),
                ('webp_url', models.URLField(blank=True, help_text='Optimized WebP modern format URL', max_length=500)),
                ('width', models.PositiveIntegerField(default=1200)),
                ('height', models.PositiveIntegerField(default=800)),
                ('caption', models.TextField(blank=True)),
                ('is_lazy', models.BooleanField(default=True, help_text="Render with loading='lazy' for fast page speed")),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Optimized Image Metadata',
                'verbose_name_plural': 'Optimized Image Metadata',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='PageSEOMetadata',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('page_identifier', models.CharField(help_text="Key identifier (e.g. 'home', 'menu', 'reservations', 'order', 'about', 'contact', 'offers')", max_length=60, unique=True)),
                ('page_path', models.CharField(help_text="Clean URL path (e.g. '/', '/menu', '/reservations', '/order', '/contact')", max_length=200, unique=True)),
                ('meta_title', models.CharField(help_text='Target 50-60 characters', max_length=150)),
                ('meta_description', models.TextField(help_text='Target 140-160 characters for search snippet')),
                ('meta_keywords', models.CharField(blank=True, max_length=255)),
                ('canonical_url', models.URLField(blank=True, max_length=500)),
                ('og_title', models.CharField(blank=True, max_length=150)),
                ('og_description', models.TextField(blank=True)),
                ('og_image', models.URLField(blank=True, max_length=500)),
                ('og_type', models.CharField(default='website', max_length=50)),
                ('twitter_card', models.CharField(default='summary_large_image', max_length=30)),
                ('robots_directive', models.CharField(default='index, follow', help_text="Robots meta tag (e.g. 'index, follow' or 'noindex, follow')", max_length=50)),
                ('schema_type', models.CharField(default='Restaurant', max_length=50)),
                ('sitemap_priority', models.DecimalField(decimal_places=1, default=Decimal('0.8'), help_text='0.1 to 1.0 ranking for search crawlers', max_digits=3)),
                ('sitemap_changefreq', models.CharField(choices=[('always', 'Always'), ('hourly', 'Hourly'), ('daily', 'Daily'), ('weekly', 'Weekly'), ('monthly', 'Monthly'), ('yearly', 'Yearly'), ('never', 'Never')], default='weekly', max_length=20)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Page SEO Metadata',
                'verbose_name_plural': 'Page SEO Metadata',
                'ordering': ['page_path'],
            },
        ),
        migrations.CreateModel(
            name='RestaurantSEOProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('restaurant_name', models.CharField(default='Amber Spice Restaurant & Takeaway', max_length=200)),
                ('tagline', models.CharField(default='Authentic Indian Cuisine & Fine Dining in Dublin', max_length=255)),
                ('meta_title_default', models.CharField(default='Amber Spice | Authentic Indian Restaurant & Takeaway in Dublin', max_length=150)),
                ('meta_description_default', models.TextField(default='Experience authentic Indian cuisine, slow-cooked curries, tandoori grills, and aromatic biryanis at Amber Spice Dublin. Book your table or order online for delivery.')),
                ('canonical_domain', models.URLField(default='https://amberspice.ie', help_text='Canonical website root URL (e.g. https://amberspice.ie)')),
                ('street_address', models.CharField(default='12 Merrion Row', max_length=255)),
                ('city', models.CharField(default='Dublin', max_length=100)),
                ('region', models.CharField(default='Co. Dublin', max_length=100)),
                ('postal_code', models.CharField(default='D02 X224', max_length=20)),
                ('country', models.CharField(default='IE', max_length=10)),
                ('latitude', models.DecimalField(decimal_places=6, default=Decimal('53.338200'), max_digits=9)),
                ('longitude', models.DecimalField(decimal_places=6, default=Decimal('-6.254600'), max_digits=9)),
                ('google_maps_place_id', models.CharField(blank=True, help_text='Google Maps Place ID for reviews & CID', max_length=100)),
                ('google_maps_embed_url', models.URLField(blank=True, help_text='Embed iframe URL for Google Maps', max_length=500)),
                ('google_business_url', models.URLField(blank=True, help_text='Direct link to Google Business Profile', max_length=500)),
                ('phone', models.CharField(default='+353 (0)1 234 5678', max_length=30)),
                ('email', models.EmailField(default='info@amberspice.ie', max_length=254)),
                ('price_range', models.CharField(default='€€', help_text='Schema priceRange: €, €€, or €€€', max_length=10)),
                ('cuisine_types', models.JSONField(blank=True, default=list, help_text="Cuisines served: ['Indian', 'Curry', 'Tandoori', 'Biryani', 'South Asian']")),
                ('opening_hours_json', models.JSONField(blank=True, default=dict, help_text="Weekly opening hours schema: {'Mo-Su': '12:00-23:00'}")),
                ('og_image_url', models.URLField(blank=True, help_text='Default 1200x630 share image for social media', max_length=500)),
                ('twitter_handle', models.CharField(blank=True, default='@AmberSpiceDublin', max_length=50)),
                ('ga4_measurement_id', models.CharField(blank=True, help_text='Google Analytics 4 Measurement ID (e.g. G-XXXXXXX)', max_length=50)),
                ('gtm_container_id', models.CharField(blank=True, help_text='Google Tag Manager Container ID (e.g. GTM-XXXXXXX)', max_length=50)),
                ('meta_pixel_id', models.CharField(blank=True, help_text='Meta / Facebook Pixel ID', max_length=50)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Restaurant SEO & Local Profile',
                'verbose_name_plural': 'Restaurant SEO & Local Profile',
            },
        ),
    ]

