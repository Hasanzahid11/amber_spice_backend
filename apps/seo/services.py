from decimal import Decimal
from django.conf import settings
from django.utils import timezone
from apps.engagement.models import RestaurantProfile
from apps.menu.models import Category, Dish
from .models import SEOMetadata, RedirectRule


DEFAULT_PAGES = [
    {
        'path': '/',
        'title': 'Amber Spice | Authentic Indian Cuisine & Charcoal Grill Dublin',
        'description': 'Experience authentic Awadhi & Old Delhi flavors in Dublin. Hand-ground spices, clay-oven tandoor, royal dum biryanis, and 100% Irish Halal certified meats.',
        'keywords': 'Indian Restaurant Dublin, Awadhi Cuisine, Charcoal Grill, Dum Biryani, Halal Indian Dublin, South William Street Dining',
        'priority': Decimal('1.0'),
        'change_frequency': 'daily',
        'og_type': 'restaurant',
    },
    {
        'path': '/menu',
        'title': 'Menu | Amber Spice Royal Indian Cuisine Dublin',
        'description': 'Explore our Dublin menu: Awadhi slow-cooked curries, charcoal grilled kebabs, fragrant dum biryanis, and fresh tandoori breads crafted with premium Irish ingredients.',
        'keywords': 'Amber Spice Menu, Indian Food Dublin, Dum Biryani Dublin, Butter Chicken, Tandoori Naan, Lamb Rogan Josh',
        'priority': Decimal('0.9'),
        'change_frequency': 'weekly',
        'og_type': 'restaurant.menu',
    },
    {
        'path': '/offers',
        'title': 'Special Offers & Vouchers | Amber Spice Dublin',
        'description': 'Exclusive dining offers and online delivery discounts at Amber Spice Dublin. Free delivery on orders over €30 and first-order welcome vouchers.',
        'keywords': 'Amber Spice Offers, Indian Food Discount Dublin, Free Delivery Dublin, Restaurant Vouchers',
        'priority': Decimal('0.8'),
        'change_frequency': 'weekly',
        'og_type': 'website',
    },
    {
        'path': '/about',
        'title': 'Our Story & Culinary Heritage | Amber Spice Dublin',
        'description': 'Discover the culinary journey of Amber Spice Dublin. Celebrating centuries-old Awadhi recipes, royal tandoor cooking, and culinary mastery on South William Street.',
        'keywords': 'About Amber Spice, Chef Story, Awadhi Heritage Dublin, Traditional Indian Spices',
        'priority': Decimal('0.7'),
        'change_frequency': 'monthly',
        'og_type': 'website',
    },
    {
        'path': '/delivery-info',
        'title': 'Delivery & Collection | Amber Spice Dublin 1, 2, 4, 6, 8',
        'description': 'Fast hot food delivery across Dublin city center and suburbs. Sealed insulated bag delivery with real-time courier tracking.',
        'keywords': 'Food Delivery Dublin, Indian Takeaway Dublin, Order Online Indian Food, Dublin Courier Tracking',
        'priority': Decimal('0.8'),
        'change_frequency': 'monthly',
        'og_type': 'website',
    },
    {
        'path': '/reviews',
        'title': 'Customer Reviews & Testimonials | Amber Spice Dublin',
        'description': 'Read verified customer dining reviews and food ratings for Amber Spice Dublin on South William Street.',
        'keywords': 'Amber Spice Reviews, Dublin Restaurant Ratings, Best Indian in Dublin Reviews',
        'priority': Decimal('0.7'),
        'change_frequency': 'weekly',
        'og_type': 'website',
    },
    {
        'path': '/gallery',
        'title': 'Culinary & Ambience Gallery | Amber Spice Dublin',
        'description': 'Take a visual tour of Amber Spice Dublin: signature dishes, royal atmosphere, and artisan spice preparation.',
        'keywords': 'Amber Spice Gallery, Indian Food Photos, Dublin Restaurant Ambience',
        'priority': Decimal('0.6'),
        'change_frequency': 'monthly',
        'og_type': 'website',
    },
    {
        'path': '/contact',
        'title': 'Contact & Table Reservations | Amber Spice Dublin',
        'description': 'Reserve your table at Amber Spice Dublin or get in touch for private dining, catering, and customer support.',
        'keywords': 'Book Table Amber Spice, Dublin Restaurant Contact, South William Street Phone',
        'priority': Decimal('0.7'),
        'change_frequency': 'monthly',
        'og_type': 'website',
    },
]


def ensure_default_metadata():
    """Seeds default metadata records if table is empty or missing paths."""
    for item in DEFAULT_PAGES:
        SEOMetadata.objects.get_or_create(
            path=item['path'],
            defaults={
                'title': item['title'],
                'description': item['description'],
                'keywords': item['keywords'],
                'priority': item['priority'],
                'change_frequency': item['change_frequency'],
                'og_title': item['title'],
                'og_description': item['description'],
                'og_type': item['og_type'],
                'twitter_title': item['title'],
                'twitter_description': item['description'],
                'canonical_url': f"https://amberspice.ie{item['path'] if item['path'] != '/' else ''}",
            }
        )


def build_restaurant_schema():
    """Generates live Schema.org Restaurant structured data from RestaurantProfile."""
    profile = RestaurantProfile.objects.order_by('id').first()
    name = profile.name if profile and profile.name else 'Amber Spice'
    phone = profile.phone if profile and profile.phone else '+353 1 234 5678'
    address = profile.address if profile and profile.address else '14 South William Street'
    city = profile.city if profile and profile.city else 'Dublin'
    lat = float(profile.latitude) if profile and profile.latitude else 53.3421
    lng = float(profile.longitude) if profile and profile.longitude else -6.2625

    return {
        '@context': 'https://schema.org',
        '@type': 'Restaurant',
        'name': name,
        'image': 'https://amberspice.ie/figma-assets/logo.png',
        '@id': 'https://amberspice.ie',
        'url': 'https://amberspice.ie',
        'telephone': phone,
        'priceRange': '€€',
        'servesCuisine': ['Indian', 'Awadhi', 'Mughlai', 'Halal', 'Charcoal Grill'],
        'address': {
            '@type': 'PostalAddress',
            'streetAddress': address,
            'addressLocality': city,
            'addressRegion': 'Co. Dublin',
            'postalCode': 'D02 P682',
            'addressCountry': 'IE',
        },
        'geo': {
            '@type': 'GeoCoordinates',
            'latitude': lat,
            'longitude': lng,
        },
        'openingHoursSpecification': [
            {
                '@type': 'OpeningHoursSpecification',
                'dayOfWeek': ['Monday', 'Tuesday', 'Wednesday', 'Thursday'],
                'opens': '17:00',
                'closes': '22:00',
            },
            {
                '@type': 'OpeningHoursSpecification',
                'dayOfWeek': ['Friday', 'Saturday'],
                'opens': '16:30',
                'closes': '22:30',
            },
            {
                '@type': 'OpeningHoursSpecification',
                'dayOfWeek': ['Sunday'],
                'opens': '16:30',
                'closes': '21:30',
            },
        ],
        'hasMenu': 'https://amberspice.ie/#menu',
        'acceptsReservations': 'True',
    }


def generate_sitemap_xml(base_url='https://amberspice.ie'):
    """Generates standard XML sitemap containing all pages, categories, and dishes."""
    ensure_default_metadata()
    now = timezone.now().strftime('%Y-%m-%d')
    base = base_url.rstrip('/')

    xml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]

    # 1. Main Pages
    pages = SEOMetadata.objects.filter(is_active=True).order_by('-priority', 'path')
    for page in pages:
        url_path = page.path if page.path != '/' else ''
        xml_lines.append('  <url>')
        xml_lines.append(f'    <loc>{base}{url_path}</loc>')
        xml_lines.append(f'    <lastmod>{page.updated_at.strftime("%Y-%m-%d")}</lastmod>')
        xml_lines.append(f'    <changefreq>{page.change_frequency}</changefreq>')
        xml_lines.append(f'    <priority>{page.priority}</priority>')
        xml_lines.append('  </url>')

    # 2. Categories
    categories = Category.objects.all().order_by('order', 'name')
    for cat in categories:
        xml_lines.append('  <url>')
        xml_lines.append(f'    <loc>{base}/#menu?category={cat.slug}</loc>')
        xml_lines.append(f'    <lastmod>{now}</lastmod>')
        xml_lines.append('    <changefreq>weekly</changefreq>')
        xml_lines.append('    <priority>0.8</priority>')
        xml_lines.append('  </url>')

    # 3. Available Dishes
    dishes = Dish.objects.filter(is_available=True).order_by('name')
    for dish in dishes:
        xml_lines.append('  <url>')
        xml_lines.append(f'    <loc>{base}/#menu?dish={dish.id}</loc>')
        xml_lines.append(f'    <lastmod>{now}</lastmod>')
        xml_lines.append('    <changefreq>weekly</changefreq>')
        xml_lines.append('    <priority>0.7</priority>')
        xml_lines.append('  </url>')

    xml_lines.append('</urlset>')
    return '\n'.join(xml_lines)


def generate_robots_txt(base_url='https://amberspice.ie'):
    """Generates standard robots.txt directives pointing to dynamic sitemap."""
    base = base_url.rstrip('/')
    return (
        f"User-agent: *\n"
        f"Allow: /\n"
        f"Disallow: /admin/\n"
        f"Disallow: /api/\n"
        f"Disallow: /rider/\n"
        f"Disallow: /track/\n\n"
        f"Sitemap: {base}/sitemap.xml\n"
    )


def audit_seo():
    """Audits SEO health across all active pages and calculates quality scores."""
    ensure_default_metadata()
    pages = SEOMetadata.objects.filter(is_active=True)
    reports = []
    total_score = 0

    for page in pages:
        issues = []
        score = 100

        # Title checks
        if not page.title:
            issues.append('Missing title tag')
            score -= 30
        elif len(page.title) < 30:
            issues.append('Title tag is too short (< 30 chars)')
            score -= 10
        elif len(page.title) > 70:
            issues.append('Title tag is too long (> 70 chars, will be truncated by Google)')
            score -= 5

        # Description checks
        if not page.description:
            issues.append('Missing meta description')
            score -= 30
        elif len(page.description) < 70:
            issues.append('Meta description is too short (< 70 chars)')
            score -= 10
        elif len(page.description) > 320:
            issues.append('Meta description exceeds optimal length')
            score -= 5

        # OpenGraph check
        if not page.og_title or not page.og_description:
            issues.append('Incomplete OpenGraph social sharing tags')
            score -= 10

        # Canonical check
        if not page.canonical_url:
            issues.append('Missing canonical URL')
            score -= 10

        score = max(score, 0)
        total_score += score
        status = 'healthy' if score >= 85 else 'warning' if score >= 60 else 'critical'
        reports.append({
            'path': page.path,
            'status': status,
            'issues': issues,
            'score': score,
        })

    total_pages = len(reports)
    avg_score = round(total_score / total_pages) if total_pages else 100
    healthy = sum(1 for r in reports if r['status'] == 'healthy')
    warnings = total_pages - healthy

    return {
        'total_pages': total_pages,
        'healthy_pages': healthy,
        'pages_with_warnings': warnings,
        'overall_score': avg_score,
        'reports': reports,
    }
